# Fault LLM v2 当前研究交接

更新日期：2026-09-18

本文件只保留当前状态和继续工作所需入口。此前数百行的阶段性构图日志、旧研究点编号和未完成计划已由两篇小论文终稿、冻结实验与 `docs/archive/` 中的历史文档取代。

研究点三的正式基线定义、最少实验矩阵和分优先级TODO见 `docs/RP3_EXPERIMENT_BASELINES_AND_TODO.md`。

## 当前研究结构

1. 研究点一：无需逐条人工审批的自动证据质量门控与可追溯知识图谱构建。
2. 研究点二：预算约束型向量—图协同证据检索、两阶段支持判别与确定性回答。
3. 研究点三：证据契约保持型决策蒸馏、轻量化与代价敏感边缘推理。

唯一当前总规划：[`research/MASTER_THESIS_THREE_RESEARCH_POINTS_PLAN.md`](research/MASTER_THESIS_THREE_RESEARCH_POINTS_PLAN.md)。

2026-09-17范围调整：连续负结果后暂停当前哈希四头优化链，下一阶段候选方向收窄为
“证据契约约束下的选择性执行与资源自适应边云协同”。这是研究计划调整，不是已验证替代；
见[`research/RP3_SCOPE_REASSESSMENT_20260917.md`](research/RP3_SCOPE_REASSESSMENT_20260917.md)。RP1/RP2冻结不变。

## 研究点一事实入口

- 英文主稿：[`../papers/ICSMD_2026/RP1_ICSMD2026_English_Final.tex`](../papers/ICSMD_2026/RP1_ICSMD2026_English_Final.tex)
- 中文主稿：[`../papers/ICSMD_2026/RP1_ICSMD2026_中文正式稿_v5.tex`](../papers/ICSMD_2026/RP1_ICSMD2026_中文正式稿_v5.tex)
- 论文数字证据包：[`../results/experiments/research_point_1/publication_revision_v2/experiment_evidence_pack_v2.md`](../results/experiments/research_point_1/publication_revision_v2/experiment_evidence_pack_v2.md)

15份构建文档、1934个物理页产生8003条审计记录：1698条自动证据合格、881条隔离、5424条拒绝。标准中文应用层为1326条证据记录、1281项Claim和2022个中文实体；根目录严格层为208条。

方法的成立范围是：自动记录是否满足冻结的结构、页面证据、关系支持、来源和术语发布契约。它不提供专家事实正确率、故障诊断准确率或工程安全保证。

## 研究点二事实入口

- 英文主稿：[`../papers/D2AI_ICDM_2026/RP2_D2AI2026_English_Final_v1.tex`](../papers/D2AI_ICDM_2026/RP2_D2AI2026_English_Final_v1.tex)
- 中文主稿：[`../papers/D2AI_ICDM_2026/RP2_D2AI2026_中文初稿_v6.tex`](../papers/D2AI_ICDM_2026/RP2_D2AI2026_中文初稿_v6.tex)
- v6协议：[`RP2_V6_EQUAL_BUDGET_PROTOCOL.md`](RP2_V6_EQUAL_BUDGET_PROTOCOL.md)
- 冻结清单：[`../configs/frozen/rp2_v6_paper_evidence_freeze.json`](../configs/frozen/rp2_v6_paper_evidence_freeze.json)
- 主结果：[`../results/experiments/research_point_2/graphrag_v6_equal_budget/paper_summary/table_equal_budget_main.md`](../results/experiments/research_point_2/graphrag_v6_equal_budget/paper_summary/table_equal_budget_main.md)
- 去图控制：[`../results/experiments/research_point_2/graphrag_v6_1_no_graph_control/paper_summary/table_equal_budget_main.md`](../results/experiments/research_point_2/graphrag_v6_1_no_graph_control/paper_summary/table_equal_budget_main.md)

研究点二在208条严格中文证据和40条受控查询上冻结。Full K3相对Dense K3提高检索和引用指标，并将平均端到端时延由839.4 ms降至531.2 ms。Full与Full-NoGraph差异很小且不显著，因此图传播只解释为尾部召回补充。

查询的候选故障范围和诊断角色已给定；输出是单角色原子建议，不是完整诊断卡，也不是开放式故障识别。

## 研究点三当前状态

