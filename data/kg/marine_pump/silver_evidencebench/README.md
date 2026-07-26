# Marine Pump Silver EvidenceBench

该目录用于构造船舶机舱泵系的弱监督证据检索测试集。

基本要求：

- 查询与正例证据按文档隔离，避免由路径反向生成查询造成闭环。
- Silver 正例必须有原文证据位置且置信度不低于 0.8。
- 第一版总计 30-50 条查询，10 类故障各覆盖约 3-5 条；每条查询配置 30-80 条候选路径。
- 同时报告全量 Silver 集和高置信 Silver 子集的结果。
- 使用 macro 指标，避免高频故障类型主导结论。

当前已提供以下中间审计资产，但尚未生成 EvidenceBench 查询或标签：

- `fault_scope_draft_v1.json`：历史故障范围草案，仅保留作版本追踪；正式映射以 `configs/fault_ontology_marine_pump_v1.json` 中声明的内容版本为准。
- `source_coverage_lexical_build_v2.csv`：仅构建集的词法候选页审计。
- `fault_category_coverage_matrix_v2.csv/json/md`：严格 Silver 证据覆盖、来源覆盖和词法候选页的联合矩阵。

词法命中只用于定位待抽取页面，不能作为三元组、类别归属或 Silver 正例。当前10类均未通过严格的批量构图门槛，图谱和 Silver EvidenceBench 均尚未构建。
