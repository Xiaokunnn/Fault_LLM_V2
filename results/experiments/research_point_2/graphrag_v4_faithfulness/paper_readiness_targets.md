# RP2 v4 论文就绪门槛

所有证据与语义标签均为 Silver，未经领域专家审核。

| 方法 | P | F1 | 预算归一F1 | 严格点支持 | 全原子主张支持 | 可回答回答率 | 不可回答拒答率 | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_dense_k4_guard | 0.865 | 0.163 | 0.210 | 0.962 | 0.938 | 0.471 | 1.000 | 7064.589 |
| B4_metapath_k3_guard | 0.885 | 0.260 | 0.370 | 0.967 | 0.962 | 0.765 | 1.000 | 5852.002 |
| A_guard_ours_v4_k3_no_guard | 0.862 | 0.307 | 0.436 | 0.844 | 0.828 | 0.853 | 1.000 | 6896.778 |
| Ours_v4_k3 | 0.862 | 0.307 | 0.436 | 0.906 | 0.897 | 0.853 | 1.000 | 6883.028 |

## Ours v4 门槛

- silver_citation_precision_macro: 0.862 >= 0.800 — PASS
- budget_normalized_silver_citation_f1: 0.436 >= 0.650 — FAIL
- dual_strict_point_support_rate: 0.906 >= 0.600 — PASS
- all_atomic_claims_strictly_supported_answer_rate: 0.897 >= 0.300 — PASS
- all_text_strictly_supported_answer_rate: 0.897 >= 0.300 — PASS
- answerable_answer_rate: 0.853 >= 0.850 — PASS
- unanswerable_abstention_rate: 1.000 >= 0.950 — PASS
- strict_contract_rate: 1.000 >= 0.950 — PASS
- p95_latency_ratio_vs_dense_k4_max: 0.974 <= 1.050 — PASS