服务器工作目录为 `~/08-zxk/Fault_LLM_V2`。主线代码从 `origin/main` 同步；本轮结果整理在
`codex/rp3-augmented-v1-results`分支，收录代码、协议、可审阅指标、逐行预测及训练/校准清单。
模型、原始响应、特征bundle和日志仍保留服务器。收录范围见
[`RP3结果索引`](../results/experiments/research_point_3/README.md)。

已经完成：

1. 在严格208图上重建并冻结 `TeacherGraph_RP3_v1`；轻量证据记忆为208条Evidence、203项Claim、14份文档、10个来源族、38个故障—角色桶。
2. 精确重放研究点二选择与核验策略，导出40条原始教师轨迹；固定证据记忆查询泛化划分为32条train和8条组隔离validation。
3. MP008独立开发流程完成40/40核验；其轨迹、证据记忆和特征均标记为development，不参与梯度或早停。
4. 基线四头LEC完成训练、仅Route头效用拟合、FP32 ONNX导出和静态INT8 QDQ。INT8文件包含40个QDQ节点，使用40个MP008代表输入完成数值检查。
5. 基线路由rollout：train精确教师集合一致11/32，validation一致1/8；train动作目标为11 answer、16 fallback、5 abstain，validation为1 answer、6 fallback、1 abstain。
6. 基线MP008量化后校准失败关闭：40条中Route原始argmax为26 fallback、14 abstain、0 answer，最大可接受回答数为0。因此没有生成部署用 `calibration_manifest.json`，不得执行正式evaluate、工具部署或声称边缘效果。

本次续跑新增完成：

7. 构建集证据移除增强完成：原始40条加125条派生轨迹，train 129/validation 36，仍为10个原始故障场景；冻结7B核验响应、断点和可用性掩码全部保留。
8. `lec_augmented_v1` 完成train/route/export/quantize，参数量1,261,093，INT8大小1,342,926 bytes、40个QDQ节点。原始查询非空教师选集一致成功数为train 3/32、validation 0/8，未显示改善。
9. 增强组MP008校准失败关闭：40条全部原始argmax为abstain，可接受回答数为0。无部署校准证书，未执行evaluate。
10. 构建集只读诊断：24条教师非空的增强validation轨迹均预测所需角色数量为0，虽然均有支持分数≥0.5的同角色可用候选。
11. MP008仅3条教师非空回答、37条空集。在禁止空集answer的契约下，接受至少5个答案必有至少40%的教师集合不一致率，因此现有最低5个答案/不一致率≤10%的校准门槛本身不可达。未修改门槛或MP008数据。

完整结果和证据链接：[`RP3_AUGMENTED_V1_RESULTS_20260917.md`](RP3_AUGMENTED_V1_RESULTS_20260917.md)。
当前环境torch 2.6.0+cu118，基线记录为cu124；模型/训练配置一致但不能声称运行环境完全相同。

后续已完成P1离线诊断和P2核心逐头消融：

- 新增`diagnose`入口，已在B0/M0现有FP32/INT8上生成Pointer、Support、Field、Route、量化差异和CPU控制器计时；不读取MP008/外部样本。
- R0/R1/R2/R3-confidence/R3-entropy和成本Route在相同学生输出上离线重放；成本仍为无量纲1/8/12/50。
- 三种子7042027/7042028/7042029完成A1–A4：9次bootstrap和3次只拟合Route；A4复用A3，所有非Route权重和选集保持一致。
- 原始validation非空集合成功：A1为2/8、2/8、2/8；A2为2/8、3/8、2/8；A3/A4均0/8。验证集只有2个基础场景，不宣称统计泛化优势。
- 产物入口：[`RP3_DIAGNOSTICS_V1.md`](RP3_DIAGNOSTICS_V1.md)、[`RP3_HEAD_ABLATION_V1_PROTOCOL.md`](RP3_HEAD_ABLATION_V1_PROTOCOL.md)、`results/experiments/research_point_3/head_ablation_v1/summary.md`。
- 105项RP3测试通过（10条已有ONNX tracer warnings）；原1056个研究资产哈希保持不变。

字段监督审计和预声明的三种子归一化对照也已完成，见
[`RP3_FIELD_NORMALIZATION_V1_RESULTS_20260917.md`](RP3_FIELD_NORMALIZATION_V1_RESULTS_20260917.md)：

