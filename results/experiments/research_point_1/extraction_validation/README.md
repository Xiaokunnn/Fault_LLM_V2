# RP1小范围API抽取验证：已完成，75%目标未通过

[结果报告](../../../../docs/research/RP1_EXTRACTION_VALIDATION_RESULTS.md)为当前入口。

10页、224条收到的记录，129条程序通过（57.6%），对应129种精确去重关系。固定60条AI源文抽查为S25/E30/U5；其中23条同时通过程序和源文要求（38.3%）。这些比例均不构成人工准确率或全体记录可用保证。本批没有发布最终应用图。

- `extracted_records.csv`：全部224条记录及程序状态、抽查标签；not_sampled表示未抽查。
- `api/`：10份原始完整响应、解析结果及所有请求状态，包含一次超时及显式重试。
- `method.json` / `selection.json` / `request_freeze.json`：固定方法、选页和请求。
- `sources.jsonl` / `source_inventory.jsonl`：目标/前页原文及调用前65项源文清单。
- `candidates.jsonl` / `structural_summary.json`：本地全部决定，不合约和未决记录仍保留。
- `review_sample.jsonl` / `source_review.jsonl`：固定60条样本及逐条AI理由。
- `coverage_review.jsonl` / `metrics.json`：检查清单匹配与最终指标。
- `compiler_correction.json` / `compiler_comparison.json`：多块读取实现修正及修正前后统计。原实现与决定保存在logs。
- `transport_retry.json`：唯一超时页显式重试的原因、次数和边界。
- `verification.json` / `completion.json`：完整性校验和最终交付状态。

无网络复算：

```bash
python scripts/verify_rp1_extraction_validation.py
PYTHONPATH=src .venv/bin/python -m pytest -q tests/unit/test_rp1_contextual_extraction.py
```

已完成请求与结果具有防覆盖保护。不要重复prepare/collect/summarize或调用API覆盖这些结果。运行脚本`validate_rp1_extraction.py`默认需要明确子命令；网络调用只用于已授权请求。本轮API密钥未写入代码、响应、日志或配置。
