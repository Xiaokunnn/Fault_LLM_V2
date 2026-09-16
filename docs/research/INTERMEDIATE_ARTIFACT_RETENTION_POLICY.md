# 中间产物清理与保留策略

更新日期：2026-09-16

当前研究叙述不再把 `Silver` 作为方法创新名称。本文档和物理目录中保留该词仅用于复现历史命名；对应资产应理解为“自动证据合格记录”或“自动评价标签”，不等于专家真值。

## 2026-08-13 清理

- 删除 `.tmp/` 与 `tmp/` 中可重建的论文渲染、Word QA、PDF抽文、汇总复算和旧图构建测试缓存；保留已被Git跟踪的两组RP2 smoke复现实验。
- 删除 `papers/` 中 LaTeX 的 `.aux/.bbl/.blg/.fdb_latexmk/.fls/.out/.synctex.gz/.xdv` 构建文件及 `_qa_*`、`_work_v5` 渲染缓存；保留主 `.tex/.pdf`、参考文献、图件、会议模板和历史正文版本。
- 将过期规划、构图阶段页计划及RP2 v3–v5阶段报告移入 `docs/archive/`，并在归档索引中声明不得作为当前状态入口。
- 当时保留了存在用户未提交修改的 `RP2_D2AI2026_中文初稿_v4.docx`，未对其移动、重写或删除。

## 2026-09-16 论文版本精简

- 在工作区无未提交修改的前提下，按用户要求删除 RP1 中文 v1–v4和 RP2 中文 v1–v5 历史草稿。
- 删除旧 Word/Markdown、preview、`_work_v4` 页面渲染工作区、重复同哈希 PDF 和已被最终上传包取代的重复构建入口。
- 删除仅用于生成上述历史 Word 草稿、且默认输入已不存在的两份构建脚本。
- 保留 RP1 项目主稿、中文 v5 正式稿、R1 修订投稿包和其回复/摘要；保留 RP2 英文终稿和中文 v6 作者信息更新稿。
- 被删除文件均曾受 Git 跟踪，必要时可从版本历史恢复。

## 已删除

- `_tmp_venue_inspect/`：会议网页与表格检查临时目录，与论文实验无关。
- `tmp/pdfs/`：阅读规划PDF时生成的页面渲染缓存，可随时重建。
- `results/experiments/research_point_1/api_prompt_comparison_v1/*/extraction_run_summary.json`：B0–Ours仅本地dry-run形成的空摘要，不包含真实API结果，保留会造成“实验已完成”的误解。
- `data/interim/heldout_external/rp1_extraction_v1/extraction_run_summary.json`：外部抽取仅dry-run产生的空摘要，不是MP010–MP013真实模型结果。
- `data/interim/page_index/marine_pump_pages_v1.sqlite`及摘要：可由`corpus_v2`确定性重建的旧词法页面索引；正式GraphRAG v2将改建向量索引。
- `results/experiments/research_point_2/development_v1/retrieval_results.jsonl`：30次重复产生的逐请求调试明细，约8MB；汇总指标和报告已保留，需要时可用`--save-results`重新生成。
- `qwen3_7_max_corpus_retrieval_v2_large_audit_dry_run/`：不含真实模型响应的空dry-run目录。
- 项目内`__pycache__`、`.pytest_cache`：Python和测试缓存，可自动重建。

## 必须保留

- `data/source_docs/`：原始PDF、来源URL、文档划分和文件哈希。
- `data/interim/parsed_pages/`：页码、正文、表格、bbox和页面哈希，是证据定位基础。
- `data/interim/candidate_triples/`：候选、自动证据合格、隔离、拒绝及模型响应缓存，是8003条审计记录和图谱复现基础。该目录体积较大，但不能按“中间文件”直接删除。
- `data/kg/`：Schema、术语表、发布图谱、三元组和自动证据评价集。
- `results/experiments/research_point_1/`中真实构图质量、约束、来源族、CQ与消融结果。
- `results/experiments/research_point_2/`中结构检索先导实验；其定位虽已降级为先导实验，但仍是后续向量/7B正式实验的比较基线。
- `raw_responses/`中的真实API响应与裁决缓存：用于断点续跑、费用控制和可审计复现，不应删除。

## 后续清理规则

1. 只有满足“可由已提交代码确定性重建、没有真实API调用、没有唯一审计信息、没有被报告引用”四项条件的产物才可删除。
2. API响应、自动门控决策和拒绝理由即使体积较大也必须保留。
3. 新实验的dry-run输出应写入 `tmp/`，避免与正式结果目录混放。
4. 每次正式实验冻结后，保留配置、汇总指标、逐查询结果、图表和输入哈希；重复的临时导出和渲染缓存可删除。
