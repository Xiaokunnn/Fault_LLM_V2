"""All conditions, seed uncertainty, held-gate probes and source-linked examples."""
from collections import defaultdict
import csv
import io
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from role_io import *
from evaluate import probe,OLD_METHODS
from contrast import load_parent
from train import ARMS


def table(name,rows):
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);save(NEW/'tables'/name,s.getvalue())


def main():
    allrows=[];mechanism=[];utility=[];exposure=[];compared=[]
    for dataset in ['cold','structured']:
        root=NEW/dataset;assert (root/'evaluation/complete.json').exists()
        for seed in SEEDS:utility.append(dict(dataset=dataset,**read(root/f'data/utility_{seed}.json')))
        for seed in SEEDS:
            for subset,values in read(root/'reference_probes'/f'parent_s{seed}'/'summary.json').items():
                mechanism.append(dict(dataset=dataset,method='parent_full',seed=seed,checkpoint='best',subset=subset,values=values))
        for reason,n in read(root/'data/candidate_exposure_summary.json')['counts'].items():exposure.append(dict(dataset=dataset,reason=reason,n=n,not_semantic_error=reason not in ['schema_illegal']))
        for p in sorted((root/'evaluation').glob('*/metrics.json')):
            m=read(p);name=p.parent.name;method,seedstr=name.rsplit('_s',1);seed=int(seedstr)
            row=dict(dataset=dataset,method=method,seed=seed,MRR=m['link_MRR'],Hits1=(m['head']['all']['Hits1']+m['tail']['all']['Hits1'])/2,
                Hits10=(m['head']['all']['Hits10']+m['tail']['all']['Hits10'])/2,relation_MRR=m['relation']['all']['MRR'],
                schema_legal=1-(m['head']['top1_schema_violation_rate']+m['tail']['top1_schema_violation_rate'])/2,reused=not name.startswith('role_'))
            if name.startswith('role_'):
                c=read(root/'models'/name/'complete.json');cfg=read(root/'models'/name/'config.json');row.update(best_epoch=c['best_epoch'],train_seconds=c['seconds'],trainable_parameters=cfg['trainable_parameters'])
                for which in ['best','last_diagnostic']:
                    summaries=read(p.parent/(which+'_probe_summary.json'))
                    for subset,s in summaries.items():mechanism.append(dict(dataset=dataset,method=method,seed=seed,checkpoint=which,subset=subset,values=s))
            else:row.update(best_epoch=None,train_seconds=None,trainable_parameters=None)
            allrows.append(row)
        assert sum(x['dataset']==dataset for x in allrows)==3*(len(ARMS)+len(OLD_METHODS))
        mapping={r['claim_id']:r['group_id'] for r in read(PARENT/dataset/'data/base_split.jsonl')}
        for control in ['collab_full','simkgc_G2','simkgc_filter','collab_lan','collab_no_dynamic','collab_no_neighbor',
                        'role_gate_kgc','role_joint_kgc','role_margin_only','role_absolute_only','role_joint_full','role_shuffled','role_relative_only']:
            if not (root/'evaluation'/f'{control}_s{SEEDS[0]}'/'rankings.jsonl').exists():continue
            grouped=defaultdict(list);seed_deltas=[]
            for seed in SEEDS:
                a=read(root/'evaluation'/f'role_full_s{seed}'/'rankings.jsonl');b=read(root/'evaluation'/f'{control}_s{seed}'/'rankings.jsonl');idx={(r['id'],r['task']):r for r in b};values=[]
                for r in a:
                    if r['task']=='relation':continue
                    v=1/r['rank']-1/idx[r['id'],r['task']]['rank'];grouped[mapping[r['id']]].append(v);values.append(v)
                seed_deltas.append(float(np.mean(values)))
            v=np.array([np.mean(x) for x in grouped.values()]);rng=np.random.default_rng(SEEDS[0]);draws=[float(np.mean(rng.choice(v,len(v),replace=True))) for _ in range(2000)]
            compared.append(dict(dataset=dataset,control=control,query_weighted_delta=float(np.mean(seed_deltas)),group_macro_delta=float(np.mean(v)),
                CI95=[float(x) for x in np.quantile(draws,[.025,.975])],seed_deltas=seed_deltas,groups=len(v),
                caution='Conditional exposed historical task, automatic labels, exploratory multiple contrasts; not factual or independent test accuracy'))
    table(f'all{len(allrows)}_evaluations.csv',allrows);table('all_evaluations.csv',allrows);save(NEW/'tables/mechanism_probes.jsonl',mechanism);save(NEW/'tables/utility_counts.json',utility);table('candidate_usage_reasons.csv',exposure);save(NEW/'tables/paired_comparisons.json',compared)
    groups=defaultdict(list)
    for r in allrows:groups[r['dataset'],r['method']].append(r)
    summaries=[]
    for (d,m),rr in sorted(groups.items()):
        assert len(rr)==3
        s=dict(dataset=d,method=m)
        for k in ['MRR','Hits1','Hits10','relation_MRR','schema_legal']:s[k]=float(np.mean([x[k] for x in rr]));s[k+'_sd']=float(np.std([x[k] for x in rr]))
        summaries.append(s)
    table('grouped_metrics.csv',summaries);save(NEW/'tables/grouped_metrics.json',summaries)
    lookup={(x['dataset'],x['method']):x for x in summaries}
    def mt(methods):
        lines=['| 场景 | 方法 | MRR±种子SD | Hits@1 | Hits@10 | 类型合法率 |','| --- | --- | --- | --- | --- | --- |']
        for dataset in ['cold','structured']:
            for method in methods:
                if (dataset,method) not in lookup:continue
                r=lookup[dataset,method];lines.append(f"| {dataset} | {method} | {r['MRR']:.6f} ± {r['MRR_sd']:.6f} | {r['Hits1']:.4f} | {r['Hits10']:.4f} | {r['schema_legal']:.4f} |")
        return '\n'.join(lines)
    probe_lines=['| 场景 | 方法/检查点 | probe强对照数(各seed) | gate+均值 | gate-均值 | 自然候选均值 | 自然饱和率>0.95 |','| --- | --- | --- | --- | --- | --- | --- |']
    for dataset in ['cold','structured']:
        for method in ['parent_full','role_gate_kgc','role_margin_only','role_absolute_only','role_full','role_joint_full','role_shuffled','role_relative_only']:
            if method!='parent_full' and (dataset,method) not in lookup:continue
            for checkpoint in (['best','last_diagnostic'] if method=='role_full' else ['best']):
                pp=[r['values'] for r in mechanism if r['dataset']==dataset and r['method']==method and r['checkpoint']==checkpoint and r['subset']=='probe_strong']
                nat=[r['values'] for r in mechanism if r['dataset']==dataset and r['method']==method and r['checkpoint']==checkpoint and r['subset']=='natural_validation_candidate_gates']
                def avg(rr,key):
                    vv=[x[key] for x in rr if x.get(key) is not None];return float(np.mean(vv)) if vv else float('nan')
                probe_lines.append(f"| {dataset} | {method}/{checkpoint} | {','.join(str(x['n']) for x in pp)} | {avg(pp,'mean_gate_plus'):.4f} | {avg(pp,'mean_gate_minus'):.4f} | {avg(nat,'mean'):.4f} | {avg(nat,'saturation_rate'):.4f} |")
    stable=all(c['CI95'][0]>0 and min(c['seed_deltas'])>0 for c in compared if c['control'] in ['simkgc_G2','simkgc_filter','collab_lan','collab_no_dynamic','role_gate_kgc','role_absolute_only'])
    decision='在固定历史任务的主要比较中出现一致正向证据，仍不能据此宣称独立事实风险或原创性已确认。' if stable else '未证明稳定超过G2、简单过滤、LAN和匹配简单损失；本轮不确认算法创新成立。'
    lines=f'''# 证据角色对照候选贡献学习：实际实验报告

日期2026-11-16。**本目录已实际完成{6*len(ARMS)}个新适配器训练、48个历史强比较复用，共{len(allrows)}项补全评价，三种子全保留。** 主模型仍为旧SimKGC双塔+有向邻域/注意力/门/null/有界残差，没有新GNN层、重新抽取、文本模型替换或正式图改写。

## 1. 结论

{decision}

历史213/18项测试已经公开，本轮只作冻结任务的受控历史比较，不能改称新独立测试。机制probe也不是事实Gold：其查询不进入新的门训练，但旧底座可能见过原基础标签。最后检查点只报告机制，不选择其测试好看值。

## 2. 定义与梯度

完整公式、监督来源与梯度推导见[METHOD.md](METHOD.md)，执行前约束见[PROTOCOL.md](PROTOCOL.md)。N+须同时有来源合同的有向角色依据、同文档设备/范围相容、不是目标副本，并在训练标签上冻结干预显示正贡献；不是简单共现。N-来自真实来源对象/行/合法关系扰动，始终是代理负例。

原L_KGC保留。Lscore比较相同背景中正/负上下文的实际目标margin；Labs从原MLP logit作0.8/0.2平滑BCE，提供饱和状态下不消失的恢复梯度。主模型仅更新545个门参数，非门参数固定；joint处理检验补偿。对照只让指定slot收到对照梯度，背景门stop-gradient，主KGC仍更新所有可用候选门。

这不是新BCE或新margin公式：研究增量候选是来源角色约束、边际干预监督和补偿路径隔离的完整协议，必须优于简单损失和公开强模型才有实质支持。GraphMask、CFLP、LAN、S²DN和类型自监督降噪已有相邻机制，不能凭“反事实/对照”命名宣称首创。

## 3. 实际候选未使用原因

| 场景 | 无监督锚点邻接 | 全部关联被来源/事实排除 | 仅16邻居截断 | 已使用 | Schema非法 |
| --- | --- | --- | --- | --- | --- |
'''
    for dataset in ['cold','structured']:
        c=read(NEW/dataset/'data/candidate_exposure_summary.json')['counts']
        lines+=f"| {dataset} | {c['not_incident_to_supervised_anchors']} | {c['all_incident_queries_excluded_by_copy_or_source']} | {c['max16_truncation_only']} | {c['used']} | {c['schema_illegal']} |\n"
    lines+='''
主因互斥；次要排除次数可重叠，逐条见candidate_exposure_ledger。合法但未采样从未称为语义错误，除Schema外本邻域没有隐含语义质量拒绝。本轮不改变邻接/16上限，因此不能声称仅换损失就让未邻接边参与了表示学习；文本/实体向量也保持冻结。

## 4. 角色样本、条件可辨识性与规模

初始冷场景420条构造记录去重为392，结构场景350去重为332；若本目录为clean_v2，还移除了端点疑似同义答案副本，原始与去歧义后的账本均保留。多数是同文档来源对象替换，少量关系/方向/真实表格行替换；不是数百项经专家确认错误。严格正贡献/负贡献筛选后的本目录实际训练对数：

| 场景 | seed | 强fit对 | 强probe对 | 全部被评分角色对 |
| --- | --- | --- | --- | --- |
'''
    for u in utility:lines+=f"| {u['dataset']} | {u['seed']} | {u['strong_fit']} | {u['strong_probe']} | {u['scored']} |\n"
    lines+='''
所有未通过方向筛选的记录保留，不把它们叫真实错误。筛选由各seed冻结旧模型执行，种子差异包括代理监督差异。probe很小，应读样本数而非仅看比例。

纯条件/型号归属交换若不改变15维门输入，输出必相同。冷/结构各132/113条此类不可辨识记录单列，不强行制造相反标签。当前主体没有条件拥有者/行列ID的具体输入，只靠损失无法学会这些绑定。即便对象/关系扰动可以区分，也不证明已学习所有条件或表格分支。

## 5. 强比较与新处理实际补全结果

'''+mt(['simkgc_G1','simkgc_G2','simkgc_G3','simkgc_filter','collab_lan','collab_no_dynamic','collab_no_neighbor','collab_full','role_gate_kgc','role_full'])+'''

指标为相同2150实体/15关系目录上的精确ID过滤排名，容差1e-8平均并列rank，非事实准确率。新模型用原验证link MRR选择，包含epoch0，未用测试/机制probe挑选。

## 6. 学习目标与补偿路径消融

'''+mt(['role_gate_kgc','role_joint_kgc','role_margin_only','role_absolute_only','role_full','role_joint_full','role_shuffled','role_relative_only'])+'''

gate_kgc与joint_kgc同起点/最大预算，只用KGC；所有组仍计算相同对照前向。margin_only无绝对门锚定；absolute_only无功能margin项；joint_full解冻补偿路径；shuffled破坏来源/贡献方向；relative_only替换为偏置不敏感的相对logit目标。clean_v2仅重跑四个核心处理，未在本表出现的处理属于首轮探索，不混合为同数据比较。实际早停轮数/成本在all_evaluations表，不假称实际更新次数完全一样。

## 7. 门是否真的学会辨别

'''+ '\n'.join(probe_lines)+'''

best用于主比较，last_diagnostic只用于解释训练。饱和率下降本身不等于可靠性学习成功，也不能把未被验证选择的末轮当性能结果。完整probe_all与强fit/probe的logit顺序、实际贡献顺序、门均值均保留。只在教师已偏好的强子集变好，也可能是蒸馏教师偏好；未筛选角色probe更能显示局限，但仍非专家评价。

## 8. 配对不确定性

| 场景 | full相对 | 查询平均MRR差 | 事实组95%区间 | 三seed差 |
| --- | --- | --- | --- | --- |
'''
    for c in compared:lines+=f"| {c['dataset']} | {c['control']} | {c['query_weighted_delta']:+.6f} | [{c['CI95'][0]:+.6f}, {c['CI95'][1]:+.6f}] | {','.join(f'{x:+.5f}' for x in c['seed_deltas'])} |\n"
    lines+='''
区间对应事实组宏平均差，查询平均差权重不同；2000次固定拆分组bootstrap，先合并同事实组头/尾和种子，不把重复种子当独立样本。多个探索比较未校正，不构成真实事实/新文档泛化证书。结构任务仅18测试项、严格双端基础邻域支持6项，不能扩大解释。

## 9. 如何回答五个研究问题

区分贡献须同时看未用于新门拟合的probe顺序、自然候选门和补全表现；避免全放行须在被验证选择的模型成立，不能只看last；更多候选正向作用须有覆盖和任务收益，不能拿更大候选池替代；是否稳定超过强基线见全部种子与区间；创新性则还需超越简单BCE/排序/公开方法，单加损失不够。本轮不把未达标处写成已解决。

所有对照主体、配置、原始分数、探针及逐候选账本已保存。不得把冻结教师的正/负utility称为物理因果效应或事实真假。当前机制有训练集教师偏好、少量角色原型和不可辨识输入的明确边界。

## 10. 复现和保全

见[REPRODUCE.md](REPRODUCE.md)。本轮不调用外部大模型、不要求人工、不修改正式图谱或RP2/RP3。之前两轮封存资产需逐哈希核验。utility最初基础别名索引越界的错误日志保留，修正为完整上下文目录后才拟合；没有覆盖任何旧模型或参考标签。
'''
    save(NEW/'REPORT.md',lines);save(NEW/'decision.json',dict(stable_against_all_main_comparisons=stable,conclusion=decision,new_architecture=False,expert_Gold=False))
    figdir=NEW/'figures';figdir.mkdir(exist_ok=True);fig,axes=plt.subplots(1,2,figsize=(12,4))
    methods=['simkgc_G2','simkgc_filter','collab_lan','collab_full','role_gate_kgc','role_absolute_only','role_full']
    for ax,dataset in zip(axes,['cold','structured']):
        rr=[lookup[dataset,m] for m in methods];ax.bar(['G2','Filter','LAN','Old full','KGC only','Gate BCE','New full'],[r['MRR'] for r in rr],yerr=[r['MRR_sd'] for r in rr],capsize=3)
        ax.set(title=dataset+' historical-task recovery',ylabel='Exact-ID link MRR');ax.set_ylim(bottom=0);ax.tick_params(axis='x',rotation=25);ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(figdir/'main_comparisons.png',dpi=170);fig.savefig(figdir/'main_comparisons.svg');plt.close(fig)
    print(decision,flush=True)


if __name__=='__main__':main()
