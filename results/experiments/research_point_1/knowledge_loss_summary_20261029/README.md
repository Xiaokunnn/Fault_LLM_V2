# 2026-10-29 知识损失汇总

只读汇总30页审计、29页保留实验和最新10页局部ID实验，不新增API、修复运行或语义标签。

- `summary.json`：三批独立分母、损失类别与恢复证据。
- `loss_breakdown.csv`：数量、分母、比例及已有错误细类。
- `record_and_reference_ledger.jsonl`：721项分类发生，包括参考和候选，不是721条独立知识。
- `recovery_targets.jsonl`：3项30页中文发布参考、19条29页支持记录（其中8条核心）、3条10页接口记录。单位不同，不把25行相加为25条净新增知识；均未在本次执行修复。
- `source_manifest.json`：19个只读源文件SHA256及汇总脚本哈希。

正文见[汇总报告](../../../../docs/research/RP1_KNOWLEDGE_LOSS_SUMMARY_20261029.md)。

复算：`python scripts/aggregate_rp1_knowledge_losses.py`。
