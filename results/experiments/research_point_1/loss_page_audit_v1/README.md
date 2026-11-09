# RP1 构建集损失与页面漏抽试审 v1

日期：2026-09-29。单一 AI 审阅者初审；**无领域专家真值，无新抽取/教师调用，无上游修改**。

结果解释以 [中文报告](../../../../docs/research/RP1_LOSS_AND_PAGE_AUDIT_V1_RESULTS_20260929.md) 为准；初始规则见 [协议](../../../../docs/research/RP1_LOSS_AND_PAGE_AUDIT_V1_PROTOCOL_20260929.md)。

## 先读这些文件

| 文件 | 用途 |
|---|---|
| `summary.json` | 97 条记录、30 页、210 条候选与 245 项参考的汇总 |
| `record_findings.csv` / `.jsonl` | 逐条语义初审、主因、原失败标志、正确发布层去向 |
| `record_breakdowns.csv` | 主样本/补样分别按文档、版式代理、关系和解释分类 |
| `record_failure_flag_breakdowns.csv` | 原失败标志 × 决策，标志可重叠，不可相加 |
| `page_summary.csv` | 包含所有零目标页和未决页的逐页结果 |
| `page_match_findings.jsonl` | 参考知识与候选 ID、门控和发布层的逐项对应 |
| `page_candidate_findings.jsonl` | 全部 210 条页面候选的正确性初审 |
| `verification.json` | 抽样、来源、封存顺序、连接和计数复核；2680 个既有文件未变 |

**重要纠错：** 初始协议假设跨阶段 evidence ID 不变，但中文规范化重建了 ID。
`record_review_packets.jsonl` 内旧 `published` 字段已失效，禁止用于分析。以
`corrected_publication_membership.jsonl` 和最终 `record_findings.*` 为准。
详见 `membership_join_correction.json`。原快照、旧包、样本和全部冻结源文件均保留；
新连接使用文档、物理页、关系、原文端点和完整引用组成的唯一源键，独立验证 208/620/1326。
`protocol_snapshot.md` 中的原 ID 假设也被这项有记录的更正取代；没有静默修改封存协议。

## 抽样、源文与人工可追查材料

- `input_manifest.json`、`supplemental_input_manifest.json`：主输入、追加读取的旧响应和原提示/页面计划的哈希。
- `preservation_before.json`：开始时旧资产保全快照。快照也含两个本轮刚新建的文件；核验单独区分它们与既有文件。
- `record_population_frame.jsonl`、`population_breakdowns.json`：8003 条候选总体及旧决策/标志分布。
- `record_sample_manifest.jsonl`、`record_sampling_summary.json`：90 条概率样本 + 7 条定向补样、概率及权重。
- `page_sample_manifest.jsonl`：1934 页中按文档×解析表格状态固定抽出的 30 页。
- `pages_source_only.jsonl` / `.md`、`page_renders/`：不含候选和自动判定的页面包及实际 PDF 页面图。
- `page_reference_annotations.jsonl`、`page_reference_seal.json`、`comparison_opened.json`：先验参考、封存哈希和比较开放时间。
- `record_semantic_annotations.jsonl`、`record_visual_followup.jsonl`、`record_renders/`：97 条初审及 4 条补充视觉判断；聚合时以后者补充初审。
- `page_candidate_comparison_packets.jsonl`、`page_candidate_index.jsonl`：同页全部审计候选与 C001–C210 索引。
- `page_candidate_semantic_annotations.jsonl`、`page_reference_matches.jsonl`：后续语义判断和匹配原始记录。
- `page_raw_comparison_packets.jsonl`、`selected_raw_responses.jsonl`、`selected_original_page_plan.jsonl`：旧全量抽取候选、响应和页面计划。
- `candidate_lineage_audit.json`：8007 行 raw 与 8003 条审计池的非一一对应，以及所选页 206/210 差异。
- `selected_pre_audit_rejections.jsonl`：为空；旧全量运行入库前拒绝清单在这些页面没有记录。

## 解读限制

主样本按文档和决策平衡，原比例不能外推总体；7 条覆盖补样无概率权重。
`descriptive_sampling_weight_totals.json` 只是 AI 标签的加权描述，不是专家准确率。
表格/正文是旧字段代理，不能直接解释为真实版式效果对比。

245 项参考仅覆盖 11 类核心诊断关系，是非穷尽的 AI 清单。
93 项明确匹配、75 项部分/相关表达、77 项未识别到对应；75 项不能全算漏抽，
77 项中还有 7 项与旧模型的任务范围解释不一致。解盲后还发现参考清单漏纳的有效候选，
原分母保持封存，未反向用输出补真值。因此 93/245 不能作为正式召回率。
MP020 p26 贡献 94 项参考，各知识项并不独立。

`record_adjudication_queue.csv`、`page_reference_adjudication_queue.csv`、
`page_candidate_adjudication_queue.csv` 是待二次裁定队列，均为 pending，不代表已有人类评审。
队列显示初审标签；如需盲法第二标注，先只使用 `pages_source_only.jsonl` 和范围协议。

## 已执行流程与复现注意

1. `scripts/audit_rp1_loss_pages.py prepare`：固定抽样、快照、源文包。
2. 读取 30 页源文和 PDF 页面图，书写 `source_first_annotation_notes.py` 中的逐页人工编码内容。
3. `scripts/audit_rp1_loss_pages.py seal-pages` 后才执行 `open-records`。
4. 逐条审阅 97 条记录与 210 条页面候选，书写语义记录和 `page_comparison_review.py` 中的匹配判断。
5. 阅读已有响应和原任务范围，查清来源连接，保存发布连接纠错及补充输入哈希。
6. `python scripts/summarize_rp1_loss_pages.py`：聚合已保存的判断。
7. `python scripts/verify_rp1_loss_pages.py`：独立复算抽样、映射、汇总和保全。
8. `python scripts/export_rp1_audit_review_queues.py`：导出失败标志分解和待复核队列。

以上脚本对应仓库根目录；实际参数定义以脚本为准。原始准备脚本保存在
`prepare_script_snapshot.py`，当前准备脚本另外包含已说明的发布连接修正。
标注脚本保存的是审阅者显式写出的判断，**不是自动产生独立语义真值的算法**。
产物采用独占创建，拒绝覆盖；流程已经完成，不要在原目录重跑。再做研究必须使用新版本目录，
保留本次盲法时序、主观判读和纠错记录，也不能重跑旧教师/基线来补本轮指标。
