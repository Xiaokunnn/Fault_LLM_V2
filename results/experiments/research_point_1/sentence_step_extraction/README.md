# 单句／步骤抽取实验

2026-10-13完成：缓存开发 → 方法冻结 → 源文参考固定 → 10次qwen3.8-max → 一层全量源文AI评价。整体FAIL，没有扩图或修改旧教师。

- `development/`：全部138条缓存菜单检查、原生位置回读、两个源文结构回归例，不是新模型质量结果。
- `validation/method.json`、`request_freeze.json`：冻结代码、模型、页面载荷与76项参考。
- `validation/api/`：10份完整原始响应及调用元数据。无重试、无额外审核API。
- `validation/decisions.jsonl`、`source_review.jsonl`、`records.csv`：162条全部保留，107程序通过、69源文支持、66联合。
- `validation/coverage_review.jsonl`：73项主图参考完整24、其余49不完整/表达错误，另3项控制。不是正式召回。
- `validation/quality_metrics.json`、`error_and_omission_summary.json`：质量、数量、错误放行、未决及漏抽。
- `preservation.json`、`validation/verification.json`：214个先前文件和真实源位置重建。

AI判断为Codex非盲源文阅读，不是专家事实真值。精确去重66不等于与旧图合并后的净新增66；没有应用图发布。完整说明见[报告](../../../../docs/research/RP1_SENTENCE_STEP_EXTRACTION.md)。

离线复算：`python scripts/summarize_rp1_steps.py`。不要重新执行prepare或execute，也不要改代码后重报本批成绩。
