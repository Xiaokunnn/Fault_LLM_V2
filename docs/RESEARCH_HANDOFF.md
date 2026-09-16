# Fault LLM v2 当前研究交接

更新日期：2026-08-13

本文件只保留当前状态和继续工作所需入口。此前数百行的阶段性构图日志、旧研究点编号和未完成计划已由两篇小论文终稿、冻结实验与 `docs/archive/` 中的历史文档取代。

## 当前研究结构

1. 研究点一：无需逐条人工审批的自动证据质量门控与可追溯知识图谱构建。
2. 研究点二：预算约束型向量—图协同证据检索、两阶段支持判别与确定性回答。
3. 研究点三：证据契约保持型决策蒸馏、轻量化与代价敏感边缘推理。

唯一当前总规划：[`research/MASTER_THESIS_THREE_RESEARCH_POINTS_PLAN.md`](research/MASTER_THESIS_THREE_RESEARCH_POINTS_PLAN.md)。

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

## 研究点三启动前必须解决

1. 冻结唯一 `TeacherGraph_RP3_v1`：严格208、保守620与标准1326不能混用同一名称。
2. 在所选教师图上重建向量索引并重放研究点二选择、核验和拒答流程。
3. 定义完整诊断卡和教师轨迹契约；确定性渲染器继续作为规则组件，不作为主要蒸馏对象。
4. 学生主体固定为目标参数量小于50M的四头轻量证据控制器（LEC），以ONNX INT8部署；3B模型只可作为可选对话壳/工具调用者，不是主要蒸馏对象。
5. 以有界本地证据访问保持ID可追溯；没有候选/可用性输入的闭卷学生不得声称学习证据删除干预。
6. MP008仅开发；MP009–MP013仅最终外部评价，不进入训练、课程、阈值或路由校准。
7. 真正声称边缘部署前，至少在一块目标板上测量内存、TTFT、TPOT、端到端时延、能耗与热稳态。

## 命名说明

当前研究叙述不再把 `Silver` 作为方法名称或创新概念。历史论文、冻结配置、代码字段和目录中的 `silver` 为复现标识，不批量重命名。自动生成的内容统一说明为“教师生成监督”或“自动证据契约标签”，并明确不是专家真值。

历史规划与阶段报告索引见 [`archive/README.md`](archive/README.md)。
