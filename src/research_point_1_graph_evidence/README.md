# Research Point 1: Marine Pump Graph Evidence

研究点一代码目录，研究范围为低算力约束下的船舶机舱泵系低时延图谱证据检索与自适应剪枝。

计划模块：

```text
stage01_document_ingest/    PDF 页级解析与 chunk 生成
stage02_triple_extraction/  带 evidence_text 的三元组抽取
stage03_schema_validation/  类型、关系方向和来源校验
stage04_graph_build/        版本化 KG、类型邻接和元路径索引构建
stage05_silver_benchmark/   文档隔离的 Silver EvidenceBench
stage06_retrieval/          锚点索引、门控、增量扩展、提前终止和缓存
stage07_evaluation/         证据质量、时延、资源、消融和鲁棒性实验
```

旧项目 `Edge_Fault_LLM/src/02_graph_rag/graph_prune/` 中的查询解析、锚点匹配、领域门控、元路径、证据评分、自适应剪枝和重排算法可作为迁移参考。迁移时应去除旧轴承图谱路径和实验耦合，补充离线索引、访问代价、提前终止、缓存及分阶段计时，并在本项目中重新测试。旧Token预算选择只可保留为可选输出整理组件。

当前已完成文档级v2划分、Python版坐标保持PDF解析、严格v2.1证据校验、中文语义层规范、类别覆盖矩阵、24页定向补抽计划及两份独立来源补充。正式图谱将统一使用中文规范实体、中文关系显示名和中文类型显示名，同时保留英文或中文原文证据。尚未构建正式图谱和 Silver EvidenceBench。

`audit_document_coverage.py` 对本地 PDF 运行可复现的词法覆盖审计。结果只用于筛选待抽取页面，不能直接作为三元组或 EvidenceBench 标签。

`stage02_triple_extraction/bailian_qwen_pilot.mjs` 使用百炼 `qwen3.7-max` 的非思考 JSON 模式执行离线抽取。密钥只从当前进程环境变量或内存参数读取，不进入配置、日志或结果。当前冻结试抽取页为 MP001 PDF p.52、MP004 PDF p.11、MP005 PDF p.60 和 MP008 PDF p.26；结果见：

- `data/interim/candidate_triples/qwen3_7_max_triple_pilot_v1/candidate_triples.jsonl`
- `results/benchmarks/qwen3_7_max_triple_pilot_v1/pilot_extraction_report.md`
- `results/benchmarks/qwen3_7_max_triple_pilot_v1/pilot_coverage_report.json`

本轮模型原始提出56条，31条通过候选阈值，25条因原文跨度无法验证而拒绝；保留候选中23条达到当前 Silver 置信度阈值，8条待复核，其中1条由二次AI语义抽样审计明确降审，7条长跨度重建证据均不得自动进入高置信层。构建集10类故障的批量构图覆盖门槛均未通过，因此不得据此启动批量构图。MP008属于开发集且仅保留2/23条原始提议，表明跨厂商表格迁移尚不稳定；其证据不补足构建集覆盖数量。

严格v2复验不调用外部模型。旧31条候选中3条保留为严格Silver候选、11条进入待复核、17条拒绝；7条历史重建证据全部保持E3，不得因重新定位到原文而升级为E1。正式校验代码位于 `stage03_schema_validation/`，复验和矩阵结果位于：

- `data/interim/candidate_triples/qwen3_7_max_triple_pilot_strict_v2/`
- `data/kg/marine_pump/silver_evidencebench/fault_category_coverage_matrix_v2.md`

中文图谱采用双层语言策略：

- EvidenceAssertion中的实体surface、`evidence_text`、页码、bbox和URL保持来源原语言；
- CanonicalEntity的规范名统一中文，英文来源词形保存为结构化别名；
- `causes`、`FaultMode`等机器码不改动，展示为“导致”“故障模式”等冻结中文名；
- 模型翻译默认待复核，只有冻结词典命中或独立复核通过后才具备中文图谱发布资格。
