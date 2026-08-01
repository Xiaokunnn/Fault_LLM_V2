# Fault LLM v2

面向船舶机械故障智能诊断的研究项目，最新三研究点规划为：研究点一研究船舶机舱泵系可追溯 Silver 证据知识图谱构建与质量治理；研究点二研究来源族感知的预算约束低时延图谱证据检索；研究点三研究证据选择/诊断能力蒸馏及风险受控使用。三点形成“可信知识生产→低时延证据选择→能力蒸馏与风险控制”的递进链条。

完整的三研究点规划见 [`docs/research/proposal_marine_pump_evidence_2026-07-20.md`](docs/research/proposal_marine_pump_evidence_2026-07-20.md)；研究点一的当前基础、实施细节和迁移说明见 [`docs/RESEARCH_HANDOFF.md`](docs/RESEARCH_HANDOFF.md)。

该项目是重新构建的独立主数据线。旧轴承图谱、旧图片和既有实验继续保留在同级 `Edge_Fault_LLM`，不迁入本目录。旧项目只作为算法原型参考，v2 的图谱、数据划分和实验结论必须独立生成。

## 当前状态

- 已完成五类船舶机械对象比较，选定船舶机舱泵系。
- 已收集并校验21份公开PDF，共2096页。其中15份构建集文档共1934页；MP008为36页开发集；MP009—MP013共126页，为保留测试集。MP010—MP013当前只完成文件级封存，不进入主图谱或调参。
- 已发布文档级v4划分：原开发集与保留测试集边界不变；MP017—MP022仅进入构建集，不被包装为独立盲测资料。
- 已定义 10 类候选故障和带证据溯源、关系类型约束的三元组 Schema。
- 已完成4份代表性文档各1页的 `qwen3.7-max` 试抽取：模型提出56条，31条通过候选阈值，25条因原文跨度无法验证而拒绝；保留候选中23条达到当前Silver置信度阈值，8条待复核，其中1条由二次AI语义抽样审计明确降审，7条长跨度重建证据均不得自动进入高置信层。MP008开发页仅保留2/23条，跨厂商表格迁移尚未通过。
- 已完成Python版结构化文档解析和严格v2.1本地复验：正文与表格分别保存文本块、行列、单元格和bbox，并增加页级来源语言识别及中英文故障表头支持；旧31条候选经实体锚点、关系蕴含及E1/E2/E3规则复验后，仅3条保留为严格Silver候选，11条待复核，17条拒绝。
- 已冻结“中文语义层 + 多语言原文证据层”规则：最终实体、类型和关系显示统一中文，关系/类型机器码保持稳定；英文原文、页码、bbox和URL不得被译文覆盖。仅词典批准或独立复核通过的中文规范名可进入正式图谱。
- 已完成429页source-v3宽召回抽取，共形成1245条候选；严格校验后235条为Silver，双轮拒绝优先语义裁决再晋级110条，最终为345条Silver、134条自动裁决未通过记录和766条拒绝。
- MP022定向补缺后的历史结果为535条Silver、187条自动待判/隔离和1085条拒绝、7/10类通过；该结果已被最终语义修复版本取代。
- 已从source-v3结果一次性冻结82个缺口修复页，其中10个已有视觉核验记录的表格页已重新执行同行/同行组解析；Schema v3新增方向受限的`prevented_by`，不把预防动作改写成确定因果。
- 已新增并完整解析MP022 Alfa Laval官方手册52页，冻结其中8个缺口页面；关键表格页已完成AI视觉版面核验并完成qwen3.7-max抽取、严格校验和覆盖重算。
- 已完成最终语义修复和拒绝优先双轮自动裁决：当前为534条Silver、188条自动待判/隔离和1088条拒绝；全程无人工专家审核，全部结果仅称Silver。
- 已用故障类别映射v1.4执行头尾字段限定的本地冻结复算，移除7条由同表其他单元格词汇触发的管路/阀件误映射；管路/阀件检维证据由13条回落到8条，10类故障仍全部通过证据门槛，正式决策为`start_full_extraction`。
- 当前10/10只表示构建集的原文证据覆盖门槛通过，不表示中文图谱或Silver EvidenceBench已经完成；中文发布门槛当前仍需在全量抽取后的术语规范化阶段单独完成。
- 已冻结全量构图流水线：15份构建文档1934个物理页中，1889页进入`qwen3.7-max`逐页抽取，45页按空白、封面、目录、索引或完全重复规则确定性排除；流水线支持隐藏密钥、逐页进度、ETA、有限重试、响应缓存和中断续跑。

## 目录结构

