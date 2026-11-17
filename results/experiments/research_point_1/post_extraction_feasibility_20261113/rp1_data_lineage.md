# RP1抽取后构图：数据资产、血缘与可用性审计

日期：2026-11-13。当前检出`833c8040058055434c7f6a9595ec524c3935755f`。本轮为只读数据审计：不生成候选、不训练、不调用模型、不访问Neo4j、不改图谱和历史评价。代码提交是当前观察快照，不冒充所有历史实验的执行提交。结果、原始输入哈希和可复算脚本均在本独立目录。

## 1. 核数与口径

下表路径均相对仓库根。原始目录简称`data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/`。

| 资产 | 实际规模 | 位置/来源 | 说明 |
| --- | ---: | --- | --- |
| 原始API提议 | 8071 | 原始目录`extraction_run_summary.json` | 模型提议口径，不是8003 |
| 接口拒绝 | 64 | 原始目录`rejected_model_proposals.jsonl` | 53中文标签形式、10未知关系、1缺类型；不是PDF解析失败或已判事实错误 |
| 原始缓存候选 | 8007 | 原始目录`candidate_triples.raw_zh.jsonl` | 提议载荷、两端/引文/页/请求ID等 |
| 历史全审计图 | 8003记录、7651存储Claim、9149实体 | `data/kg/marine_pump/triples/KG_v1_raw/` | 含1698自动准入、881隔离、5424拒绝 |
| 后续证据修复输入 | 8003 | `data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/candidate_triples.evidence_repaired.jsonl` | 与上一行同条数但版本/ID/字段不完全相同，不能按位置拼接 |
| 历史自动准入集 | 1698记录、1650历史Claim | 全审计图按保存决策选择 | 历史代码/路径保留Silver名称；不是事实Gold |
| strict208 | 208断言、203 Claim、281实体 | `data/kg/marine_pump/triples/KG_v1_validated/` | 历史归档和旧RP2/RP3冻结来源 |
| standard1326 | 1326断言、1281 Claim、2022实体 | `data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full/standard_graph/triples/KG_v1_validated/` | 标准术语治理对照 |
| expanded1456 | 1456断言、1400 Claim、2150实体 | `data/kg/marine_pump/versions/expanded_v1_20261012/` | 当前研究主图；新下游迁移未执行 |

8007→8003经历规范化/证据修复/去重和身份变化，净差4不能代表只有4次处理损失。通过显式`legacy_triple_id`可把7991条缓存记录连到审计池，16条没有这种直接链接；反向有12条审计记录的legacy ID不在当前缓存ID集合。expanded中1445条可直接连接原缓存ID，余11条不能靠这一字段完成。这里的“未链接”不等于丢失：可继续使用父ID和精确来源键，不能擅自补造映射。全部8007项显式链接账本见`raw_candidate_lineage.jsonl`。

原全量生成别名为DashScope `qwen3.7-max`；本地7B和27B是后续开发实验，不能归为原始8003池的生成模型。

主图复用1326条标准记录并恢复130条，其中98条原拒绝、27条原隔离、5条原准入。因此只有1331条能沿该版本父链接对应历史准入，1456不是1698的直接子集。130条采用独立有限原生角色契约，不能沿用旧蕴含分数当作重新验证。实际Claims为1400，旧摘要的1414是上下文组合口径。

## 2. 原文、页和证据回溯

仅使用构建集MP001—MP007、MP015—MP022。原始PDF共15份；本轮逐文件存在性及SHA256与保存文档哈希核对全部通过。解析资产`data/interim/parsed_pages/corpus_v2/{MPxxx}.pages.v2.jsonl`共1934个物理页，包含页文本、文本块、原生表格、单元ID、行/列/行组、bbox、来源元数据。未使用MP008及外部文档补充样本。

复用`scripts/run_evidence_contract_validation_experiments.py:audit_record`只读函数，显式经`load_provenance_schema`加载并规范化v3 Schema，重新检查当前全审计图：

| 检查 | 通过/8003 | 比例 | 限制 |
| --- | ---: | ---: | --- |
| 页对象可解析到 | 8003 | 100% | 有页不等于引文正确 |
| 来源字段/哈希格式/页面载荷哈希/来源匹配 | 各8003 | 各100% | 未证明关系语义 |
| 引文或表格证据可定位 | 6526 | 81.54% | 包含E3可回查内容，不代表可自动准入 |
| 两端可在定位证据中找到 | 5226 | 65.30% | 共现不证明关系 |
| 关系及Domain/Range合法 | 6711 | 83.86% | 不对语义类型作专家裁定 |
| E1/E2结构、两端、位置和来源契约全部通过 | 3956 | 49.43% | 仅构成结构/位置可用池 |

逐条见`candidate_locator_audit.jsonl`，非只读保存的旧valid标志。旧证据级别为E1 3670、E2 2761、E3 440、无已定等级1132。1934页中1532页有某种解析warning，但其中1227条是印刷页标签待审、694条是表格视觉布局待审，彼此重叠；不能称1532页解析失败。7页被标为无机器可读文本；并无8003条内“解析失败真值”字段。

expanded的1326条基线按既有位置契约回读，130条新记录按原生块/单元子跨度地址回读，1456条地址检查通过；`expanded_location_checks.jsonl`保留两种契约区别。后者不是重跑旧语义验证器。1400项Claim均关联至少1条实际断言，无缺证据Claim；不等于1456条事实或完整条件全部正确。

## 3. 不将8003条全部投入融合

下面是互斥的**程序阶段归因**，不是互斥事实错误标签：按Schema→位置/来源/E3→剩余支持/阈值→严格术语的固定优先级。

