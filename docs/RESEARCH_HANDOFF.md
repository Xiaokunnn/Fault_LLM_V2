# Fault LLM v2 当前研究交接

更新日期：2026-09-17

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

## 研究点三当前状态

服务器工作目录为 `~/08-zxk/Fault_LLM_V2`。代码从 `origin/main` 同步，正式实验输出保留在服务器，未随Git提交。

已经完成：

1. 在严格208图上重建并冻结 `TeacherGraph_RP3_v1`；轻量证据记忆为208条Evidence、203项Claim、14份文档、10个来源族、38个故障—角色桶。
2. 精确重放研究点二选择与核验策略，导出40条原始教师轨迹；固定证据记忆查询泛化划分为32条train和8条组隔离validation。
3. MP008独立开发流程完成40/40核验；其轨迹、证据记忆和特征均标记为development，不参与梯度或早停。
4. 基线四头LEC完成训练、仅Route头效用拟合、FP32 ONNX导出和静态INT8 QDQ。INT8文件包含40个QDQ节点，使用40个MP008代表输入完成数值检查。
5. 基线路由rollout：train精确教师集合一致11/32，validation一致1/8；train动作目标为11 answer、16 fallback、5 abstain，validation为1 answer、6 fallback、1 abstain。
6. 基线MP008量化后校准失败关闭：40条中Route原始argmax为26 fallback、14 abstain、0 answer，最大可接受回答数为0。因此没有生成部署用 `calibration_manifest.json`，不得执行正式evaluate、工具部署或声称边缘效果。

当前正在做：预先声明的构建集证据移除增强实验。该实验只对构建集候选集合做全删除、已选证据逐条删除和首个未选证据删除，并使用冻结7B重新核验受影响选择；派生行继承原故障场景split。它不是新增独立病例，也不使用MP008调参。

服务器下一步：

```bash
cd ~/08-zxk/Fault_LLM_V2
git pull --ff-only origin main
bash scripts/run_rp3_experiments.sh augment \
  2>&1 | tee logs/rp3_augment_20260917.log

export RP3_CONFIG=configs/research_point_3/lec_train_augmented_v1.json
export RP3_RUN_DIR=results/experiments/research_point_3/lec_augmented_v1
bash scripts/run_rp3_experiments.sh train
bash scripts/run_rp3_experiments.sh route
bash scripts/run_rp3_experiments.sh export
bash scripts/run_rp3_experiments.sh quantize
bash scripts/run_rp3_experiments.sh calibrate
```

只有增强组生成有效校准证书后才能执行 `evaluate`。基线目录 `results/experiments/research_point_3/lec_v1` 必须保留，作为无干预增强对照。

仍未完成：增强组结果、MP009–MP013外部评价、620/1326层迁移、完整消融、可选LLM壳接入，以及Jetson等目标边缘硬件的内存、端到端时延、能耗与热稳态测量。

## 远程新对话接手顺序

1. 先读根目录 `AGENTS.md`、本文件和 `docs/RP3_SERVER_EXPERIMENT_GUIDE.md`。
2. 执行 `git status -sb` 和 `git log -1 --oneline`，不要用reset/clean删除服务器实验资产。
3. 查看 `logs/rp3_augment_20260917.log` 和增强目录是否已生成，再从最后成功阶段继续。
4. 不重新运行已完成的teacher、MP008和基线训练，也不删除失败的基线校准搜索报告。
5. 任何教师一致性指标都不能写成专家诊断准确率；任何RTX服务器结果都不能写成真实边缘硬件结果。

## 命名说明

当前研究叙述不再把 `Silver` 作为方法名称或创新概念。历史论文、冻结配置、代码字段和目录中的 `silver` 为复现标识，不批量重命名。自动生成的内容统一说明为“教师生成监督”或“自动证据契约标签”，并明确不是专家真值。

历史规划与阶段报告索引见 [`archive/README.md`](archive/README.md)。
