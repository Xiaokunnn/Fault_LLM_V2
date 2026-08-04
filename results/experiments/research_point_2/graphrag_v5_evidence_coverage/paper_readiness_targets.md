# RP2 论文就绪门槛：marine_pump_rp2_graphrag_v5_evidence_coverage

所有证据与语义标签均为 Silver，未经领域专家审核。

| 方法 | P | F1 | 预算归一F1 | 平均引用 | 多引用率 | 逐候选契约 | 严格点支持 | 全原子主张支持 | 可回答回答率 | 不可回答拒答率 | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_dense_k4_coverage_guard | 0.929 | 0.105 | 0.134 | 1.143 | 0.143 | 0.300 | 0.875 | 0.857 | 0.206 | 1.000 | 11537.156 |
| B4_role_k3_coverage_guard | 0.808 | 0.124 | 0.177 | 1.385 | 0.385 | 0.525 | 0.944 | 0.923 | 0.382 | 1.000 | 11317.516 |
| A_ours_v5_k3_coverage_no_guard | 0.906 | 0.231 | 0.328 | 1.312 | 0.312 | 0.425 | 0.762 | 0.750 | 0.471 | 1.000 | 11265.390 |
| Ours_v5_k3_coverage_guard | 0.906 | 0.216 | 0.307 | 1.188 | 0.188 | 0.425 | 0.947 | 0.938 | 0.471 | 1.000 | 11216.881 |

## Ours_v5_k3_coverage_guard 门槛

- silver_citation_precision_macro: 0.906 >= 0.800 — PASS
- budget_normalized_silver_citation_f1: 0.307 >= 0.650 — FAIL
- dual_strict_point_support_rate: 0.947 >= 0.600 — PASS
- all_atomic_claims_strictly_supported_answer_rate: 0.938 >= 0.300 — PASS
- all_text_strictly_supported_answer_rate: 0.938 >= 0.300 — PASS
- answerable_answer_rate: 0.471 >= 0.850 — FAIL
- unanswerable_abstention_rate: 1.000 >= 0.950 — PASS
- strict_contract_rate: 0.425 >= 0.950 — FAIL
- p95_latency_ratio_vs_dense_k4_max: 0.972 <= 1.050 — PASS
