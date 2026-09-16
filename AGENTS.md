# Fault_llm_v2 agent handoff

## Current research structure

- Research point 1 is automated evidence-quality gating and traceable knowledge-graph construction without triple-by-triple human approval.
- Research point 2 is budget-constrained hybrid evidence selection and verifier-workload control. One-hop graph propagation is a tail-recall signal, not the main source of mean improvement.
- Research point 3 is a callable Lightweight Evidence Controller (LEC) that distills ranking, binary support, active underfilling, and cost-sensitive routing into a small edge tool.
- The active implementation target is research point 3. Research points 1 and 2 are frozen upstream teachers and must not be silently changed to improve RP3.
- The object remains the ship engine-room pump system. The sibling `Edge_Fault_LLM` directory is read-only prototype reference.

## Sources of truth

- RP1 claims and numbers come first from `papers/ICSMD_2026/RP1_ICSMD2026_English_Final.tex` and its frozen experiment assets.
- RP2 claims and numbers come first from `papers/D2AI_ICDM_2026/RP2_D2AI2026_English_Final_v1.tex`, `docs/RP2_V6_EQUAL_BUDGET_PROTOCOL.md`, and `configs/frozen/rp2_v6_paper_evidence_freeze.json`.
- The current three-point plan is `docs/research/MASTER_THESIS_THREE_RESEARCH_POINTS_PLAN.md`.
- The current RP3 comparison matrix and ordered backlog are `docs/RP3_EXPERIMENT_BASELINES_AND_TODO.md`.
- Files under `docs/archive/` and old v1-v5 protocols are historical reproduction records, not current project status.

## Terminology and evidence boundary

- Do not use “Silver” as the current research-point name, claimed innovation, or shorthand for truth quality.
- Use: candidate record, automatically evidence-qualified record, quarantined record, rejected record, automatic benchmark label, or teacher-generated supervision.
- Historical filenames, directories, schemas, status codes, paper text, and frozen configs containing `silver` remain unchanged for reproducibility.
- Automatically evidence-qualified means only that a record passed the declared executable evidence contract. It is not expert-confirmed factual accuracy, diagnostic accuracy, or an engineering safety guarantee.
- No triple-by-triple domain-expert review has been performed. Never call automatic records Gold or human ground truth.
- The canonical semantic graph is Chinese. Source-language surfaces, verbatim evidence, physical PDF page, URL, document/page hashes, scope, and all location/provenance fields that actually exist must remain unchanged. The current strict-208 source records contain character offsets but no bbox; preserve and disclose that absence instead of inventing boxes or claiming complete bbox retention.

## Frozen corpus split

- Primary graph build set: MP001–MP007 and MP015–MP022 (15 documents, 1934 physical pages).
- Development only: MP008. It must not fill build coverage or enter the primary graph.
- External evaluation only: MP009–MP013. They must not enter the primary graph, RP3 training, curriculum design, prompt/schema tuning, thresholds, retrieval parameters, or router calibration.
- MP010–MP013 were processed once after upstream freezing and remain external evaluation assets only.
- MP014 is excluded because it is an offshore ESP signal dataset rather than a ship engine-room pump document-evidence source.

## Current frozen assets

- RP1 full audit: 8003 records = 1698 automatically evidence-qualified, 881 quarantined, 5424 rejected.
- RP1 terminology layers: strict 208 evidence records, conservative 620, standard 1326.
- The root `data/kg/marine_pump/triples/KG_v1_validated` is the strict 208-record graph used by the RP2 v6 paper.
- The 620- and 1326-record graphs are terminology-governance experiment assets. They are not interchangeable with the 208-record RP2 teacher graph.
- RP2 v6 uses 40 controlled queries with known fault scope and diagnostic role. It is not open-ended fault identification, and its output is a single-role set of evidence-linked atomic suggestions rather than a complete diagnosis card.

## Current RP3 execution status (2026-09-17)

