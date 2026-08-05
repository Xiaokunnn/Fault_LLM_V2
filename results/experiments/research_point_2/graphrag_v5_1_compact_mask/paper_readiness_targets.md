# RP2 论文就绪门槛：marine_pump_rp2_graphrag_v5_1_compact_mask

所有证据与语义标签均为 Silver，未经领域专家审核。

| 方法 | P | F1 | 预算归一F1 | 平均引用 | 多引用率 | 逐候选契约 | 严格点支持 | 全原子主张支持 | 可回答回答率 | 不可回答拒答率 | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_dense_k4_compact | 0.856 | 0.233 | 0.300 | 1.682 | 0.500 | 1.000 | 0.946 | 0.955 | 0.647 | 1.000 | 579.386 |
| B4_role_k3_compact | 0.839 | 0.312 | 0.443 | 1.464 | 0.357 | 1.000 | 0.927 | 0.893 | 0.824 | 1.000 | 459.380 |
| Ours_v5_1_k3_compact | 0.818 | 0.370 | 0.525 | 1.636 | 0.455 | 1.000 | 0.889 | 0.848 | 0.971 | 1.000 | 490.811 |

## Ours_v5_1_k3_compact 门槛

- silver_citation_precision_macro: 0.818 >= 0.800 — PASS
- budget_normalized_silver_citation_f1: 0.525 >= 0.650 — FAIL
- dual_strict_point_support_rate: 0.889 >= 0.600 — PASS
- all_atomic_claims_strictly_supported_answer_rate: 0.848 >= 0.300 — PASS
- all_text_strictly_supported_answer_rate: 0.848 >= 0.300 — PASS
- answerable_answer_rate: 0.971 >= 0.850 — PASS
- unanswerable_abstention_rate: 1.000 >= 0.950 — PASS
- strict_contract_rate: 1.000 >= 0.950 — PASS
- p95_latency_ratio_vs_dense_k4_max: 0.847 <= 1.050 — PASS