| 类别 | 记录数 | 后续用途 |
| --- | ---: | --- |
| Schema不合法 | 1292 | 错误诊断，不能直接作融合正例 |
| Schema合法但位置/来源/E1E2契约不完整 | 2755 | 定位、E3和来源差异诊断；不能直接宣称有有效证据 |
| 位置结构可用但旧支持/阈值等未准入 | 2258 | 551隔离+1707拒绝；仅可供受控重新核验/歧义研究 |
| 旧准入、严格中文发布未就绪 | 1490 | 包含后续标准治理回收，不能继续称全未发布 |
| 历史strict已发布 | 208 | 历史状态，不代表新主图规模 |
| 合计 | 8003 | 不混入64条接口拒绝 |

3956条可用池=1698准入+551隔离+1707拒绝。保存关系支持状态为1704 entailed、2252 undetermined；二者不是事实正负。旧全量重叠拒绝原因有evidence_invalid 4632、relation_not_entailed 2777、relation_type_invalid 1292、dual_qwen否决253等，不能相加。`candidate_flow_ledger.jsonl`和统计CSV分别保留互斥/重叠口径。

在固定1698旧证据集上，标准术语层保留1326，未发布372；strict只保留208，差1490。372和1490是不同发布政策的损失，不能相加。术语阻断不是该关系事实错误。候选具有可定位证据也不意味着被拒就是误拒。

## 4. 字段保存情况及缺口

`summary.json:field_counts`逐层统计字段存在和非空，重要区别如下：

- 两端源语、类型、关系、中文候选名、来源文档/物理页、来源族、证据文本、模型置信及验证/拒绝原因均有可回查载荷；原始缓存未经过审计的记录没有最终判定是正常的。
- 历史候选和1326条复用记录没有统一显式条件或时序结构；条件可能仍在端点、引文、章节、表格行中。缺字段≠语义丢失。
- 新130条有`conditions_source`和模态，但列表含fault/cause/remedy/check/local_source_context角色。这是460项上下文角色条目，不是460个真实if条件，也不证明完整时序绑定。
- 新图没有全图统一的显式极性字段，旧1326条新模态为`legacy_unspecified`。未知不能填成正向、必然或无条件。
- 来源族是人工注册的依赖代理，不是统计独立证明。`source_language=en`也可能覆盖MP016/MP019的多语言页，不能据元数据直接计语言重复次数。
- strict紧凑记忆145条E1有连续offset，63条E2连续offset为空；底层原生表格坐标存在不等于所有导出视图都有bbox。本轮未补造位置。

## 5. 实体、主张与多候选身份

历史实体ID由类型及术语ID或规范标签生成，Claim由有向实体对和关系生成，证据ID再包含页、引文及单元身份。见`stage03_schema_validation/deduplicator.py:stable_entity_id/stable_claim_id/stable_evidence_id/deduplicate_triples`。它实现稳定身份和精确主张—证据去重，不实现通用语义别名发现。

主图另用EXE/EXC/EXA命名空间。1326条复用记录根级ID仍有旧MPE/MPC，须使用`expanded_*`连接实际2150实体/1400Claim/1456断言；130新增采用新ID。断言文件未直接携带来源族，应与完整`source_records`按`expanded_assertion_id`连接。

历史审计实际7651 Claim，按本轮NFKC/空白/大小写规范化的类型—中文名—关系键重算为7600个主张族，其中51个键有多个旧Claim ID。历史1698相应为1650 ID/1646键（4个键多ID）。这是身份口径/术语变化候选，不是已经证明51次错误拆分。standard与expanded的规范键数恰等实际Claim数。

expanded有38项Claim关联多条断言，涉及94条记录；1362项仅1条。每条记录可沿发布记录→精确来源键或显式父ID→扩图输入→页/PDF追溯。`version_parent_crosswalk.jsonl`保留已核实的1456项父记录映射。它不是承诺所有raw缓存ID都原样保留；跨版本不能只按ID字符串或行号连接。

## 6. 生成流程与源码边界

| 环节 | 现有代码 | 本轮观察 |
| --- | --- | --- |
| 原生解析 | stage01_document_ingest/models.py、pdf_parser.py | 有布局与位置字段，识别结果仍会失败 |
| 候选及规范化 | stage02_triple_extraction/chinese_extraction_contract.py | 保留旧LLM模块；本轮不重抽 |
| 类型、位置、支持、状态 | stage03_schema_validation各validator及pipeline | 规则通过≠事实正确 |
| 标准中文发布 | run_local_full_terminology_experiment.py、run_silver_terminology_governance.py | 已有字典/局部一致性治理 |
| 身份/证据分层 | deduplicator.py、build_versioned_knowledge_graph.py | 同主张多断言，不消去来源 |
| 来源族指数 | stage04_graph_build/source_family_support.py | 族内max、top-B补零；不改准入 |
| 独立扩图 | build_rp1_graph_expansion_v1.py | 1326复用+130有限角色恢复；条件不入Claim身份键 |

RP2/RP3旧strict实验、教师、checkpoint、ONNX和模型均未改变。新主图作为后续默认知识源属于版本政策，不代表新版索引、参考、教师或蒸馏已经完成。

## 7. 证据完整性与统计限制

主图Claim的断言数分布为：1条1362项、2条30项、3条3项、4条3项、6条1项、7条1项；来源族代理数全部为1。没有无法连接的Claim，不能由此推断无语义损失。全部计数均指当前保存文件；输入来源清单和哈希见`source_manifest.json`，本轮没有补齐历史未保存的输出或构造专家标签。