- The model-capable server checkout is `~/08-zxk/Fault_LLM_V2`. Code is synchronized through `origin/main`; use Git pull/push rather than upload patch archives unless Git is unavailable.
- `TeacherGraph_RP3_v1` has been rebuilt and frozen on the server. Its compact memory reports 208 evidence records, 203 claims, 14 documents, 10 source families and 38 fault-role buckets. The 40 original controlled queries are split into 32 build-train and 8 group-disjoint build-validation traces.
- MP008 development preparation completed all 40 verifier rows. Training and MP008 feature bundles were generated separately with explicit `training` and `development` purposes.
- The baseline `lec_v1` completed training, route fitting, FP32 ONNX export and static INT8 QDQ quantization. The quantized controller has 40 QDQ nodes and was checked on 40 MP008 representative inputs.
- Baseline route rollouts show teacher-relative exact selection agreement of 11/32 on build-train and 1/8 on build-validation. Route targets are train: 11 answer, 16 fallback, 5 abstain; validation: 1 answer, 6 fallback, 1 abstain.
- Baseline post-INT8 MP008 calibration failed closed: raw route argmax counts are 26 fallback and 14 abstain, with zero answer predictions and zero feasible accepted answers. No deployable `calibration_manifest.json` exists, so baseline `evaluate` and edge deployment are blocked by design.
- The current next experiment is the prespecified build-set evidence-removal arm: run `bash scripts/run_rp3_experiments.sh augment`, then train with `configs/research_point_3/lec_train_augmented_v1.json` into `results/experiments/research_point_3/lec_augmented_v1`. Preserve `lec_v1` as the non-augmented baseline.
- MP008 must not be used to change model hyperparameters, gradients, early stopping or model selection. The augmented arm keeps the baseline model/training settings and uses only prespecified build-set interventions with frozen 7B replay.

## Research point 3 gates

1. Freeze one explicit `TeacherGraph_RP3_v1` on the strict 208-record graph actually used by RP2 v6, with input paths, hashes, 208 evidence/203 claim/281 entity counts, vector index, model versions, and replay results. The 620/1326 layers are post-freeze tier-shift stress tests, not alternative main teachers.
2. Rebuild and replay the RP2 selector, verifier, and abstention policy on that exact graph before exporting teacher traces. This has completed on the model-capable server; other checkouts must still verify the frozen manifests and must not synthesize missing assets.
3. Freeze a complete diagnosis-card schema. Do not call the existing RP2 single-role JSON a complete card.
4. The main student is a four-head LEC (rank/pointer, binary support, field/underfill, three-action route), target <50M parameters and ONNX INT8. Keep deterministic text rendering as a rule component.
5. Qwen2.5-3B-Instruct INT4 is an optional edge dialogue/tool-calling shell; 1.5B and 7B are shell capacity bounds, not the main distilled object. Thresholds must be recalibrated after any quantization.
6. Evidence-removal/interference training requires the student to observe a bounded candidate signature or availability mask. A fully closed-book student cannot claim evidence-set intervention sensitivity.
7. Online actions are student answer, full RP2 teacher fallback, or abstain/human review. An ID-addressed local evidence memory is bounded evidence access, not retrieval-free inference.
8. Do not motivate RP3 by claiming the graph cannot fit on the edge; the evidence store is small. Measure savings from avoiding embedding, candidate scoring, long prompts, and repeated 7B verification.
9. A real edge-deployment claim requires measurements on target hardware. RTX 5880 resource limiting is only a resource-constrained simulation.
10. Build-set group-disjoint validation is used for early stopping/model selection. MP008 is reserved only for support/route thresholds and post-quantization calibration; it must not contribute gradients, early stopping, or model selection.

## Preservation and cleanup

- Never delete original PDFs, parsed pages, real API responses/caches, candidate decisions and failure reasons, frozen graph assets, frozen experiment outputs, or the two paper source trees.
- Generated render/QA caches and LaTeX build intermediates may be deleted when the final source and PDF are preserved.
- Preserve existing user modifications in a dirty worktree. In particular, do not overwrite or move an already modified paper draft.
- Before destructive cleanup, resolve explicit absolute targets inside the repository and verify that they are reproducible caches.
- Server-generated teacher caches, MP008 responses, checkpoints, ONNX files, calibration-search reports and experiment logs are research records. Do not remove them when synchronizing code with Git.
