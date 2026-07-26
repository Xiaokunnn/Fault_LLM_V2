# Configurations

保存可版本化的流水线配置，不在代码中硬编码实验参数。

当前已冻结：

- `document_split_marine_pump_v2.json`：新增独立来源后的正式文档级划分和来源家族隔离。
- `fault_ontology_marine_pump_v1.json`：10类故障的统一选页/映射规则与正式覆盖门槛。
- `page_layout_review_marine_pump_v2.json`：代表页视觉核验和印刷页码覆盖。
- `targeted_page_plan_marine_pump_v2.json`：第一轮24页定向补抽计划。
- `entity_terminology_zh_marine_pump_v1.json`：中文图谱的类型、关系、中英术语、受保护词和翻译发布状态。
- `triple_extraction_qwen3_7_max_targeted_zh_v1.json`：下一轮24页中文规范实体候选抽取契约；当前只冻结契约，尚未调用模型。
- `triple_extraction_qwen3_7_max_pilot_v1.json`：历史四页试抽取的百炼模型、重试和密钥不落盘策略。
- `document_split_marine_pump_pilot_v1.json`：历史试抽取划分，仅用于结果复现；正式解析与覆盖统计不得再使用。

后续阶段再新增：

- `ingest_v1.json`：解析器、页范围和 chunk 策略。
- `extraction_v1.json`：模型、提示词版本和置信度阈值。
- `graph_v1.json`：Schema、去重和图谱版本参数。
- `benchmark_v1.json`：文档切分、查询规模和噪声比例。
- `retrieval_v1.json`：元路径、关系权重、候选上限、提前终止和时延档。
- `runtime_rk3588_v1.json`：线程、功耗模式、存储、索引、缓存和内存上限。
