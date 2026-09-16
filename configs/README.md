# Configurations

该目录保存可版本化的Schema、文档划分、提示契约、图谱构建、检索、生成、评价和冻结配置。物理文件名中的 `silver` 为历史兼容标识，不代表专家真值。

当前关键配置包括：

- `document_split_marine_pump_v4.json`：最终文档级划分；
- `fault_ontology_marine_pump_v1.json`：10类候选故障及角色映射；
- `provenance_schema_marine_pump_v1.json`及相关Schema：证据与来源字段；
- `entity_terminology_zh_marine_pump_v4_silver.json`：冻结的中文术语治理配置；
- `rp2_graphrag_v6_equal_budget.json`：研究点二v6主实验；
- `rp2_graphrag_v6_1_no_graph_control.json`：公平去图控制；
- `frozen/rp2_v6_paper_evidence_freeze.json`：研究点二论文证据冻结清单。

研究点三不得直接继承含糊的 `KG_v1_validated` 名称。主教师清单固定为 `configs/research_point_3/teacher_graph_rp3_v1.json`，只绑定RP2 v6真实使用的208条严格层及其输入哈希、证据/Claim/实体规模、模型、索引和重放版本；620/1326条层只以独立 `TierShift` 身份作冻结后压力测试。

API密钥不得写入配置、命令历史、日志或缓存元数据。
