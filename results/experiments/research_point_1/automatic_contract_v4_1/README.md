# RP1 automatic_contract_v4_1

[完整结果](../../../../docs/research/RP1_AUTOMATIC_CONTRACT_V4_RESULTS_20261003.md) · [原协议](../../../../docs/research/RP1_AUTOMATIC_CONTRACT_V4_PROTOCOL_20261003.md) · [有限解析修订](../../../../docs/research/RP1_AUTOMATIC_CONTRACT_V4_1_AMENDMENT_20261003.md)

修订版P1条件完整核心记录E0/E1=57/74，完整参考匹配41/79、58/79。达到相对旧B的开发改善判据；仍有问题/未决放行，专家准确率/召回率和泛化未成立，不扩大API或发布图。

- `automatic_outputs.jsonl`：P0/P1共466条自动决策，完整保存载荷、规则、出处及隔离原因。
- `AI_source_review_466.jsonl`：独立于运行模块的本助手技术复核，非独立专家。
- `summary.json`、`page_summary.jsonl`、`reference_matches_340.jsonl`：量质、逐页与参考匹配。
- `page_coverage_completed.jsonl`：补上E0背景页无断言的NA空行，原统计不改。
- `patch_impact.json`：只改变预先声明4个输出，其余462个逐值相同。
- `verification.json`：19个合成边界测试，466次逆序重放、466次ID改名不变性、1082个见证回读。
- `independent_review_queue.jsonl`：233项源文复核入口，专家填写字段留空，不以AI代填。
- `promotion_gate.json`：开发改善通过，正式方法推广仍NOT_ESTABLISHED。

独立评审应先阅读[不带候选标签的六页源文](../adjudication_targeted_v2_1/expert_source_only.md)，再评审自动候选；旧85项AI参考非穷尽、非专家真值。29个保留页未打开。

```bash
python scripts/verify_rp1_automatic_contract_v4.py
```
