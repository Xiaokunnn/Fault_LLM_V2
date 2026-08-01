# 中间产物清理与保留策略

更新日期：2026-08-01

## 已删除

- `_tmp_venue_inspect/`：会议网页与表格检查临时目录，与论文实验无关。
- `tmp/pdfs/`：阅读规划PDF时生成的页面渲染缓存，可随时重建。
- `results/experiments/research_point_1/api_prompt_comparison_v1/*/extraction_run_summary.json`：B0–Ours仅本地dry-run形成的空摘要，不包含真实API结果，保留会造成“实验已完成”的误解。
- `data/interim/heldout_external/rp1_extraction_v1/extraction_run_summary.json`：外部抽取仅dry-run产生的空摘要，不是MP010–MP013真实模型结果。

## 必须保留

- `data/source_docs/`：原始PDF、来源URL、文档划分和文件哈希。
- `data/interim/parsed_pages/`：页码、正文、表格、bbox和页面哈希，是证据定位基础。
- `data/interim/candidate_triples/`：候选、Silver、隔离、拒绝及模型响应缓存，是8003条审计记录和图谱复现基础。该目录体积较大，但不能按“中间文件”直接删除。
- `data/kg/`：Schema、术语表、发布图谱、三元组和Silver基准。
- `results/experiments/research_point_1/`中真实构图质量、约束、来源族、CQ与消融结果。
- `results/experiments/research_point_2/`中结构检索先导实验；其定位虽已降级为先导实验，但仍是后续向量/7B正式实验的比较基线。
- `raw_responses/`中的真实API响应与裁决缓存：用于断点续跑、费用控制和可审计复现，不应删除。

## 后续清理规则

1. 只有满足“可由已提交代码确定性重建、没有真实API调用、没有唯一审计信息、没有被报告引用”四项条件的产物才可删除。
2. API响应、Silver决策和拒绝理由即使体积较大也必须保留。
3. 新实验的dry-run输出应写入 `tmp/`，避免与正式结果目录混放。
4. 每次正式实验冻结后，保留配置、汇总指标、逐查询结果、图表和输入哈希；重复的临时导出和渲染缓存可删除。
