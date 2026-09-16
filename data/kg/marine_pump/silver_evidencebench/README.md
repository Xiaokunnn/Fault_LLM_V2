# Marine Pump Evidence Benchmark

目录名中的 `silver_evidencebench` 是冻结兼容路径。当前统一称其为**自动证据评价集**，相关性和支持标签均非专家真值。

## 已形成资产

- `rp2_full_graph_development_v2/`：研究点二v6的40条受控查询及208条候选证据；覆盖10类候选故障与4类诊断角色，其中34条可回答、6条不可回答。
- `rp2_v6_paraphrase_robustness/`：80条确定性问题改写，只用于检索措辞稳健性评价。
- `rp2_development_v1/`：早期开发版本，保留用于复现，不作为当前论文主结果。

## 使用规则

- 在线方法不得读取 `relevant_evidence_ids`、`fault_class_ids` 等答案字段。
- 评价按基础查询、故障类、Claim或来源族成组统计；同一问题的改写不是独立样本。
- MP008只用于开发；MP009–MP013只用于冻结后的外部评价，不进入训练、调参或路由校准。
- 该评价集检验受控查询下的检索、引用、作答与拒答行为，不代表开放式故障识别或工程维修准确率。