```text
Fault_llm_v2/
├── configs/                         流水线、Schema 和实验配置
├── data/
│   ├── source_docs/marine_pump/     原始 PDF、来源清单、待下载清单
│   ├── interim/
│   │   ├── parsed_pages/            页级解析结果
│   │   └── candidate_triples/       试抽取候选及逐条校验状态
│   └── kg/marine_pump/
│       ├── schema/                  节点、关系和溯源约束
│       ├── triples/                 校验后的版本化三元组
│       ├── graph_versions/          GraphML、gpickle、索引和统计
│       └── silver_evidencebench/    查询、候选路径、Silver 标签和审计
├── docs/research/                   资料清单、对象评分和选型报告
├── results/
│   ├── benchmarks/                  证据质量、时延、资源和鲁棒性指标
│   └── experiments/                 实验运行输出
├── scripts/                         可重复运行的命令入口
├── src/
│   ├── research_point_1_graph_evidence/
│   │   ├── stage01_document_ingest/   PDF 页级解析与切分
│   │   ├── stage02_triple_extraction/ 原文surface与中文规范名候选抽取
│   │   ├── stage03_schema_validation/ 证据、关系、来源及中文规范化校验
│   │   ├── stage04_graph_build/        版本化知识图谱构建
│   │   ├── stage05_silver_benchmark/   文档隔离的 Silver EvidenceBench
│   │   ├── stage06_retrieval/          锚点、门控、扩散和元路径检索
│   │   └── stage07_evaluation/         baseline、时延、资源、消融和鲁棒性实验
│   ├── research_point_2/            图谱证据蒸馏与原型记忆（尚未启动）
│   └── research_point_3/            置信度校准与选择性回退（尚未启动）
└── tests/                           单元测试和端到端集成测试
```

当前 `data/`、`docs/research/` 和 `results/` 中已经存在的船舶机舱泵系数据与实验内容均属于研究点一。研究点二在研究点一低时延教师、目标硬件协议与评价协议冻结后启动，研究点三在学生输出与置信特征稳定后启动，并按相同原则建立各自的数据、文档和结果边界。

## 数据原则

1. 原始文档只读保存，不在原 PDF 上修改。
2. 每条三元组必须保存 `doc_id`、页码/章节、`evidence_text`、置信度、抽取器和来源 URL。
3. 构图、开发和测试文档按文档来源隔离，避免查询与证据泄漏。
4. 词法命中只能用于定位页面，不能直接作为三元组或 Silver 标签。
5. 每类故障至少获得5条症状证据、3条原因/机理证据和2条检查/维修证据，并来自至少2份独立文档和2个 `source_family_id`；未达标类别不得进入批量构图。
6. 泵型、服务场景和适用范围必须随证据保存；柔性叶轮泵等特定机理不得无条件推广到全部离心泵。
7. 正式图谱使用中文规范实体；原语言实体surface和证据原文作为EvidenceAssertion保留，中文译文不能替代证据或参与覆盖计数。

## 实施顺序

1. 以 `data/interim/candidate_triples/final_semantic_gap_v1_gate_frozen/` 作为覆盖门槛冻结产物；不得再用开发集或保留测试集补构建覆盖。
2. 为15份`build_train`文档的1934个物理页建立全量抽取清单；只允许按预注册的空白页、封面、目录、索引和重复页规则作确定性排除，不能再按10类检索分数缩成候选池。
3. 使用冻结的Schema、提示词和故障映射批量调用`qwen3.7-max`，逐页打印进度并支持缓存、断点续跑、重试和失败页清单。
4. 所有候选通过严格证据、表格同行/同行组、关系Domain/Range、适用范围和文档划分校验；E3及无效E1/E2不得自动进入Silver。
5. 全量抽取完成后执行中文术语规范化并分别冻结 `KG_v1_raw`、`KG_v1_validated`；原文surface、页码、bbox和来源URL继续保留，不被中文译文覆盖。
6. 在构图阶段保留同一Claim的多来源断言，禁止规则注入、事后来源回填、按度删证据、频率定方向和强制DAG。
7. 构造总计30—50条Silver质量查询，并为路径排序评价冻结每条查询的30—80条候选证据路径。
8. 冻结目标低算力硬件和性能测量协议，迁移并复验索引、领域门控、元路径增量扩展、自适应剪枝、提前终止和缓存方法。
9. 主图谱与方法冻结后再解析已封存的MP009—MP013并开展外部测试，最后运行端到端时延、资源、消融和噪声鲁棒性实验；Token数只作可选下游生成成本的次要指标。

当前试抽取报告见 [`results/benchmarks/qwen3_7_max_triple_pilot_v1/pilot_extraction_report.md`](results/benchmarks/qwen3_7_max_triple_pilot_v1/pilot_extraction_report.md)，候选记录见 [`data/interim/candidate_triples/qwen3_7_max_triple_pilot_v1/candidate_triples.jsonl`](data/interim/candidate_triples/qwen3_7_max_triple_pilot_v1/candidate_triples.jsonl)。
