# Research Point 2: Budget-Constrained Low-Latency Evidence Retrieval

## GraphRAG v2（大模型实验主线）

`dense_index.py` 使用本地 BGE-M3 建立中文证据向量索引；`graph_rag_v2.py` 实现稠密向量召回、固定跳数、自适应扩散、关系角色约束和来源族预算选择；`generation.py` 定义 Qwen2.5-7B-Instruct 的证据限定生成协议与引用校验。

服务器完整执行命令和反泄漏边界见 `docs/RUN_RP1_RP2_NEXT_EXPERIMENTS.md`。旧的字符串检索代码保留为 pilot/对照，不代表最终大模型 GraphRAG 实验。

研究点二为“面向船舶机舱泵系故障辅助诊断的来源族感知预算约束图谱证据检索方法”。它以研究点一冻结的中文可追溯 Silver 证据图谱为输入，研究在候选评分数、图/证据访问数、返回证据数和时延截止约束下，如何保留与故障问题有关、来源独立且低冗余的证据。

本研究点不以减少 Token 作为主目标。Qwen 生成是最终实验的必要环节，Token 数只是辅助成本指标；主要性能指标是端到端 p50/p95 时延、超时率、候选评分数、证据访问数、引用有效率和回答完成率。

## 与研究点一的边界

- 研究点一负责文档证据抽取、Silver 分级、来源族治理、中文术语发布和图谱结构质量。
- 研究点二不修改 Silver 标签和主图，只消费冻结的 `KG_v1_validated` 和版本化基准。
- 来源族字段作为检索时的多样性约束，不被解释为来源间统计独立。
- 自动或半自动产生的查询、候选集、证据标签和结果统一称为 Silver，绝不称 Gold。

## 当前实现

- `dataset.py`：从 `KG_v1_validated` 分层 JSONL 读取可追溯证据，并从冻结 CQ v1 生成开发版 Silver 候选集。
- `retrieval.py`：实现全量词法扫描、结构化 Top-K 和来源族感知预算约束选择。
- `evaluation.py`：实现 Recall@K、MRR、nDCG、来源族覆盖、冗余率和 p50/p95 时延统计。
- `dense_index.py` / `graph_rag_v2.py` / `generation.py`：实现最终的 BGE-M3 + 图扩散 + Qwen2.5-7B 链路。

CQ v1 中的 `fault_class_ids`、答案实体 ID 和相关证据 ID 都是隐藏评价字段，不得作为在线排序特征。候选故障名称通过查询文本和图中的中文实体标签进行锚点，关系角色门控只使用冻结 Schema，避免将 CQ 结构统计冒充检索性能。

当前 CQ 派生候选集只是开发基准，用于联调方法和发现问题，不能冒充保留测试。MP009–MP013 只能在主图、查询协议、方法参数和性能协议冻结后用于一次性外部 Silver 评价。