- 训练全字段零标签424/516（82.17%），但A3最佳模型非请求字段仅贡献约29%–35%的cardinality CE，不能声称空字段损失主导。
- A1/A2/A3最佳epoch均1的数值原因是验证排序损失增长超过其他损失下降；A1/A2没有字段损失也存在此现象。
- 复用三个A3控制，不重训；新臂将请求/非请求字段分别归一化后各权重0.5，其余设置不变，未附加MP008。
- 原始validation场景宏三种子均值：非空目标raw零预测91.67%→37.50%，请求raw基数准确率16.67%→37.50%，Pointer F1 0.0556→0.3472。
- 7042027在完整validation的教师空集误填0/12→3/12；**预声明整体改善条件未通过**。零可用证据误填仍每种子0/8。
- 新臂最佳epoch为2/1/1；不得根据后期任务指标另选checkpoint。114项RP3测试通过，原1160个研究文件哈希不变。
- 产物：`results/experiments/research_point_3/field_normalization_v1/`和`field_supervision_audit_v1/`；源码、协议、三个配置及控制引用在训练前冻结。

联合门控审计及W1/J1三种子实验已继续完成，见
[`RP3_JOINT_CONTRACT_V1_RESULTS_20260917.md`](RP3_JOINT_CONTRACT_V1_RESULTS_20260917.md)：

- 有候选且全部核验为负的教师空集只有train 5/129、validation 4/36；原7042027三头同时允许误填，非解码ID约束失效。
- C0复用上一轮requested_balanced；W1新增困难空集监督，J1再增加支持/字段/数量契约负对数概率正则，各3种子，未改解码。
- W1/J1完整validation教师空集误填均每种子0/12，但原始validation Pointer F1均值0.3472→0.0750，非空目标最终为空41.67%→90.28%，整体优化失败。
- J1较W1降低模型违约质量0.4878→0.4690，raw指标的预定窄比较通过；但两臂validation最终选集逐条相同，不能宣称答案质量改善。
- 两新臂最佳epoch均1/1/2；六次新训练的目标函数重建误差<2e-7，123项RP3测试通过，1265个旧研究/日志文件原样保留。
- 产物`results/experiments/research_point_3/joint_contract_v1/`及`joint_gating_audit_v1/`；理论说明见[`research/RP3_JOINT_CONTRACT_METHOD.md`](research/RP3_JOINT_CONTRACT_METHOD.md)。

支持可分性/梯度审计及G1正支持更新保护三种子也已完成，见
[`RP3_POSITIVE_GUARD_V1_RESULTS_20260917.md`](RP3_POSITIVE_GUARD_V1_RESULTS_20260917.md)：

- 同点式输入的教师正负标签冲突为train 10组、validation 3组，经验最少错误10/756、3/126；5条训练困难空集均不属于冲突组，不能用此解释全部退化。
- C0全train局部梯度中，正支持与困难负例梯度余弦−0.7242/−0.8266/−0.8018；它不是历史AdamW更新证据。
- G1仅改变W1实际参数位移：半空间投影保护train正支持，实际损失检查与失败回退；三种子预注册，复用C0/W1不重训。
- 原始validation场景宏Pointer F1为G1 0.1972、W1 0.0750、C0 0.3472；非空目标最终为空55.56%、90.28%、41.67%。G1每种子完整validation教师空集误填0/12。
- G1/W1通过预设均值比较，G1/C0失败。支持正例20/20过门，同时负例15/15也过门；不能称支持判别改善。三个最佳epoch均1，后期负支持损失上升，未事后换模型。
- 129项RP3测试、训练目标/更新/清单校验通过，1331个既有研究与日志文件原样保留；产物`support_separability_v1/`及`positive_guard_v1/`。

候选集合上下文S0/S1也已完成，见[`RP3_SET_CONTEXT_V1_RESULTS_20260917.md`](RP3_SET_CONTEXT_V1_RESULTS_20260917.md)：

