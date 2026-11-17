"""Deterministic post-test tables/figures and bounded ranking casebook."""
from collections import defaultdict
import csv
import io
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import RUN,SEEDS,read,save
from summarize import table


def rows(name):return list(csv.DictReader((RUN/'tables'/name).open()))


def main():
    allrows=rows('all_frozen_models.csv');mainrows=rows('baseline_G1_G4.csv');cat=read(RUN/'data/catalogue.json')
    costs=[];cold=[];doc=[];coverage=[]
    for r in allrows:
        folder=RUN/'models'/r['model'];complete=read(folder/'complete.json');cfg=read(folder/'config.json');metrics=read(RUN/'evaluation'/r['model']/'test/metrics.json')
        costs.append(dict(model=r['model'],algorithm=r['algorithm'],training_loop_seconds=r['training_seconds'],test_evaluation_seconds=r['evaluation_seconds'],
            peak_cuda_allocated_bytes=complete.get('peak_cuda_bytes'),parameters=cfg.get('parameters'),best_epoch_or_snapshot=complete.get('best_epoch',complete.get('best_snapshot')),
            seconds_caveat='Missing initial AnyBURL learning wall time is blank; measured loops include validation, exclude dependency download/feature preparation; no end-to-end service claim'))
        for status in ['warm','one_cold','both_cold']:
            values=[metrics[t][status]['MRR'] for t in ['head','tail']]
            cold.append(dict(model=r['model'],algorithm=r['algorithm'],view=r['view'],prototype=r['prototype'],fraction=r['fraction'],noise=r['noise'],status=status,
                facts=metrics['tail'][status]['n'],link_MRR=float(np.mean(values)) if all(v is not None for v in values) else None))
        coverage.append(dict(model=r['model'],nonconstant_scores=float(r['discriminative_coverage']),rule_target_support=r['rule_target_support_coverage'],
            ranking_top1_exact_label_mismatches=(1-float(r['link_Hits1']))*426,
            schema_top1_violation_rate=float(r['top1_schema_violation']),
            caveat='Exact-label/tied-rank proxy, not fact-negative counts. Symbolic target support requires positive author rule score.'))
        path=RUN/'evaluation'/r['model']/'document_holdout/metrics.json'
        if path.exists():
            m=read(path);doc.append(dict(model=r['model'],algorithm=r['algorithm'],view=r['view'],prototype=r['prototype'],seed=r['seed'],link_MRR=m['link_MRR'],relation_MRR=m['relation']['all']['MRR'],facts=m['tail']['all']['n']))
    table('runtime_costs.csv',costs);table('cold_endpoint_metrics.csv',cold);table('prediction_error_and_coverage_proxies.csv',coverage);table('document_holdout_models.csv',doc)
    by=defaultdict(list)
    for r in doc:by[r['algorithm'],r['view'],r['prototype']].append(r)
    table('document_holdout_grouped.csv',[dict(algorithm=k[0],view=k[1],prototype=k[2],seeds=len(v),link_MRR_mean=float(np.mean([x['link_MRR'] for x in v])),
        link_MRR_sd=float(np.std([x['link_MRR'] for x in v])),facts_per_seed=v[0]['facts']) for k,v in sorted(by.items())])
    figdir=RUN/'figures';figdir.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,3,figsize=(12,3.8))
    for ax,alg in zip(axes,['anyburl','complex','simkgc']):
        rr=sorted([r for r in mainrows if r['algorithm']==alg],key=lambda r:r['display_view'])
        ax.bar([r['display_view'] for r in rr],[float(r['link_MRR_mean']) for r in rr],yerr=[float(r['link_MRR_sd']) for r in rr],capsize=3,color=['#527aa2','#409a87','#a98551','#9372aa'])
        ax.set(title={'anyburl':'AnyBURL (author JAR)','complex':'ComplEx (adaptation)','simkgc':'SimKGC-IB (adaptation)'}[alg],ylabel='Filtered exact-ID link MRR')
        ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.2)
    fig.suptitle('Same 213 masked Claims; three repeats (neural seeds fixed); label-recovery proxy')
    fig.tight_layout();fig.savefig(figdir/'baseline_G1_G4.png',dpi=180);fig.savefig(figdir/'baseline_G1_G4.svg');plt.close(fig)
    rr=rows('prototype_ablation.csv');lookup={r['prototype']:r for r in rr};order=['continue','anchor','anchor_uniform']
    fig,ax=plt.subplots(figsize=(6.5,4))
    ax.bar(['C0 continue','P1 KL + weights','P2 KL + uniform'],[float(lookup[v]['link_MRR_mean']) for v in order],
        yerr=[float(lookup[v]['link_MRR_sd']) for v in order],capsize=4,color=['#899ba6','#358672','#c0a455'])
    ax.set(ylabel='Filtered exact-ID link MRR',title='Matched initialization prototype; three seeds');ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(figdir/'prototype_ablation.png',dpi=180);fig.savefig(figdir/'prototype_ablation.svg');plt.close(fig)
    rr=read(RUN/'tables/grouped_metrics.json');base=next(r for r in rr if r['algorithm']=='complex' and r['view']=='G3' and r['fraction']==1 and r['noise']==0)
    fig,axes=plt.subplots(1,2,figsize=(9,3.6))
    for ax,key,selector,title in [(axes[0],'fraction',lambda r:r['noise']==0 and r['fraction'] in [.25,.5,1.], 'Auxiliary candidate scale'),
                                 (axes[1],'noise',lambda r:r['fraction']==1 and r['noise'] in [0,.25,.5], 'Synthetic type-compatible tail corruption')]:
        vals=sorted([r for r in rr if r['algorithm']=='complex' and r['view']=='G3' and selector(r)],key=lambda r:r[key])
        ax.errorbar([r[key] for r in vals],[r['link_MRR_mean'] for r in vals],yerr=[r['link_MRR_sd'] for r in vals],marker='o',capsize=3)
        ax.set(title=title,xlabel=key,ylabel='Link MRR');ax.set_ylim(bottom=0);ax.grid(alpha=.2)
    fig.suptitle('ComplEx-only sensitivity: low performance is not a robustness certificate')
    fig.tight_layout();fig.savefig(figdir/'scale_noise.png',dpi=180);fig.savefig(figdir/'scale_noise.svg');plt.close(fig)
    # Deterministic success/failure selection AFTER all model decisions are frozen.
    selected=read(RUN/'discovery/model_selection.json')['folder']
    rankings=read(RUN/'evaluation'/selected/'test/rankings.jsonl')
    sources=defaultdict(list)
    for r in read(RUN/'audit_only/base_source_records.jsonl'):sources[r['expanded_claim_id']].append(r)
    cases=[]
    for name,eligible,sorter in [('high_rank_failure',[r for r in rankings if r['task']!='relation' and r['rank']>100],lambda r:(-r['rank'],r['id'],r['task'])),
                                 ('rank1_recovery',[r for r in rankings if r['task']!='relation' and r['rank']==1],lambda r:(r['id'],r['task']))]:
        for q in sorted(eligible,key=sorter)[:4]:
            h,r,t=q['triple'];src=sources[q['id']]
            cases.append(dict(case=name,model=selected,claim_id=q['id'],task=q['task'],rank=q['rank'],endpoint_status=q['endpoint_status'],
                target=[cat['entities'][h]['label_zh'],cat['relations'][r],cat['entities'][t]['label_zh']],
                predicted_entity=cat['entities'][q['top1']]['label_zh'],predicted_type=cat['entities'][q['top1']]['entity_type'],
                evidence=[{k:x.get(k) for k in ['doc_id','pdf_page_number','source_family_id','head_surface','tail_surface','relation','evidence_text','applicability_scope']} for x in src],
                caveat='Recovery or failure against automatic base label only; target not human Gold; prediction may be an unlabelled alternative.'))
    save(RUN/'analysis/ranking_cases.jsonl',cases)
    text=['# 排名与文档核验失败案例\n','固定模型由验证集选择；以下按已冻结排序规则挑出4个大排名失败及4个rank1恢复。选择案例不会改变训练。排名失败不等于预测事实为假。\n']
    for i,c in enumerate(cases,1):
        text += [f"## {i}. {c['case']} / {c['claim_id']}",f"目标：{' → '.join(c['target'])}。任务{c['task']}，rank={c['rank']}，端点{c['endpoint_status']}。首选实体：{c['predicted_entity']}（{c['predicted_type']}）。"]
        for x in c['evidence']:text.append(f"源文：{x['doc_id']}物理页{x['pdf_page_number']}，{x['head_surface']} → {x['relation']} → {x['tail_surface']}。证据：{x['evidence_text']}。范围：{x['applicability_scope']}。")
    text += ['## 文档核验揭示的具体机制问题',
        'R09：MP022 p14的接液盘是泄漏后的收集措施，prevented_by错误改变了作用时点。R23：p35的O-ring(44)与(15)编号不同，模型按“同类密封+装配”相近语义错配。R06把安装位置短轴误当被维护对象。R08把收集泄漏液等同缓解泄漏本体，当前证据不足。',
        'R07和R19则显示有源文支持的动作仍须保留清洗步骤/型号或维护矩阵周期。R10—R13无检索支持，只能U，不能当错误事实。R22/R24有局部原子支持，但均为基础图已知知识；不算新发现。',
        '24例是定向诊断，不能外推26,328条预测的准确率。完整记录与证据见 ../discovery/SOURCE_REVIEW.md。']
    save(RUN/'analysis/FAILURE_CASES.md','\n\n'.join(text)+'\n')
    print('Tables, 3 scientific figures, and 8 ranking cases saved')


if __name__=='__main__':main()
