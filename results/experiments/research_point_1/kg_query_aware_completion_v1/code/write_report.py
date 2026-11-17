"""Final deliverable from frozen actual outputs; no further model changes."""
import csv
import numpy as np
from collections import defaultdict
from io_utils import *


def main():
    summary=read(EXP/'data/summary.json');means={r['method']:r for r in read(EXP/'analysis/grouped_metrics.json')};comparisons=read(EXP/'analysis/paired_comparisons.json')
    costs=read(EXP/'analysis/cost_summary.json');enhance=read(EXP/'enhancement/complete.json');strata=read(EXP/'analysis/test_strata.json')['counts'];check=read(EXP/'verification/checks.json')
    rt=list(csv.DictReader((EXP/'RETRIEVAL_RESULTS.csv').open()));diag=list(csv.DictReader((EXP/'analysis/transport_retrieval_diagnostic.csv').open()));diagnostic=defaultdict(list)
    for r in diag:diagnostic[r['method']].append(float(r['MRR']))
    def table(methods):
        z=['| 方法 | Link MRR ± seed SD | Hits@1 | Hits@10 | 关系MRR | 头尾Top1类型合法率 |','| --- | --- | --- | --- | --- | --- |']
        for m in methods:
            r=means[m];z.append(f"| {m} | {r['MRR']:.6f} ± {r['MRR_sd']:.6f} | {r['Hits1']:.6f} | {r['Hits10']:.6f} | {r['relation_MRR']:.6f} | {r['type_legal']:.6f} |")
        return '\n'.join(z)
    texts=['''# RP1查询感知候选检索与关系补全：完整实测报告

2026-11-16。**本轮形成了一个相对部分强基线有正向证据的简化方法：关系感知检索＋有向端点迁移固定融合；新神经协同原型没有额外收益。尚未证明稳定超过全部强基线，也不确认RP1原创核心算法已经成立。**

以下均为已运行结果，不是实验计划。正式图谱及RP2/RP3未改，无新的抽取或外部大模型API调用。

## 1. 完成范围和数据

''',f'''实际新训练39个模型：9个从预训练开始的SimKGC底座、6个旧LAN/Full结构、24个最小残差与消融。初始57项评价之后，保留概率排名数值诊断，补充6项kNN数值一致性评分和9项固定迁移成分诊断，共72套保存分数；其中6套原概率结果仅作数值附录，不能当额外独立算法试验。三种子16112026/27/28全部保留。

只使用expanded1456、初始候选与15构建手册，域输入Git对象`{I.REV}`。基础1456 Assertions/1400 Claims/2150实体。实际原始行{summary['raw_records']}，规范化候选{summary['normalized_records']}，二者分母不同，不擅自将差额解释成四个语义错误。

新冻结划分989训练、187验证、224测试，共1087事实/证据组；测试有160组。不是新外部文档测试，更不是专家Gold。屏蔽225个留出来源页与目标副本后，5084条去重候选中含Schema非法931条；扣除已有训练事实重复，额外合法上下文3671条。加989基础训练事实形成4660条索引、9320有向视图、7177可见上下文实体，答案目录仍2150。

旧213/18项任务没有用于本轮调参，旧微调权重不进入新划分。旧实验仅用于代码复用与保全核验。

## 2. 查询检索是否扩大了候选参与

| 策略（全量合法池） | 实际使用去重候选 | 非空查询比例 | 目录外端点槽位比例 | 候选原定位合同通过比例 | 候选原语义合同通过比例 |
| --- | --- | --- | --- | --- | --- |
''']
    for r in rt:
        if r['pool']=='all':texts.append(f"| {r['strategy']} | {r['distinct_used_candidates']} | {float(r['nonempty_rate']):.4%} | {float(r['outside_base_endpoint_fraction']):.4%} | {float(r['located_contract_fraction']):.4%} | {float(r['entailed_contract_fraction']):.4%} |\n")
    texts.append('''
R3相对R0另使用2217条原本没被该一跳方法采样的候选，2923/3671=79.62%的可检索额外候选被训练查询曝光，R0为20.29%。这是**计算使用覆盖**，不是被证明有用或正确的知识比例。R1使用数量更多，也不能据此判优。

1978个训练方向查询中，自事实/来源排除后1447个没有可用R0邻域；R2/R3为其中99.79%提供了非空上下文。RETRIEVAL_RESULTS.csv另保留原始邻接列，该列包含训练事实自身，不能用来替代上述可用邻域口径；补充表见retrieval/eligible_strata_and_mismatches.csv。

R1的查询端点角色类型不兼容槽位约55.18%；R2/R3按既定类型条件降为0。R3约95.62%槽位同有向关系，但这只说明结构匹配，不证明语义贡献。可比较的单一训练型号签名中，R3约72.84%候选签名不相交，既提示跨设备迁移风险，也不能直接算已确认范围错误。模型没有目标来源型号作为输入。

候选原生地址检查比例、原门控合同、基础事实占比及逐关系覆盖均保存；没有新人工/大模型相关性Gold。未通过旧语义合同可能包括规则拒绝和真实错误，不能直接当噪声真值。

## 3. 新语义特征是否真正改善辨识

4660条索引关系中，4117有可见证据、47有显式条件、1855有原生位置、1824有行组、明确列角色为0。所有缺失显式标记，没有从报告抄答案补字段。

构造175个来源关系/扰动对：89对旧输入已有对象或方向差异；39对新增绑定文本使输入可区分；47对在192词元截断后依然完全相同。扰动只是代理，不是真实错误事实。

最初固定文档probe仅四条记录，样本不足，完整保留。补充对所有有样本文档逐一留出、同一线性读出器固定C=1：旧标量表示AUC=0.599804、balanced accuracy=0.588571；新绑定文本AUC=0.535037、balanced accuracy=0.531429。三个确定性读出种子结果相同，不是假称三份独立验证。

因此，**新增可观察信息没有转化为稳定的角色/条件辨识能力**。长端点及JSON绑定被截断、冻结中文编码器处理多语言源文未获任务适配、查询只给h/r而缺少运行场景，都是具体局限。不能把字段存在或向量不同说成语义理解已解决。见FEATURE_ANALYSIS.md及feature_analysis/lodo_notes.md。

## 4. 主强比较

'''+table(['simkgc_G1','simkgc_G2','simkgc_filter','collab_lan','collab_full','fixed_R1','fixed_R2','fixed_R3','transport_R3','query_full','knn_train_log','knn_candidates_log'])+'''

2150实体全目录、15关系、相同目标及已知事实过滤；主指标精确ID，1e-8平均并列rank。类型合法率是Schema检查，不是事实准确率。冷端点按基础训练图的实体ID度定义，名称/别名仍可能见过，不是自然语言完全陌生实体。

SimKGC为真实作者模型的既有本地适配；LAN与kNN-KGE为公开机制适配。kNN作者MLM实体模型没有完整复现，不以本地适配失败宣称其论文方法无效。概率分数的小值可能触发绝对并列容差，主表使用修正后的log混合分数，lambda=0时原余弦返回；原概率结果与原因保留，未修改主模型或测试目标。

## 5. 新原型消融

'''+table(['query_full','query_no_retrieval','query_no_relation','query_no_structure','query_no_evidence','query_k8','query_k32','query_conservative','fixed_R3','transport_R3'])+'''

full相对去检索、去显式角色、去结构及去证据有小幅均值优势，但不因此认定各模块有效：配对区间与所有种子见analysis/paired_comparisons.json；full仍低于同池固定迁移。不同候选规模没有单调收益，32条比16条更差；全量合法池优于保守池的均值尚未达到强判据。原始候选不是无条件有效知识。

事后固定迁移诊断只替换检索策略、公式/融合网格不变，不重新训练。该诊断在初始测试曝光后执行，不能改称新独立验证：

| 固定有向迁移 | 三seed MRR均值 | seed SD |
| --- | --- | --- |
''')
    for m,v in sorted(diagnostic.items()):texts.append(f'| {m} | {np.mean(v):.6f} | {np.std(v):.6f} |\n')
    texts.append(f"| transport_R3（原主比较） | {means['transport_R3']['MRR']:.6f} | {means['transport_R3']['MRR_sd']:.6f} |\n")
    texts.append('''
有向迁移R3优于同池只聚合尾对象（0.235458对0.228990），三个种子均正向；R3对R2迁移只多约0.000559且有一seed为负。当前主要证据在**广域相关关系检索＋有向端点迁移**，而不是复杂神经融合或已被证明的图结构推理。

## 6. 配对不确定性与结构分层

| 方法相对基线 | 查询平均MRR差 | 事实组宏平均差95%区间 | 三seed均正向 |
| --- | --- | --- | --- |
''')
    for c in comparisons:
        if (c['method']=='transport_R3' and c['control'] in ['simkgc_G1','simkgc_G2','simkgc_filter','collab_lan','collab_full','fixed_R3']) or (c['method']=='query_full' and c['control'] in ['simkgc_G2','transport_R3']):
            texts.append(f"| {c['method']} / {c['control']} | {c['query_mean_delta']:+.6f} | [{c['CI95'][0]:+.6f}, {c['CI95'][1]:+.6f}] | {c['all_seed_positive']} |\n")
    texts.append(f'''
区间为2000次事实组配对bootstrap，先合并同组头/尾与三个seed，不把重复种子当独立样本。查询平均和事实组宏平均权重不同，区间不是前一列估计量的直接区间。多个探索比较没有多重性校正。固定迁移相对G2、LAN、旧Full有正向区间，但相对纯SimKGC和简单过滤跨零，**不能称稳定超过全部强基线**。

测试结构：both_cold={strata.get('both_cold',0)}、one_cold={strata.get('one_cold',0)}、warm={strata.get('warm',0)}；两端基础邻域支持5项，候选辅助3项，双端基础度≥2仅1项。后两类可能重叠，不能相加。没有两步基础连接类别时如实缺失，未人为补简单样本。该划分主要支持冷端点检索诊断，不足证明结构丰富场景稳定收益。分层逐方法表见analysis/stratified_results.csv。

## 7. 错误和潜在增强应用

验证平均最高的transport_R3用于应用，固定第一个seed；没有用测试最优seed。检查{enhance['query_count']}个Schema允许的头/关系查询，按每头/关系限额保存150条候选推断，而非发布150条知识。

有限别名闭包下149条未在基础图/初始池匹配，1条初始池已有；149条仍可能含近义重复。131条未找到本次字面局部证据，18条局部共现，1条已有候选记录，均不直接等于真假。3条有未见页且未重叠引文命中，不等于独立来源语义确认。

源文AI回读已明确记录：端盖O型圈的两个表述疑似重复；接头目视检查属于试验范围；“过载导致电机过载”不能由Motor overloaded表项支持；“功能故障 evolves_to 故障模式”方向/演化语义无支持；冷却故障报警段落属于半导体变流器冷却，省略设备范围有风险。可定位的新文字支持也不能掩盖条件缺失。没有确认并发布的新事实。

同时保存真实自动目标排名改善（如轴封弹簧维护3→1）和退化（如唇形密封由安装转为检查更换、Schema不符）的案例。详见ERROR_ANALYSIS.md、ENHANCEMENT_CASES.jsonl与ENHANCEMENT_REVIEW.md。AI回读不是专家Gold，不用于训练或事后选择。

## 8. 计算成本、复现和保全

39个真实训练的worker耗时合计{costs['summed_fit_worker_seconds']:.2f}秒，约{costs['summed_fit_worker_seconds']/60:.2f}分钟；部分阶段并行，不能当墙钟。最大PyTorch分配峰值{costs['max_torch_peak_bytes']/2**30:.3f}GiB，历史服务器模型保持运行。新模型检查点约{costs['output_checkpoints_bytes']/2**30:.3f}GiB，索引编码{costs['index_encoding_seconds']:.2f}秒。

预加载目录查询的R3实际单查询检索均值约0.790ms；缓存检索结果后的固定迁移融合＋2150实体评分约1.107ms，神经原型约1.183ms。两段分别测量，不相加冒充端到端；不含新文本编码、启动或磁盘加载，不是边缘设备测量。全部成本和分位数见analysis/runtime_latency.csv与training_costs.csv。

7项协议/实现测试通过；旧四轮封存清单、域输入、15份PDF、主评分前代码哈希、训练检查点及七组分数重放核验通过。原图谱、原始响应、RP2/RP3未变。复现见REPRODUCE.md；源数据、模型与预测哈希见verification/。

## 9. 最终五个问题

1. **是否提高候选有效利用？** 训练曝光显著扩大，R3另用2217条原R0未采样候选；固定迁移对G2有内部恢复收益，但不能将2923条曝光都叫有效知识。
2. **是否提高关系理解与预测？** Link排名部分改善；关系类型MRR没有一致提高，条件/角色代理读出未改善，不能称广义关系语义理解已解决。
3. **是否稳定超过全部强基线？** 没有。简化方法优于部分基线，但相对纯文本和简单过滤的不确定性仍大；新神经原型不胜简化方法。
4. **是否有可解释机制？** 广域检索和有向端点迁移有具体对照依据；结构附加项微弱，语义神经融合没有额外收益。不是“候选越多越好”。
5. **是否足以冻结为RP1核心原创算法？** 当前不足。已形成可复现、有正向内部证据的简单增强基线，保留为后续基准；不能把检索、向量差和低秩层的组合直接宣称原创。该结论不是退回研究方向排名，也不再修补抽取门控。

本阶段交付已完成，负结果和正向组件证据同时保留。若继续改善，依据应来自当前源角色/条件不可辨识和跨设备迁移错误，而非继续加损失或把共现预测直接发布。
''')
    save(EXP/'FINAL_REPORT.md',''.join(texts))
    save(EXP/'README.md','''# RP1 查询感知候选检索与关系补全

2026-11-16，已实际完成39个训练、三种子、主强比较与消融。简化的检索＋有向端点迁移取得部分基线正向内部证据；神经原型未胜简单方法，尚不足认定原创核心算法成立。

先读[FINAL_REPORT.md](FINAL_REPORT.md)。定义见[METHOD.md](METHOD.md)，拆分/屏蔽见[DATA_PROTOCOL.md](DATA_PROTOCOL.md)，强比较与消融见BASELINE_RESULTS.csv / ABLATION_RESULTS.csv，候选覆盖见RETRIEVAL_RESULTS.csv。源码、检查点、原始分数、各轮日志和全部种子均保留；复现见[REPRODUCE.md](REPRODUCE.md)。

150条潜在关系是未发布推断，不是新增正确知识。正式图谱、RP2/RP3和历史结果不变。
''')
    save(EXP/'delivery_complete.json',dict(trained_models=39,saved_evaluations=72,initial_evaluations=57,numeric_supplement=6,posthoc_transport_supplement=9,seeds=SEEDS,unit_tests=7,main_model_gain_established=False,simple_transport_positive_against_G2=True,all_strong_baselines_stably_beaten=False,confirmed_new_facts=0,graph_changes=0,RP2_RP3_changes=0,internal_only=True))
    print('Final report complete; no training or model selection performed.')


if __name__=='__main__':main()
