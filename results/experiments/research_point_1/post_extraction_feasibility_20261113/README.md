# RP1第一阶段：抽取后构图的数据可行性审计

日期：2026-11-13。状态：完成只读审计，**等待用户确认后才能进入第二阶段**。本目录不是新算法实现、模型实验或新图谱版本。

## 阅读入口

| 文件 | 内容 |
| --- | --- |
| [rp1_data_lineage.md](rp1_data_lineage.md) | 真实规模、版本、来源/字段、候选流转、可用池和ID |
| [rp1_problem_statistics.csv](rp1_problem_statistics.csv) | 问题类型、数量/分母/单位、来源、自动候选身份及可信度限制 |
| [rp1_casebook.md](rp1_casebook.md) | 19个真实正反例；原文、候选、审计、发布结构及解释 |
| [rp1_direction_decision.md](rp1_direction_decision.md) | A/B/C比较、一个优先/备选、放弃理由及四个验收答案 |
| [summary.json](summary.json) | 完整机器可读统计、字段覆盖、图结构及旧AI评价边界 |
| [source_manifest.json](source_manifest.json) | 原始输入/代码SHA256、当前提交和保全检查 |
| [verification.json](verification.json) / [reproduction_check.json](reproduction_check.json) | 68份输入保全、40份派生文件复算一致及计数闭包 |
| [delivery_manifest.json](delivery_manifest.json) | 本独立审计目录交付文件的SHA256（不对自身递归取哈希） |

结论为：B优先进入最小必要性验证，C备选，A在现有语料上暂不立项；**三者均没有已成立的专门算法贡献证明**。不能把“值得小样本验证”写成“已建议训练模型或实现联合优化”。当前最大可量化结构症状是碎片化，不等于全部为对齐错误。

## 逐条数据入口

- `candidate_locator_audit.jsonl`：8003条当前Schema/原生位置/来源复核。
- `candidate_flow_ledger.jsonl`：8003条互斥程序阶段归因。
- `raw_candidate_lineage.jsonl`：8007项原缓存ID显式血缘。
- `version_parent_crosswalk.jsonl`：1456条发布记录到扩图输入父记录的已存对照。
- `expanded_location_checks.jsonl`：1326旧契约与130原生子跨度分别回读。
- `clusters/*_exact.jsonl`：每个重复主张族的完整证据、页、范围与条件；不代表完整事实等价。
- `clusters/*_similarity_pairs.jsonl`：固定阈值的词法相似候选对，非合并标签。
- `entities/entity_occurrences.jsonl`：2150个实体的实际来源、角色、邻居及范围。
- `entities/name_similarity_pairs.jsonl`、`name_candidate_clusters.jsonl`：158对、119候选簇；不宣称传递同义。
- `entities/locator_pool_alias_hypotheses.jsonl`：3956位置可用旧候选中的225个同表面多中文标签簇及28个词典候选簇，两种集合重叠，不作未解决错误数。
- `entities/same_surface_multiple_entities.jsonl`、`dictionary_candidate_clusters.jsonl`：两个保守检索为空，文件保留；不证明全图无歧义。
- `condition_page_candidates.jsonl`、`condition_record_candidates.jsonl`：关键词取样框，非条件错误。
- `existing17_full_chain.jsonl`：17个原有开发靶点、旧评价、完整请求输出追踪和当前发布页记录。
- `existing_expansion_quality.jsonl`：80条既有单AI非盲评价，标签不改。
- `casebook_records.jsonl`：19案例的完整候选、显式legacy/源键连接、原生页上下文及图状态。
- `graph/*_summary.json`、`*_claim_evidence.jsonl`、`*_typed_paths.json`：仅实体—语义关系的统计，未混入来源中间节点。
- `conflict_candidates.jsonl`：本轮有限同键引文极性混合检索为0，**真实冲突总量未测**。

## 复现

在仓库根目录，使用已有本地环境：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/experiments/research_point_1/post_extraction_feasibility_20261113/audit_post_extraction.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/experiments/research_point_1/post_extraction_feasibility_20261113/build_casebook.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/experiments/research_point_1/post_extraction_feasibility_20261113/audit_post_extraction.py --verify
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/experiments/research_point_1/post_extraction_feasibility_20261113/verify_audit.py
```

第一个脚本仅向本独立目录重算统计，会覆盖**本目录自身的派生统计**；不执行旧实验脚本的main，也不写原图/旧实验。第二个脚本从固定的19项分析选择渲染案例，不执行修复。第三个命令只检查输入及审计脚本哈希，第四个核对统计闭包、交付和原始保全。

环境使用已有Python、scikit-learn（字符TF-IDF/近邻）、networkx；不加载任何预训练模型、不创建新索引服务、无需API key。检索阈值、模式、构建文档集合见`audit_config.json`，包版本见`environment.json`。算法或环境变化时使用新审计目录，不覆盖本轮交付封存文件。

`audit_post_extraction.py`复用了现有`audit_record`、`load_provenance_schema`等只读函数。最初预检发现直接将原始v3 JSON传给validator会缺少规范化验证视图，已改为调用仓库既有Schema加载器；交付数字来自修正后的完整复算，不采用该预检错误计数。没有修改仓库Schema或validator。

本轮没有新的独立语义评价集。词法检索、旧自动标签和本次定向助手分析各自标识，均不是人工专家Gold。没有用RP2查询指标代替构图质量，没有执行RP2/RP3迁移、训练或新算法设计。
