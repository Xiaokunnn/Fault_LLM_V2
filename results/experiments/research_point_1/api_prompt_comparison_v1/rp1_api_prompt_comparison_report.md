# RP1 Fixed-Page Real-API Comparison Report

## Protocol

- Model: `qwen3.7-max`, temperature 0.
- Frozen sample: the same 20 stratified, evidence-rich build-set pages for every method.
- Methods: B0, B1, B2, B3 and Ours.
- Labels: Silver only; no human expert review and no Gold labels.
- Statistical unit: page. The 95% intervals in `comparison_analysis.json` use 10,000 page-clustered bootstrap resamples.
- Held-out leakage check: MP009--MP013 are absent.

## Results

| Method | Raw | Normalized | Contract yield | Strict Silver | Silver/raw | Silver/normalized | Latency/page | Silver/min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 | 162 | 0 | 0.0% | 0 | 0.0% | 0.0% | 22.5s | 0.00 |
| B1 | 312 | 184 | 59.0% | 50 | 16.0% | 27.2% | 40.9s | 3.67 |
| B2 | 226 | 97 | 42.9% | 31 | 13.7% | 32.0% | 32.5s | 2.86 |
| B3 | 254 | 120 | 47.2% | 32 | 12.6% | 26.7% | 35.9s | 2.68 |
| Ours | 367 | 367 | 100.0% | 148 | 40.3% | 40.3% | 53.9s | 8.23 |

Ours produced 148 strict Silver assertions, 2.96 times the strongest count baseline (B1: 50). Its Silver acceptance rate over normalized candidates was 40.3%, an absolute gain of 8.37 percentage points over the strongest rate baseline (B2: 32.0%). Ours was slower per page, but its 8.23 accepted Silver assertions per API minute remained higher than every baseline.

The paired page-bootstrap differences are stored under `paired_ours_minus_baseline_ci95` in `comparison_analysis.json`. A difference is treated as statistically distinguishable at the descriptive 95% level only when its interval excludes zero; this is a clustered robustness analysis, not an expert-labelled accuracy test.

## Interpretation boundaries

1. The experiment supports improved structured-output compliance and page-grounded Silver evidence yield; it does not measure factual precision or engineering diagnostic accuracy.
2. B0's zero normalized output means its free-form proposals did not satisfy the executable evidence contract. It must not be interpreted as proving that every B0 semantic statement was false.
3. `chinese_graph_ready=0` is expected here because this experiment stops after strict evidence validation and does not run the independent terminology-release workflow. It does not invalidate the frozen 10/10 corpus evidence coverage or the existing Chinese release graph.
4. The 2/10 evidence coverage observed for Ours describes only this 20-page stratified experiment, not the complete 1889-page build corpus.
5. All outputs remain Silver and have not been reviewed by a marine engineering expert.
