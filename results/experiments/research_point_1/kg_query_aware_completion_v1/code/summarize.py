"""Full seed tables, fact-group paired uncertainty, strata and errors."""
from collections import Counter,defaultdict
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io_utils import *

BASELINES=['simkgc_G1','simkgc_G2','simkgc_filter','collab_lan','collab_full','fixed_R1','fixed_R2','query_full','fixed_R3','transport_R3','knn_train_log','knn_candidates_log']
ABLATIONS=['query_full','query_no_retrieval','query_no_relation','query_no_structure','query_no_evidence','fixed_R3','transport_R3','query_k8','query_k32','query_conservative']


def main():
    assert (EXP/'evaluation/complete.json').exists() and (EXP/'evaluation'/f'knn_candidates_log_s{SEEDS[-1]}'/'complete.json').exists()
    allrows=[];grouped=defaultdict(list);ranks={};cost=[]
    for p in sorted((EXP/'evaluation').glob('*/metrics.json')):
        method,seed=p.parent.name.rsplit('_s',1);seed=int(seed);m=read(p);c=read(EXP/'models'/p.parent.name/'complete.json')
        row=dict(method=method,seed=seed,MRR=m['link_MRR'],head_MRR=m['head']['all']['MRR'],tail_MRR=m['tail']['all']['MRR'],Hits1=(m['head']['all']['Hits1']+m['tail']['all']['Hits1'])/2,Hits10=(m['head']['all']['Hits10']+m['tail']['all']['Hits10'])/2,relation_MRR=m['relation']['all']['MRR'],type_legal=1-(m['head']['top1_schema_violation_rate']+m['tail']['top1_schema_violation_rate'])/2,relation_type_legal=1-m['relation']['top1_schema_violation_rate'],best_epoch=c.get('best_epoch'),alpha=c.get('alpha'),validation_MRR=c['validation_link_MRR'],fit_seconds=c.get('seconds'),peak_cuda_bytes=c.get('peak_cuda_bytes'),numeric_diagnostic=method in ['knn_train','knn_candidates'])
        allrows.append(row);grouped[method].append(row);ranks[method,seed]=read(p.parent/'rankings.jsonl')
    means=[]
    for method,rr in sorted(grouped.items()):
        assert len(rr)==3
        d=dict(method=method)
        for k in ['MRR','Hits1','Hits10','head_MRR','tail_MRR','relation_MRR','type_legal','relation_type_legal','validation_MRR']:
            d[k]=float(np.mean([x[k] for x in rr]));d[k+'_sd']=float(np.std([x[k] for x in rr]))
        means.append(d)
    lookup={x['method']:x for x in means}
    csvsave('ALL_SEED_RESULTS.csv',allrows);csvsave('BASELINE_RESULTS.csv',[x for x in means if x['method'] in BASELINES]);csvsave('ABLATION_RESULTS.csv',[x for x in means if x['method'] in ABLATIONS])
    save(EXP/'analysis/grouped_metrics.json',means)
    groupmap={x['claim_id']:x['group_id'] for x in read(EXP/'data/base_split.jsonl')};paired=[]
    for method in ['query_full','transport_R3']:
        for control in ['simkgc_G1','simkgc_G2','simkgc_filter','collab_lan','collab_full','fixed_R1','fixed_R2','fixed_R3','transport_R3','query_no_retrieval','query_no_relation','query_no_structure','query_no_evidence','query_conservative']:
            if method==control:continue
            groups=defaultdict(list);seedmeans=[]
            for seed in SEEDS:
                a=ranks[method,seed];b={(x['id'],x['task']):x for x in ranks[control,seed]};dd=[]
                for x in a:
                    if x['task']=='relation':continue
                    delta=1/x['rank']-1/b[x['id'],x['task']]['rank'];groups[groupmap[x['id']]].append(delta);dd.append(delta)
                seedmeans.append(float(np.mean(dd)))
            values=np.array([np.mean(x) for x in groups.values()]);rng=np.random.default_rng(SEEDS[0]);boot=[float(np.mean(rng.choice(values,len(values)))) for _ in range(2000)]
            paired.append(dict(method=method,control=control,query_mean_delta=float(np.mean(seedmeans)),group_macro_delta=float(np.mean(values)),CI95=[float(x) for x in np.quantile(boot,[.025,.975])],seed_deltas=seedmeans,groups=len(values),all_seed_positive=min(seedmeans)>0,conditional_internal_proxy=True))
    save(EXP/'analysis/paired_comparisons.json',paired)
    # Overlapping descriptive strata, never used for selection.
    edges=read(EXP/'index/edges.jsonl');base=Counter();cand=Counter();graph=defaultdict(set)
    for e in edges:
        h,r,t=e['triple'];(base if e['is_base'] else cand).update([h,t])
        if e['is_base']:graph[h].add(t);graph[t].add(h)
    targets=read(EXP/'audit_only/test_targets.jsonl');strata={}
    for x in targets:
        h,r,t=x['triple'];tags=[x['endpoint_status']]
        if base[h] and base[t]:tags+=['both_base_supported']
        if (not base[h] or not base[t]) and base[h]+cand[h]>0 and base[t]+cand[t]>0:tags+=['candidate_assisted']
        if min(base[h],base[t])>=2:tags+=['rich_base_degree_at_least_2']
        if graph[h]&graph[t]:tags+=['base_two_step_connection']
        strata[x['id']]=tags
    save(EXP/'analysis/test_strata.json',dict(counts=dict(Counter(v for vv in strata.values() for v in vv)),per_fact=strata,note='Overlapping tags, not additive; endpoint coldness based on base training graph only'))
    rr=[]
    for method in BASELINES:
        for tag in sorted({t for tt in strata.values() for t in tt}):
            ss=[];nn=0
            for seed in SEEDS:
                vv=[1/x['rank'] for x in ranks[method,seed] if x['task']!='relation' and tag in strata[x['id']]];ss.append(float(np.mean(vv)));nn=len(vv)//2
            rr.append(dict(method=method,stratum=tag,facts=nn,MRR=float(np.mean(ss)),MRR_sd=float(np.std(ss))))
    csvsave('analysis/stratified_results.csv',rr)
    # Application policy uses validation family mean, never test performance.
    chosen=max(BASELINES,key=lambda m:lookup[m]['validation_MRR'])
    save(EXP/'analysis/application_selection.json',dict(method=chosen,seed=SEEDS[0],selection='Highest 3-seed validation mean among prespecified primary families; seed fixed first, never test best',validation_means={m:lookup[m]['validation_MRR'] for m in BASELINES}))
    errors=[]
    for method in ['query_full','transport_R3']:
        ref={(x['id'],x['task']):x for x in ranks['simkgc_G2',SEEDS[0]]}
        vv=[dict(x,delta_rr=1/x['rank']-1/ref[x['id'],x['task']]['rank'],baseline_rank=ref[x['id'],x['task']]['rank'],method=method) for x in ranks[method,SEEDS[0]] if x['task']!='relation']
        for direction in ['helped','hurt']:
            subset=[x for x in vv if (x['delta_rr']>0 if direction=='helped' else x['delta_rr']<0)]
            subset.sort(key=lambda x:x['delta_rr'],reverse=direction=='helped')
            errors.extend(dict(x,effect=direction) for x in subset[:4])
    source=defaultdict(list)
    for x in read(EXP/'audit_only/source_records.jsonl'):source[x['expanded_claim_id']].append(I.source_pointer(x))
    cat=read(EXP/'data/catalogue.json');R=len(cat['relations']);views=read(EXP/'index/oriented_views.jsonl');cache=np.load(EXP/'retrieval/R3_all_global.npz')['ids'];registry=read(EXP/'data/training_source_registry.json')
    for x in errors:
        h,r,t=x['triple'];anchor=h if x['task']=='tail' else t;qr=r if x['task']=='tail' else r+R
        x['target_source']=source[x['id']];x['retrieved']=[dict(view=views[int(i)],edge=edges[int(i)//2]) for i in cache[anchor,qr,:3] if i>=0]
    save(EXP/'analysis/error_cases.jsonl',errors)
    lines=['# 补全变化案例与错误边界\n','以下“成功”仅指自动基础目标的排名，不是事实正确率。只在训练和选择封存后回读目标源文。\n']
    for x in errors:
        h,r,t=x['triple'];pred=x['top1'];predtext=(cat['entities'][pred]['label_zh'],cat['relations'][r],cat['entities'][t]['label_zh']) if x['task']=='head' else (cat['entities'][h]['label_zh'],cat['relations'][r],cat['entities'][pred]['label_zh'])
        lines += [f"## {x['method']} / {x['effect']} / {x['id']} / {x['task']}",f"参考：{cat['entities'][h]['label_zh']} → {cat['relations'][r]} → {cat['entities'][t]['label_zh']}。预测Top1：{predtext}。rank {x['baseline_rank']}→{x['rank']}；预测Schema合法={x['top1_schema_valid']}。"]
        for s in x['target_source'][:1]:lines.append(f"目标参考来源（未作检索输入）：{s['doc_id']} p{s['pdf_page_number']}：{s['evidence_text']}")
        for c in x['retrieved']:
            v=c['view'];lines.append(f"上下文：{v['plain']} 来源{c['edge']['pages']}。")
    lines+=['\n角色/型号风险见retrieval/role_mismatch_cases.jsonl。不同作用对象、型号、条件的近似文字可能排到前列；Schema合法仍不保证关系正确。发生MRR改善但Top1仍错误者不计新增正确知识。',
        '固定迁移和神经残差均有负向实例，全部保留。候选相关性只有自动合同、原生地址和类型等代理检查；没有开展事实级大模型裁判或专家评价。']
    save(EXP/'ERROR_ANALYSIS.md','\n\n'.join(lines)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(13,4));methods=['simkgc_G1','simkgc_G2','simkgc_filter','collab_lan','collab_full','fixed_R1','fixed_R2','transport_R3','query_full']
    axes[0].bar(range(len(methods)),[lookup[m]['MRR'] for m in methods],yerr=[lookup[m]['MRR_sd'] for m in methods],capsize=3);axes[0].set_xticks(range(len(methods)),['G1','G2','Filter','LAN','Old Full','R1 fixed','R2 fixed','R3 transport','R3 neural'],rotation=30,ha='right');axes[0].set(ylabel='Link MRR',title='Frozen new internal task: all three seeds')
    retrieval=list(csv.DictReader((EXP/'RETRIEVAL_RESULTS.csv').open()));r=[x for x in retrieval if x['pool']=='all'];axes[1].bar([x['strategy'] for x in r],[int(x['distinct_used_candidates']) for x in r]);axes[1].set(ylabel='Distinct candidates used by training queries',title='Coverage is not factual accuracy')
    fig.tight_layout();(EXP/'figures').mkdir(exist_ok=True);fig.savefig(EXP/'figures/main_results.png',dpi=160);fig.savefig(EXP/'figures/main_results.svg');plt.close(fig)
    save(EXP/'analysis/summary_complete.json',dict(evaluation_entries=len(allrows),primary_entries=sum(not x['numeric_diagnostic'] for x in allrows),application_method=chosen,trained_models=39,source_truth_is_automatic=True))
    print('SUMMARIZED',len(allrows),'entries; selected application',chosen,flush=True)


if __name__=='__main__':main()
