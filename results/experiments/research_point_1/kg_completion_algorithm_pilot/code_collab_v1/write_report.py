"""Completed numerical report; no prospective or selectively chosen model rows."""
import csv
import io
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collab_io import *


def main():
    groups=read(STUDY/'tables/grouped_metrics.json');paired=read(STUDY/'tables/paired_comparisons.json')
    lookup={(r['dataset'],r['variant']):r for r in groups}
    def metric_table(variants):
        lines=['| 场景 | 方法 | MRR均值±SD | Hits@1 | Hits@10 | 首选Schema合法率 |','| --- | --- | --- | --- | --- | --- |']
        for dataset in ['cold','structured']:
            for variant in variants:
                r=lookup[dataset,variant];lines.append(f"| {dataset} | {variant} | {r['link_MRR_mean']:.6f} ± {r['link_MRR_sd']:.6f} | {r['Hits1_mean']:.4f} | {r['Hits10_mean']:.4f} | {r['schema_legal_top1_mean']:.4f} |")
        return '\n'.join(lines)
    main_methods=['simkgc_G1','simkgc_G2','simkgc_G3','simkgc_filter','collab_lan','collab_full']
    ablations=['collab_full','collab_no_dynamic','collab_fixed','collab_no_relation','collab_no_neighbor','collab_no_null']
    scale=['collab_conservative','collab_scale25','collab_scale50','collab_full','collab_noise25','collab_noise50']
    comparison=['| 场景 | full相对对照 | 逐查询差 | 事实组宏平均差 | 组bootstrap 95%区间 | 三种子差 |','| --- | --- | --- | --- | --- | --- |']
    for p in paired:
        comparison.append(f"| {p['dataset']} | {p['contrast']} | {p['query_weighted_delta']:+.6f} | {p['group_macro_delta']:+.6f} | [{p['group_bootstrap_CI95'][0]:+.6f}, {p['group_bootstrap_CI95'][1]:+.6f}] | {', '.join(f'{x:+.5f}' for x in p['seed_deltas'])} |")
    supported=all(p['group_bootstrap_CI95'][0]>0 and min(p['seed_deltas'])>0 for p in paired if p['contrast'] in ['collab_full minus simkgc_G2','collab_full minus collab_lan'])
    decision='主要配对对照在本固定拆分中均出现正向证据，但小样本/旧测试已公开及已有机制重叠仍不允许直接确认独立原创创新。' if supported else '未获得同时稳定优于G2强基线和LAN公开机制的证据，本轮尚不能确认RP1算法创新成立。'
    discovery=read(STUDY/'discovery/summary.json');source_review=read(STUDY/'discovery/source_review_summary.json')
    interventions=list(csv.DictReader((STUDY/'tables/frozen_weight_interventions.csv').open()))
    it=['| 场景 | 冻结full权重后的输入干预 | MRR均值±SD |','| --- | --- | --- |']
    for dataset in ['cold','structured']:
        for variant in ['drop_candidates','drop_all','shuffle_edge_relations']:
            vals=[float(r['MRR']) for r in interventions if r['dataset']==dataset and r['intervention']==variant]
            it.append(f"| {dataset} | {variant} | {np.mean(vals):.6f} ± {np.std(vals):.6f} |")
    figdir=STUDY/'figures';figdir.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    labels=['Sim G1','Sim G2','Sim G3','Simple filter','LAN-Text','Proposed']
    for ax,dataset in zip(axes,['cold','structured']):
        rr=[lookup[dataset,m] for m in main_methods]
        ax.bar(labels,[r['link_MRR_mean'] for r in rr],yerr=[r['link_MRR_sd'] for r in rr],capsize=3)
        ax.tick_params(axis='x',rotation=25);ax.set(title=dataset+' automatic-label recovery',ylabel='Exact-ID filtered link MRR');ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(figdir/'main_baselines.png',dpi=170);fig.savefig(figdir/'main_baselines.svg');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,dataset in zip(axes,['cold','structured']):
        rr=[lookup[dataset,m] for m in ablations]
        ax.bar(['Full','No dynamic','Fixed','No relation','No neighbors','No null'],[r['link_MRR_mean'] for r in rr],yerr=[r['link_MRR_sd'] for r in rr],capsize=3)
        ax.tick_params(axis='x',rotation=25);ax.set(title=dataset,ylabel='Link MRR');ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(figdir/'ablations.png',dpi=170);fig.savefig(figdir/'ablations.svg');plt.close(fig)
    report=f'''# RP1关系感知可信候选协同补全：算法实现与验证报告

日期2026-11-14。**已实际完成15个新SimKGC底座/过滤基线训练、72个轻量适配器、9个旧冷场景基线复用，共96个主模型评价，另18个冻结权重图输入干预。** 领域输入仍为833c804的expanded1456、初始候选及15构建手册；正式图谱、RP2/RP3、历史模型与结果不改写。

## 1. 实证结论

{decision}

实测冷场景full=0.241534，G2=0.240410，LAN=0.242612，纯文本匹配适配器=0.245834；结构场景full=0.126671，G2=0.127641，LAN=0.128260，简单过滤=0.143507。full在冷场景三个种子都低于LAN。完整动态门相对固定门在冷场景差仅+0.000018，无法归因为已学会可靠候选筛选。

本轮不重做增强必要性调查或A—E任务选择。方法实现、公开机制比较、实际训练、三种子消融和新关系推断均已完成；负结果不意味着终止知识增强目标。是否有独立贡献，应由完整对照及可解释失败决定，不能把命名、门值变化或多输出候选当作创新证据。

## 2. 算法与已有工作的边界

详细计算流程、公式、数值界与伪代码见[METHOD.md](METHOD.md)，公开工作及未运行方法的边界见[RELATED_WORK.md](RELATED_WORK.md)。核心为冻结SimKGC G2上的约10万参数残差适配器：有向关系消息→查询相关注意力→证据特征学习的绝对候选贡献门→零消息null项→有界残差→明确三元组余弦评分。候选门通过基础补全监督学习，不把8000记录全部作为正例，也不是沿用固定状态权重。

已有LAN包含关系共现逻辑与查询注意力，因此实际运行LAN-Text适配对照；它沿用同G2编码器、相同候选池/邻域上限、监督、残差幅度与优化预算。按原公式的逻辑权重+神经权重实现，非弱化成均值，不冒充作者TensorFlow/TransE端到端复现。RAA-KGC作者仓库及模型代码已核对并保存，但未运行其完整文本锚点训练，不能把本轮向量聚合称作RAA-KGC。CompGCN、RACA、DSC2F、UKGE/FocusE/NAAER均使普通关系聚合、文本结构协同或置信利用缺乏单独首创性。有限候选增量是证据合同特征门及拒绝邻域贡献，仍需独立实证/查新，不能预先宣称原创。

新适配器不编码全文证据，不显式求解设备型号、条件或时序蕴含；仅使用已声明的12维合同/结构特征与端点语义。故不能把它称为已经解决条件治理或语义角色验证。

## 3. 两套冻结任务与防泄漏

冷场景完整保留上轮939训练/198验证/213测试及2150实体/15关系答案集合，复用G1/G2/G3共9个旧模型与真实分数。该旧测试已公开，不能重新称为未见。新结构样本只从旧训练事实组选择，经整组/同义反向对/重复候选/原生单元/证据20gram及同源页候选排除后，两端仍有合法上下文邻边：911训练、10验证、18测试，原461项保留评价不转入训练。测试中6项有双端基础邻域，12项依赖不确定候选邻域；验证对应2/8项。

这些数字表示非孤立结构可用性，不证明存在能推出目标的逻辑路径。新结构目标之前曾是旧训练标签，故**新结构编码器全部从原始预训练BGE微调，不加载旧微调权重**。名称仍是共享闭合目录，预训练语料记忆未知；新任务不是独立现场/人工事实测试。18项尤其基础支持仅6项，统计能力有限，不扩大样本解释。

训练适配器的每个查询输入进一步排除自身整证据组、别名端点对和同来源页候选，防止邻域直接回填目标。验证/测试全局遮蔽在模型拟合前完成；模型输入仅锚点和关系，不看答案或测试来源。测试模型统一精确ID过滤，容差1e-8并列平均rank，另保留别名过滤敏感性；程序标签恢复不等于事实准确率。主排名不提前按类型缩小答案目录，另报首选Domain/Range合法性。

完整数据、候选上下文、条件和哈希在各场景`data/`，新结构选择及原始出处在`audit_only/`。MP008及外部文档未参与，MP022仍不进入训练上下文。

## 4. 训练预算与强基线

神经种子固定14112026/27/28。新SimKGC基线沿用原作者模型适配、batch32、lr2e-5、最多10轮、patience3；简单过滤仅保留Schema合法且证据位置有效的候选，并按原候选辅助训练流程训练。新结构重跑G1/G2/G3/过滤，旧冷场景只新增过滤模型。

适配器统一hidden64、最多16邻居、AdamW lr0.001、batch128、最多60轮、每5轮验证、patience15，epoch0共同候选；文本编码器冻结。所有适配器同一G2特征、基础正/逆监督、相同采样和名义参数量，只有声明的机制/候选控制变化。no_neighbor是同名义容量的纯文本残差，不等同完全没有参数的原SimKGC。被消融掉的模块参数仍保存在state，但不从损失接收梯度；不能把名义参数相同解释为有效容量完全相同。

底座全参数训练与适配器训练并非同FLOPs；公平机制归因以LAN及各匹配适配器为主，原始强底座同时保留。编码缓存、所有checkpoint最佳epoch、成本/参数、OOM与恢复记录均留存，不选最优种子。

## 5. 六类强基线与提出方法

{metric_table(main_methods)}

![三种子主比较](figures/main_baselines.png)

完整96行及每条件三种子标准差见`tables/all96_models.csv`和`grouped_metrics.csv`。关系类型MRR也保存，但上轮Schema+频次参考已高达0.948，因此不能单凭类型分数宣称新关系理解；本轮主要检验完整实体补全和结构使用。

## 6. 机制消融

{metric_table(ablations)}

![消融](figures/ablations.png)

no_dynamic置候选g=1；fixed恢复原经验权重；no_relation只移除聚合器中的关系类型条件，保留边方向和文本底座的关系编码；no_neighbor去掉邻域但保留纯文本残差；no_null移除零消息竞争项。三种子及事实组差值如下，不能只取某个单种子或略去劣化条件。

{chr(10).join(comparison)}

区间为固定拆分上2000次事实组bootstrap；先合并同组的头/尾和三个种子，不把重复种子当独立事实样本。逐查询差与组宏平均差的权重不同，区间对应后者。未校正多重探索比较，不构成正式事实风险或跨手册泛化证书。

## 7. 候选数量、质量和合成噪声

{metric_table(scale)}

所有组共用G2底座；因此conservative与full对比检验的是额外不确定邻域信息，而非多训练一批保守标签。25%/50%是固定散列保留概率、非精确数量。full仍只对合法可追溯候选传消息，原8003记录去副本及遮蔽后才形成上下文池；每查询最多16邻居，不能把8003写为每次参与推断的事实数。

noise25/noise50对候选尾实体作固定类型相容替换，避开已知边和所有留出别名端点对，证据特征保持原样，合成标记不输入模型。开放世界下不保证替换全是真负例；这是可控扰动代理，不是原候选真实错误率。实际候选/扰动数见每模型config与all96表。

## 8. 模型究竟是否使用了图结构

同一full参数作输入干预，完全不训练或重选epoch：

{chr(10).join(it)}

drop_all逐向量在浮点容差内校验回到原G2文本表示；drop_candidates只删候选消息，仍保留基础邻域；shuffle只打乱邻边关系类型且保留方向/实体/度。与正常full比较可显示结构输入的影响，但“有影响”不是“有益”。相同检查点删除邻域后若更好，即存在负迁移。门值随查询变化也只证明可观测性，不能自动证明可靠性学习。

`tables/contribution_diagnostics.csv`保留候选实际曝光率、null质量、残差范数、门均值/方差、跨关系变化以及选择检查点的trust参数相对初值变化；选择epoch0的组不称“学习可信性已有效”。结构6/12项分开结果在`structured_support_subgroups.csv`，不把候选辅助支持与基础支持混算。

## 9. 潜在关系与源文核查

`discovery/predictions.jsonl`用完整提出方法的固定第一种子预测，未按测试挑最优模型。每条有明确三元组、余弦分数、查询排名、相对同G2底座的分数变化、基础/候选邻边来源、门权、null和新颖性分类。已见基础事实、初始候选已出现、两池外组合严格区分；反向观测作保守已知处理，不将候选再输出算新发现。

源文包固定从留出MP022匹配，优先显示分数确有变化的高排名两池外关系。核验另见`discovery/SOURCE_REVIEW.md`和逐例JSONL。模型分数不称概率，非命中不证明事实为假；源文支持亦不等于独立专家Gold。原文明示/需条件/角色不支持/无法验证分别保存，不回写正式图。

实际输出{discovery['predictions']}条typed top3提议：基础已知{discovery['novelty']['base_known']}、初始池已知{discovery['novelty']['initial_pool_known']}、两池外组合{discovery['novelty']['beyond_both']}。这不是新增正确知识数。12例实际源文AI阅读为E8/U4，没有确认新完整事实；其中10例分数相比G2下降，2例上升，不能将全部不支持项归为新算法引入错误。18条提议的两端完全同名，已作为可能退化/类型粒度问题另列，不删除难例或把自动相同名称当专家同义真值。

## 10. 失败定位与下一次有依据的算法修改

当前任务仍是关系增强算法，不退回必要性排名。若full不能稳定超过G2、LAN或no_dynamic，说明单靠补全损失未充分辨别“有用候选”与“相似但错误角色的候选”；注意力与sigmoid门存在共同缩放/重参数化，可能学成容量补偿。若结构支持场景有作用而冷场景无作用，则同时受到覆盖限制：无邻居时本模型设计上精确退回底座，不能改善孤立端点。

已有直接观测使失败定位比上述假设更明确：冷场景仅29.39%训练查询有任何邻域、23.11%有候选邻域，4318个合法候选仅824个被训练查询实际使用；结构场景训练对应26.56%/21.30%，4200个候选仅734个实际使用。后者测试虽100%非孤立，仍未胜出，因此不能只归咎冷启动。选择检查点的候选门在冷场景均值0.897—0.999、结构场景0.9986—0.9996，接近全部打开；结构场景null质量仅0.0021—0.0095。门确实发生参数更新，但并没有形成可靠的拒绝。完整实证和下一次单机制修改见[FAILURE_MECHANISM.md](FAILURE_MECHANISM.md)。

下一次最小修改应针对上述诊断：在训练集用角色交换/关系替换的上下文干预构造一致性对照，显式监督候选对正确尾相对竞争尾的margin贡献，区分“相关性注意力”和“可靠性”。不把合成扰动当真实错误标签；需要与同预算无门/公开降噪方法比较。若问题主要是冻结语义空间，则应测试有限参数文本适配的匹配控制，而非继续加邻域层数。以上仅为由本轮失败可检验的后续改动，本轮不根据已见测试继续训练或承诺其有效/原创。

## 11. 保全、复现与尚未完成项

复现命令见[REPRODUCE.md](REPRODUCE.md)，机制见[METHOD.md](METHOD.md)，代码在`code_collab_v1/`。技术恢复保留两次OOM日志及4项原未完成文件，修改仅为释放等待进程缓存和统一显存锁；不动服务器原模型。所有已完成模型复用，不将中断重跑计为新种子。测试评分无训练反馈。

本轮限制：旧冷测试已公开，新结构仅18项/单次split，其中严格基础支持6项；代理标签非人工真值；未端到端复现LAN/RAA-KGC；无全文证据蕴含、工况逻辑或候选事实概率校准；三个种子不等于多数据拆分；没有正式图谱增量或RP2/RP3应用收益验证。充分的算法创新仍须面对这些限制，不将数值变化或代码工作量替代方法有效性。
'''
    save(STUDY/'REPORT.md',report)
    save(STUDY/'decision.json',dict(stable_positive_against_G2_and_LAN_in_both_scenarios=supported,assessment=decision,
        no_test_driven_retraining=True,new_algorithm_implemented=True,all_conditions_retained=True,claim_factual_accuracy=False))
    print(decision,flush=True)


if __name__=='__main__':main()