- 六次新训练；S0/S1均1,409,222参数且初始化/RNG配对，C0只读复用。
- S1感知了旧冲突组中的上下文变化，但所有validation选集与C0相同，原始F1均值仍0.3472；负支持误接受场景宏均值0.6333→0.6500。
- S1/C0及S1/S0两项预设比较失败；最佳epoch均2/1/1。按预设停止规则暂停当前结构/损失试探。
- 理想路由上界已只读审计：原始validation教师非空7条，本地非空精确2/2/0条，即使oracle也至少回退5/5/7次才能零错误完整服务，不能直接宣称换路由可成功。
- 137项RP3测试通过，独立目标/机制/清单核验通过，1388个既有研究文件和日志保持不变；产物`set_context_v1/`、`scope_feasibility_v1/`。

E1冻结语义特征与同维度H512控制也已完成，各三个种子，C0只读复用。
原始validation场景宏F1均值C0/H512/E1为0.3472/0.2819/0.2792；E1种子7042027完整val空集误填4/12，C0为3/12。
E1非空精确提案G为2/1/0（C0为2/2/0），两项预设总体比较均失败。含编码器总参数25,411,621。
见[`RP3_SEMANTIC_V1_RESULTS_20260918.md`](RP3_SEMANTIC_V1_RESULTS_20260918.md)及`semantic_v1/summary.md`。
按停止规则暂停本轮encoder搜索和依赖其改善的新路由训练；下一步先评审构建集任务/监督/独立组数与研究范围，
不能以更换编码器或通用路由公式充当硕士算法贡献。旧阈值、MP008校准阻塞和既有资产均不变。
当前归一化、W1/J1/G1/S1均不能替换基线，不挑种子或事后改选epoch，不盲目加负例权重或降低支持门槛。
不得重跑已完成增强阶段、放宽校准门槛，或利用MP008选择学生超参数。两组都没有部署证书，evaluate继续阻塞。
基线和增强组目录均须保留。

仍未完成：可通过校准的学生、去可用性观测/去派生监督、B0/M0主方法三种子扩展、资源条件化选择性执行、MP009–MP013外部评价、620/1326层迁移、可选LLM壳接入，以及Jetson等目标边缘硬件的内存、端到端时延、能耗与热稳态测量。

## 远程新对话接手顺序

1. 先读根目录 `AGENTS.md`、本文件、`docs/RP3_EXPERIMENT_BASELINES_AND_TODO.md` 和 `docs/RP3_SERVER_EXPERIMENT_GUIDE.md`。
2. 执行 `git status -sb` 和 `git log -1 --oneline`，不要用reset/clean删除服务器实验资产。
3. 阅读增强结果报告，查看 `logs/rp3_augmented_calibrate_20260917.log` 和增强组 `experiment_summary.json`；当前最后成功阶段为增强组INT8量化，后续校准失败是已保存的负结果。
   后续离线工作已完成，优先阅读RP3结果根目录下`semantic_v1/summary.md`及E1结果报告，再看`set_context_v1/summary.md`、`scope_feasibility_v1/audit.md`与范围评审；此前`diagnostic_comparison_v1`、`head_ablation_v1`、`field_normalization_v1`、`joint_contract_v1`、`support_separability_v1`、`positive_guard_v1`也均已完成。不得重复这些实验。
4. 不重新运行已完成的teacher、MP008、features、基线或增强组，也不删除任一失败校准报告。
5. 任何教师一致性指标都不能写成专家诊断准确率；任何RTX服务器结果都不能写成真实边缘硬件结果。

接手时存在残留rebase和缺失资产，已从本地提交 `9370860` 恢复691个缺失文件，并备份后恢复6个旧版本。
恢复清单和rebase元数据位于 `logs/rp3_asset_recovery_20260917T000825/`。697个恢复资产均已复核未被本次实验改变。
残留rebase以 `--quit` 退出；当前分支为 `codex/rp3-augmented-v1-results`，原main提交保留。
Git中的6个受跟踪产物差异为恢复结果，不得当作临时改动清除；本次推送只收录结果索引列出的报告与清单，原始资产继续留在服务器。

## 命名说明

当前研究叙述不再把 `Silver` 作为方法名称或创新概念。历史论文、冻结配置、代码字段和目录中的 `silver` 为复现标识，不批量重命名。自动生成的内容统一说明为“教师生成监督”或“自动证据契约标签”，并明确不是专家真值。

历史规划与阶段报告索引见 [`archive/README.md`](archive/README.md)。
