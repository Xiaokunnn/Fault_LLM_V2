# RP1 expanded_v1_20261012

实际扩展研究图：1456条证据记录、1400种规范化关系、2150个中文实体、15份构建文档、505个有记录页。相对旧standard1326净增130条证据、119种关系。旧strict208和RP2/RP3教师不替换。

| 文件 | 用途 |
|---|---|
| `triples.csv` | 打开查看中文三元组、页码、来源、条件 |
| `graph.graphml` | 有向关系图；边关联断言ID |
| `entities.jsonl` | EXE实体ID、中文名称、类型 |
| `claims.jsonl` | EXC规范化关系及端点；相同关系的不同证据聚合 |
| `evidence_assertions.jsonl` | EXA断言ID、源文、适用范围、条件、模态、实际原生定位 |
| `source_records.jsonl` | 完整历史载荷与新恢复依据 |

连接方式：GraphML边ID = claims.claim_id；边的assertions属性连接evidence_assertions.assertion_id。条件在断言上，不能只读GraphML裸边就当作无条件事实。旧图记录没有新条件字段的部分为null/legacy_unspecified，不代表没有条件。

`expansion_layer=baseline_reused`的1326条复用旧图，`new_recovered`的130条为本轮恢复。统一读取`expanded_*` ID关联本图；旧记录自身原ID保留。

新记录的本轮资格说明位于`expansion_validation`，原审计状态保存在`expansion_prior_validation`。为保留历史，若干根字段如`evidence_validation`、`relation_entailment_validation`、`validation_status`、`graph_release_status`、`final_confidence`仍是原候选历史值，**不得当成新一轮验证结果**。本轮没有重新运行旧模型，旧E1/E2/E3等级也未重写；新增原生定位只看`expansion_source_witnesses`。

新增40条固定AI抽查中，38条关系有源文支持；26条进一步满足局部条件完整要求，11条有缺陷、3条未决。抽查旁注及原图对照详见[结果报告](../../../../../docs/research/RP1_GRAPH_EXPANSION_V1_RESULTS_20261012.md)和[质量判断](../../../../../results/experiments/research_point_1/graph_expansion_v1_20261012/quality_review.jsonl)。未审记录不能视为通过人工/AI逐条复核。

图文件在质量抽查前已固定，发现问题后未删除记录。当前是研究图，不是已证明准确的替代生产图。所有源文、URL、物理页及文档/页面哈希保持不变。没有新增API调用。
