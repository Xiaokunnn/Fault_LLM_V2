# Local blinded model second opinion

A fixed 22-item development review (10 targeted changes, 12 page-stratified controls). Runtime sees assertions and complete six-page source material only; prior AI labels and private mapping are joined after all inference finishes. Qwen2.5-7B-Instruct runs locally on CPU FP32 with frozen weights and a forced S/N/U next-token decision. Conditional scores are not calibrated confidence.

This is a separate model call, not independent human or expert review. Both extractor and reviewer belong to the Qwen family, so correlated errors remain possible. Do not show operator_only_comparison.jsonl or operator_only_disagreements.json to a human reviewer before their own source-first assessment.

freeze.json seals model settings, prompt, inputs and runner; runtime.json records weight hashes; every IRxxx.json stores a response and prompt hash. No external API, old teacher rerun or holdout page read occurs. run.log preserves progress/errors. Completion and summary are written only when the corresponding stages actually finish.
