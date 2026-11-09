# RP1 offline_contract_v3

六个已读构建集开发页，复用 E0/E1 共 233 条真实响应，无新 API 请求。

- [结果说明](../../../../docs/research/RP1_OFFLINE_CONTRACT_V3_RESULTS_20261002.md)
- [操作约定与协议](../../../../docs/research/RP1_OFFLINE_CONTRACT_V3_PROTOCOL_20261002.md)
- [逐条可读账本](candidate_review.md)：233 条原始裁定、源文修复/隔离与 409 个证据片段。
- [原 85 项参考六列匹配](reference_review.md)：保留 3 项操作旁路、3 项未决，暂定核心分母 79。

`candidate_adjudications.jsonl` 是 AI 技术编修账本，按 ID 重放，**不是自主修复模型，也不是专家标签**。
`reference_matches_510.jsonl` 保存三组技术匹配；`auxiliary_reference_matches_36.jsonl` 保存原 18 项辅助参考的双臂响应位置。
`arm_decisions.jsonl` 保留 699 条留/隔离决策；`summary.json`、`page_summary.jsonl`、`scope_sensitivity.json` 分别保存总量、逐页与范围贡献分离。

A 原始输出，B 不读标签的自动约束筛查，C AI 源文编修。原输出、专家队列、旧图谱和所有已有实验均不改动。C 每个原始候选最多一个输出，未从参考/辅助响应补造新断言。

`adjudication_freeze.json` 冻结技术注释与来源；`arm_execution_freeze.json` 冻结统计程序；`preservation_before.json` / `verification.json` 核对既有 2008 文件及结果完整性；`delivery_manifest.json` 是最终交付文件哈希清单。

```bash
python scripts/verify_rp1_offline_contract_v3.py
```

门状态：**NOT_READY_FOR_HOLDOUT_OR_SCALING**。29 个保留页未开；独立专家评价与通用自动修复未完成，不扩大 API 抽取或发布新图。
