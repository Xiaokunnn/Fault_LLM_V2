# RP2 论文就绪门槛：marine_pump_rp2_graphrag_v5_2_recall_cascade

所有证据与语义标签均为 Silver，未经领域专家审核。

| 方法 | P | F1 | 预算归一F1 | 平均引用 | 多引用率 | 逐候选契约 | 严格点支持 | 全原子主张支持 | 可回答回答率 | 不可回答拒答率 | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_dense_k4_cascade | 0.848 | 0.287 | 0.369 | 2.000 | 0.609 | 1.000 | 0.935 | 0.913 | 0.676 | 1.000 | 1418.583 |
| B4_role_k3_cascade | 0.845 | 0.372 | 0.529 | 1.793 | 0.586 | 1.000 | 0.904 | 0.862 | 0.853 | 1.000 | 1106.389 |
| Ours_v5_2_k3_cascade | 0.799 | 0.426 | 0.605 | 1.971 | 0.647 | 1.000 | 0.910 | 0.882 | 1.000 | 1.000 | 910.805 |

## Ours_v5_2_k3_cascade 门槛

- silver_citation_precision_macro: 0.799 >= 0.800 — FAIL
- budget_normalized_silver_citation_f1: 0.605 >= 0.650 — FAIL
- dual_strict_point_support_rate: 0.910 >= 0.600 — PASS
- all_atomic_claims_strictly_supported_answer_rate: 0.882 >= 0.300 — PASS
- all_text_strictly_supported_answer_rate: 0.853 >= 0.300 — PASS
- answerable_answer_rate: 1.000 >= 0.850 — PASS
- unanswerable_abstention_rate: 1.000 >= 0.950 — PASS
- strict_contract_rate: 1.000 >= 0.950 — PASS
- p95_latency_ratio_vs_dense_k4_max: 0.642 <= 1.050 — PASS
- cascade_silver_relevant_promoted_count_min: 10.000 >= 8.000 — PASS
