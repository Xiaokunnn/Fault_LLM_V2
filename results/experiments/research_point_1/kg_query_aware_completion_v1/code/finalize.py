"""Final corrected primary view; original results and documents archived intact."""
from collections import defaultdict
import csv
import shutil
import time
import numpy as np
import torch
from io_utils import *
from query_model import Context,Residual,VARIANTS
from native_role_correction import COR,NativeContext
from eval_core import Evaluator


def main():
    if (EXP/'verification/final_complete.json').exists():print('REUSE completed study');return
    deadline=time.monotonic()+3600
    while not (COR/'complete.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Field correction incomplete')
        time.sleep(2)
    torch.set_num_threads(2);cat=read(EXP/'data/catalogue.json');lookup={};allrows=[];ranks={};cost=[]
    methods=['simkgc_G1','simkgc_G2','simkgc_filter','collab_lan','collab_full','fixed_R1','fixed_R2','fixed_R3','transport_R3','knn_train_log','knn_candidates_log']+['query_'+v for v in VARIANTS]
    for method in methods:
        rr=[]
        actual='native_'+method if method.startswith('query_') and method!='query_no_evidence' else method
        for seed in SEEDS:
            folder=f'{actual}_s{seed}';m=read(EXP/'evaluation'/folder/'metrics.json');c=read(EXP/'models'/folder/'complete.json')
            r=dict(method=method,actual_model=actual,seed=seed,MRR=m['link_MRR'],Hits1=(m['head']['all']['Hits1']+m['tail']['all']['Hits1'])/2,Hits10=(m['head']['all']['Hits10']+m['tail']['all']['Hits10'])/2,head_MRR=m['head']['all']['MRR'],tail_MRR=m['tail']['all']['MRR'],relation_MRR=m['relation']['all']['MRR'],type_legal=1-(m['head']['top1_schema_violation_rate']+m['tail']['top1_schema_violation_rate'])/2,relation_type_legal=1-m['relation']['top1_schema_violation_rate'],validation_MRR=c['validation_link_MRR'],source=str(EXP/'evaluation'/folder))
            rr.append(r);allrows.append(r);ranks[method,seed]=read(EXP/'evaluation'/folder/'rankings.jsonl')
        d=dict(method=method,actual_model=actual)
        for k in ['MRR','Hits1','Hits10','head_MRR','tail_MRR','relation_MRR','type_legal','relation_type_legal','validation_MRR']:
            d[k]=float(np.mean([r[k] for r in rr]));d[k+'_sd']=float(np.std([r[k] for r in rr]))
        lookup[method]=d
    csvsave('native_role_correction/ALL_PRIMARY_SEEDS.csv',allrows)
    baseline=[m for m in methods if not m.startswith('query_')]+['query_full']
    ablations=['query_'+v for v in VARIANTS]+['fixed_R3','transport_R3']
    csvsave('native_role_correction/BASELINE_RESULTS.csv',[lookup[m] for m in baseline]);csvsave('native_role_correction/ABLATION_RESULTS.csv',[lookup[m] for m in ablations])
    groups={x['claim_id']:x['group_id'] for x in read(EXP/'data/base_split.jsonl')};comp=[]
    for method in ['query_full','transport_R3']:
        for control in ['simkgc_G1','simkgc_G2','simkgc_filter','collab_lan','collab_full','fixed_R3','transport_R3','query_no_retrieval','query_no_relation','query_no_structure','query_no_evidence','query_conservative']:
            if method==control:continue
            by=defaultdict(list);dd=[]
            for seed in SEEDS:
                b={(x['id'],x['task']):x for x in ranks[control,seed]};vals=[]
                for x in ranks[method,seed]:
                    if x['task']=='relation':continue
                    v=1/x['rank']-1/b[x['id'],x['task']]['rank'];by[groups[x['id']]].append(v);vals.append(v)
                dd.append(float(np.mean(vals)))
            values=np.array([np.mean(v) for v in by.values()]);rng=np.random.default_rng(SEEDS[0]);boot=[float(np.mean(rng.choice(values,len(values)))) for _ in range(2000)]
            comp.append(dict(method=method,control=control,delta=float(np.mean(dd)),group_macro=float(np.mean(values)),CI95=[float(v) for v in np.quantile(boot,[.025,.975])],seed_deltas=dd,groups=len(values)))
    save(COR/'paired_comparisons.json',comp)
    # Prove the reused no-evidence branch is exactly unaffected, on train-safe
    # finite catalogue queries. No loss/reliability-target edits are involved.
    old=Context(SEEDS[0]);new=NativeContext(SEEDS[0]);keys=[(i,i%30) for i in range(30)]
    for variant in ['no_evidence']:
        a=old.values([k[0] for k in keys],[k[1] for k in keys],variant);b=new.values([k[0] for k in keys],[k[1] for k in keys],variant)
        assert all(torch.equal(x,y) for x,y in zip(a,b))
    del old,new;torch.cuda.empty_cache()
    for name,sha in read(EXP/'verification/test_release.json')['code'].items():assert file_sha(EXP/'code'/name)==sha,name
    for path,sha in read(EXP/'data/freeze.json')['files'].items():assert file_sha(EXP/path)==sha,path
    for path,sha in read(EXP/'data/freeze.json')['inputs'].items():assert file_sha(ROOT/path)==sha,path
    targets=read(EXP/'audit_only/test_targets.jsonl');idx={tuple(x['triple']):i for i,x in enumerate(targets)};ev=Evaluator(targets,read(EXP/'audit_only/test_truth.json'),cat,list(range(cat['nbase'])))
    replays=[]
    for variant in ['full','no_relation','no_structure']:
        path=EXP/'evaluation'/f'native_query_{variant}_s{SEEDS[0]}';z=np.load(path/'scores.npz')
        def p(h,r,t,task):return z[task][idx[h,r,t]]
        m,rows=ev.score(p);saved=read(path/'rankings.jsonl');assert [(x['rank'],x['ties']) for x in rows]==[(x['rank'],x['ties']) for x in saved];replays.append(dict(variant=variant,MRR=m['link_MRR'],exact=True))
    for seed in SEEDS:
        for variant in VARIANTS:
            if variant=='no_evidence':continue
            folder=EXP/'models'/f'native_query_{variant}_s{seed}';c=read(folder/'complete.json');cfg=read(folder/'config.json');original=read(EXP/'models'/f'query_{variant}_s{seed}'/'config.json')
            assert all(cfg[k]==v for k,v in original.items());assert file_sha(folder/'best.pt')==c['checkpoint_sha256']
            cost.append(dict(model=folder.name,seconds=c['seconds'],peak_bytes=c['peak_cuda_bytes']))
    save(COR/'verification.json',dict(passed=True,original_main_code_unchanged=True,data_inputs_and_retrieval_preserved=True,identical_no_evidence_features=True,replays=replays,new_models=21,reused_matched_controls=3,hyperparameters_identical=True,new_independence_claim=False))
    save(COR/'additional_cost.json',dict(models=21,fit_worker_seconds=sum(x['seconds'] for x in cost),max_peak_bytes=max(x['peak_bytes'] for x in cost),per_model=cost))
    def table(names):
        out=['| 方法 | MRR±seed SD | Hits@1 | Hits@10 | 关系MRR | 类型合法率 |','| --- | --- | --- | --- | --- | --- |']
        for name in names:
            v=lookup[name];out.append(f"| {name} | {v['MRR']:.6f}±{v['MRR_sd']:.6f} | {v['Hits1']:.6f} | {v['Hits10']:.6f} | {v['relation_MRR']:.6f} | {v['type_legal']:.6f} |")
        return '\n'.join(out)
    initial=EXP/'analysis/initial_document_archive';initial.mkdir(exist_ok=True,parents=True)
    for name in ['FINAL_REPORT.md','README.md','METHOD.md','FEATURE_ANALYSIS.md','delivery_complete.json']:
        dst=initial/name
        if not dst.exists():shutil.copy2(EXP/name,dst)
    role=read(COR/'feature_freeze.json');probe=read(COR/'probe_complete.json');c0=read(EXP/'analysis/cost_summary.json');enh=read(EXP/'enhancement/complete.json');a=lookup['query_full'];simple=lookup['transport_R3'];pc=[c for c in comp if c['method']=='transport_R3' and c['control'] in ['simkgc_G1','simkgc_G2','simkgc_filter','collab_lan','collab_full']]
    document=f'''# RP1查询感知候选检索与关系补全：最终实测报告

2026-11-16。**有正向对照支持的结果来自简单检索＋有向端点迁移；小型神经协同原型没有证明额外收益。尚不足认定稳定优于全部强基线或形成原创核心算法。**

本轮已完成编码与实际实验。主神经结果采用原生role字段修正后的计算；初版报告完整保留在analysis/initial_document_archive/，原始分数、模型和CSV均未覆盖。

## 1. 数据与执行

只用锁定对象`{I.REV}`的expanded1456（1456 Assertions/1400 Claims/2150实体）、原始8007行/规范化8003候选与15构建手册。未引入其他图谱、MP008或外部文档。二者行数差异不是已证实错误数。

新内部划分989训练、187验证、224测试（160测试事实组），固定hash分组后未重划。留出别名对、逆向/不同关系副本、225来源页、原生单元和20字符证据重叠在索引前排除；训练上下文另作查询自身事实/来源屏蔽。候选索引4660条=989基础训练事实＋3671额外合法候选，双向9320视图、7177上下文实体；答案目录始终2150。

新底座从预训练开始，没有沿用见过新留出目标的旧微调权重。这里是反复研究语料上的版本化内部验证，不是专家Gold、外部测试或真实事实准确率。

初版39个训练（9文本底座＋6旧结构＋24小适配器），字段修正仅增加21个受影响小适配器，去证据控制3个复用并验证特征完全相同；合计60个真实训练。保存93套评分：57套修正后主比较，21套初版受影响结果、6套原概率数值诊断、9套事后固定迁移诊断。后36套不是额外独立验证。

## 2. 实现遗漏及修正边界

源记录使用`evidence_units.role`，初版误读`column_role`，漏序列化该字段并将其存在标记置零。这是实现问题，不是仓库没有角色数据。4703次单元出现中376次角色非unclassified，去重后114单元；修正覆盖220条索引关系/440有向视图。其余多数角色仍未知，条件列表内的fault/cause/remedy角色原已保留，不能混为同一统计。

保留初版，另建native_role_correction语义向量覆盖层；不改变划分、候选池、R0—R3检索、文本底座、模型结构、KGC损失、超参数及早停。全部受影响种子先按同一验证MRR选择并封存，后评分。因初版测试已曝光，修正不能冒称新的独立测试；它是机械字段修复后的受控复算。

修正后175对代理可辨识分类仍为89对旧输入已有差异、39对新增可见、47对截断后相同。全来源文档逐一留出，新语义读出AUC={probe['pooled'][0]['AUC']:.6f}、balanced accuracy={probe['pooled'][0]['balanced_accuracy']:.6f}，旧标量为0.599804/0.588571。没有稳定角色辨识收益。代理扰动不是事实错误标签，三个确定性读出种子不算三份独立证据。

## 3. 检索的实际收益与风险

R0使用745条候选，R1=3331、R2=3126、R3=2923。R3额外使用2217条原R0未采样候选；曝光比例20.29%→79.62%，不等于这些知识都正确或有贡献。1978个训练方向查询中1447个在自排除后无R0上下文，R3为其中99.79%提供非空检索。

R1查询角色类型不兼容槽位55.18%，R2/R3按显式类型条件降为0，R3约95.62%槽位同有向关系。但其候选旧语义合同通过比例仅5.85%，原生地址检查约78.47%，这两个自动代理都不是事实准确率。可比较的单一型号签名中约72.84%不相交，不能等同已确认范围错误，也不能忽略跨设备迁移风险。

RETRIEVAL_RESULTS.csv含逐关系覆盖、外部目录实体比例和成本；原始邻接列包含训练事实自身，正确的可用邻接分层见retrieval/eligible_strata_and_mismatches.csv。更多检索不自动更好。

## 4. 修正后的强比较

{table(baseline)}

主表路径：native_role_correction/BASELINE_RESULTS.csv。三种子16112026/27/28全部保留，SD为三seed总体标准差；2150实体全目录过滤排名，平均并列容差1e-8。精确ID主指标及类型检查不是事实/诊断准确率。

SimKGC为作者双塔/compute_logits的本地适配，LAN与kNN为机制适配而非完整作者复现。kNN原概率的数值并列问题单列，主表用log混合概率且alpha=0原余弦返回；没有通过测试改训练或融合网格。

## 5. 消融与机制

{table(ablations)}

严格同修正特征的消融见native_role_correction/ABLATION_RESULTS.csv；no_evidence将全部改变项清零，特征逐张量相同，因此直接复用原控制。不能将初版其他消融与修正主模型混用。

固定迁移公式为u_i=e_b−e_a+e_h，q'=normalize(q+alpha*Σw_i*u_i)，score=q'ᵀe_t。alpha只在验证集从0/.05/.1/.2选择，R3三seed均选.2，未在看到测试后扩大网格。它不是传递因果边，也不是新TransE训练。

事后同公式迁移R0/R1/R2均值0.226283/0.231617/0.234898，R3为0.235458；R3比R2只多0.000559且一seed为负。R3迁移优于同池尾对象固定融合0.228990。主要支持广域检索和有向端点表示，结构附加项及神经融合无强证据。事后诊断明确不是新独立测试。

## 6. 配对不确定性与冷端点

| 固定迁移相对 | 查询平均MRR差 | 事实组宏平均差95%区间 | 三seed差 |
| --- | --- | --- | --- |
'''
    for c in pc:document+=f"| {c['control']} | {c['delta']:+.6f} | [{c['CI95'][0]:+.6f}, {c['CI95'][1]:+.6f}] | {','.join(f'{v:+.6f}' for v in c['seed_deltas'])} |\n"
    document+=f'''
2000次固定事实组配对bootstrap，先合并头/尾与seed；组宏平均区间与查询平均差权重不同，多个探索比较未校正。固定迁移相对G2、LAN、旧Full区间为正，相对纯SimKGC、简单过滤跨零。修正神经模型MRR={a['MRR']:.6f}，固定迁移={simple['MRR']:.6f}；完整配对比较见native_role_correction/paired_comparisons.json。

224测试中147双冷、72单冷、5温端点；两端基础邻域支持5、候选辅助3、双端基础度≥2仅1项（后者可重叠）。冷是实体ID训练度为0，名称或别名仍可见；不是完全陌生自然语言。不能用该测试宣称丰富结构场景已获验证；初版分层保留，修正后的逐层指标见native_role_correction/stratified_results.csv。

## 7. 增强输出与失败实例

应用方法在初版和修正主比较中均为预定家族中平均验证MRR最高的固定迁移，使用首seed，不按测试选种子。完成8776个允许头/关系查询，保存150条未发布推断：有限别名闭包下149条未匹配基础/初始池，1条初始池已有；前者可能含近义重复。

131条无局部字面匹配、18条共现、1条原候选匹配，不直接等于真假。仅3条有未见页且不重叠引文命中，也不代表独立来源语义确认。AI回读揭示：端盖O型圈疑似别名重复；接头检查缺试验范围；过载→电机过载是重述风险；功能故障evolves_to故障模式不受原定义支持；冷却报警段落属于变流器冷却，缺设备条件。没有已确认并发布的新事实。

ENHANCEMENT_CASES.jsonl保留分数、排名、来源、上下文及新颖性；ENHANCEMENT_REVIEW.md是AI定性解释，不是随机准确率或专家Gold。ERROR_ANALYSIS.md与初版自动标签排名案例保留，修正后神经变化案例另存native_role_correction/error_cases.jsonl，不根据个例重新训练。

## 8. 成本、保全与复现

初版39训练worker时间{c0['summed_fit_worker_seconds']:.2f}秒；21个字段修正小适配器另用{sum(x['seconds'] for x in cost):.2f}秒。并行worker之和不是墙钟，固定融合没有训练参数。神经残差132544参数；旧LAN/Full100962参数；文本底座成本单列，不声称等FLOPs。

预加载目录查询：R3检索约0.790ms；缓存检索后的固定迁移融合/2150评分约1.107ms，初版神经约1.183ms。两段分测，不当端到端/边缘测量，不含新文本编码、启动和磁盘加载。原成本及补充成本均保存。

7项原协议测试通过；旧四轮封存清单、域输入、15PDF、原数据/主评分代码及分数重放通过；字段修正又验证同超参、无证据控制完全一致和三组分数精确重放。正式图谱、RP2/RP3、原响应和历史模型未修改。复现见REPRODUCE.md，保全见verification/及native_role_correction/verification.json。

## 9. 最终五个回答

1. **候选利用程度：** 计算曝光显著增加，且简单迁移相对G2有内部恢复收益；不把全部曝光叫有效事实。
2. **关系理解与预测：** Link排名部分改善；关系类型MRR和条件辨识未一致改善，不能称语义理解问题解决。
3. **全部强基线：** 尚未稳定超过纯文本、过滤、LAN、Full全部方法；神经原型没有额外收益。
4. **可解释机制：** 广域检索＋有向端点迁移有对照依据；更多候选、结构加项和神经模块本身不自动有效。
5. **核心创新价值：** 已形成可复现、有正向证据的简化强基线，但检索、向量差、低秩残差与记忆插值已有先例，当前不足认定原创核心算法成立。保留简单方法，不强行包装复杂模型，不退回任务排名或抽取门控修补。

METHOD.md给出代码一致公式和伪代码；RELATED_WORK.md核对公开机制；所有初版、机械修正和事后诊断身份均明确。
'''
    # Descriptive strata and error deltas for the corrected primary models.
    tags=read(EXP/'analysis/test_strata.json')['per_fact'];sr=[]
    for method in methods:
        for tag in sorted({t for vv in tags.values() for t in vv}):
            values=[];nn=0
            for seed in SEEDS:
                rr=[1/r['rank'] for r in ranks[method,seed] if r['task']!='relation' and tag in tags[r['id']]];values.append(float(np.mean(rr)));nn=len(rr)//2
            sr.append(dict(method=method,stratum=tag,facts=nn,MRR=float(np.mean(values)),MRR_sd=float(np.std(values))))
    csvsave('native_role_correction/stratified_results.csv',sr)
    ref={(r['id'],r['task']):r for r in ranks['simkgc_G2',SEEDS[0]]};errors=[]
    for r in ranks['query_full',SEEDS[0]]:
        if r['task']=='relation':continue
        delta=1/r['rank']-1/ref[r['id'],r['task']]['rank']
        if delta:errors.append(dict(r,delta_rr=delta,baseline_rank=ref[r['id'],r['task']]['rank']))
    save(COR/'error_cases.jsonl',sorted(errors,key=lambda x:x['delta_rr']))
    save(EXP/'FINAL_REPORT.md',document,replace=True)
    save(EXP/'FEATURE_ANALYSIS.md',f'''# 关系语义可辨识性（字段修正后）

初版错读column_role，真实字段为evidence_units.role。去重114个已分类原生单元、220关系/440有向视图已补入文本与字段标记。47条显式条件和1824行组等原盘点不变。初版完整文档在analysis/initial_document_archive/，初版输出没有覆盖。

175对的可辨识分类：{canonical(probe['observability'])}。留一来源文档读出AUC={probe['pooled'][0]['AUC']:.6f}、balanced accuracy={probe['pooled'][0]['balanced_accuracy']:.6f}；旧标量0.599804/0.588571。补入真实role仍未改善代理辨识。47对被192词元截断抹平；字段有值不是语义理解，模型没有用户工况输入。

原四条固定probe样本不足，完整留文档结果与每fold样本在native_role_correction/proxy_lodo_results.csv。扰动仅代理，分类器不参与KGC训练；相同确定性三种子不是三份独立证据。原文缺失、跨设备适用、长片段截断和多语言编码均为限制。
''',replace=True)
    method=(initial/'METHOD.md').read_text().replace('当前没有可靠列角色标记。','原生角色实际存于evidence_units.role；初版遗漏，已用独立覆盖层修正220关系，未知角色仍显式保留。')
    method+='\n\n字段修正只更新native_role_correction/vectors.pt中的语义与存在标记，检索、上下文池、答案目录、模型和目标均不变。受影响21个小适配器完整重跑，3个no_evidence控制经特征逐张量一致性验证复用；修正任务已经曝光，不冒称独立测试。\n'
    save(EXP/'METHOD.md',method,replace=True)
    save(EXP/'README.md','''# 查询感知候选检索与关系补全

已完成代码与实测。当前主结果见[FINAL_REPORT.md](FINAL_REPORT.md)，主强比较/消融表在native_role_correction/；根目录初版CSV及初版模型全部保留。60个实际训练、3种子、93套保存分数，包含字段修正与明确披露的诊断，不能当93次独立验证。

简单有向端点迁移取得部分基线的正向内部证据，新神经原型未证明额外收益。150条增强候选未发布为事实。定义、数据屏蔽、相关工作、复现分别见METHOD.md、DATA_PROTOCOL.md、RELATED_WORK.md、REPRODUCE.md。
''',replace=True)
    save(EXP/'delivery_complete.json',dict(trained_models=60,initial_models=39,field_corrected_small_models=21,reused_exact_no_evidence_controls=3,saved_score_sets=93,primary_score_sets=57,seeds=SEEDS,original_protocol_tests=7,all_strong_baselines_stably_beaten=False,confirmed_new_facts=0,formal_graph_changes=0,RP2_RP3_changes=0,internal_only=True,feature_field_correction_disclosed=True),replace=True)
    save(EXP/'verification/final_complete.json',dict(passed=True,source_field_corrected=True,primary_tables='native_role_correction/',raw_experiments_untouched=True,original_documents_archived=True))
    print('FINAL CORRECTED',lookup['query_full'],'simple',simple,flush=True)


if __name__=='__main__':main()
