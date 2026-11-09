# RP1 clause binding v1

Completed development-only paired filter/repair experiment on 233 existing assertions from six previously read pages. No API calls, held-out page access, graph publication, training or expert certification.

- [Protocol and theoretical scope](../../../../docs/research/RP1_CLAUSE_BINDING_V1_PROTOCOL_20261003.md)
- [Results and thesis scope](../../../../docs/research/RP1_CLAUSE_BINDING_V1_RESULTS_20261003.md)
- `execution_freeze.json`: code/input hashes before generation; `outputs.jsonl`: F/R, 466 decisions.
- `mechanism_events.jsonl`: 20 stage/candidate events involving 10 candidates.
- `AI_review.jsonl`: B/F/R, 699 disclosed same-assistant technical annotations. Evaluation only.
- `changed_record_review.jsonl`: original/proposed payloads, evidence and AI reasons for changed decisions.
- `evaluation_freeze.json`: source review and evaluation inputs frozen before aggregate metrics.
- `summary.json`, `reference_matches.jsonl`, `complete_page_summary.jsonl`: quantity, quality, one-to-one provisional-reference matches and all six pages including the background control.
- `development_gate.json`: development comparison passes; formal promotion remains NOT_ESTABLISHED.
- `verification.json`, `evaluation_verification.json`, `synthetic_tests.json`: deterministic/source checks, separate metric reconstruction and 14 synthetic tests.
- `independent_change_review_queue.jsonl`: 10 affected candidates with source witnesses and blank expert fields, no AI verdicts; purposive change review, not a representative accuracy sample.
- `preservation_before.json`: existing-file hashes; `delivery_manifest.json`: delivered files excluding the manifest itself.

B reuses v4.1 P1. F/R use the same detector; F overrejects one originally complete E1 record. Do not claim superiority over every possible stronger filter. All gains are on MP004 p10, a development page. Remaining known problems and pending independent evaluation must be disclosed. Existing artifacts must not be overwritten.
