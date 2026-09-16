# RP1 evidence-contract validation experiments

This report evaluates executable evidence-contract behaviour only. It does not measure domain truth, factual accuracy, or expert agreement. No model API or human expert review was used.

## Experiment A: all-candidate locator and provenance audit

| Decision group | Records | Page resolved | Source metadata match | Evidence located | Endpoints located | Locator contract pass |
|---|---:|---:|---:|---:|---:|---:|
| evidence_qualified | 1698 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| quarantined | 881 | 100.00% | 100.00% | 100.00% | 100.00% | 62.54% |
| rejected | 5424 | 100.00% | 100.00% | 72.77% | 48.80% | 31.47% |

`locator_contract_pass` requires a current physical-page object, complete and matching provenance, valid page-text hash, locatable evidence, and both endpoints within that evidence. E2 records additionally require resolvable parser cell identifiers, aligned rows/row groups, and in-page bounding boxes.

## Experiment B: controlled contract fault injection

| Mutation type | Injected | Detected | Missed | Detection rate |
|---|---:|---:|---:|---:|
| document_hash_corrupted | 1698 | 1698 | 0 | 100.00% |
| endpoint_evidence_truncated | 1547 | 1547 | 0 | 100.00% |
| evidence_payload_removed | 1698 | 1698 | 0 | 100.00% |
| page_hash_corrupted | 1698 | 1698 | 0 | 100.00% |
| page_locator_shifted | 1698 | 1698 | 0 | 100.00% |
| relation_tail_type_corrupted | 1698 | 1698 | 0 | 100.00% |
| source_family_removed | 1698 | 1698 | 0 | 100.00% |
| source_url_removed | 1698 | 1698 | 0 | 100.00% |
| table_bbox_out_of_bounds | 148 | 148 | 0 | 100.00% |
| table_cell_id_corrupted | 148 | 148 | 0 | 100.00% |

Overall, 13729/13729 injected violations were detected (100.00%).

## Interpretation boundary

A detected mutation means that a deliberately broken structural, locator, or provenance requirement failed the executable contract. It does not show that the underlying engineering assertion is objectively true. Semantic errors outside the declared contract, including subtle negation, modality, or applicability-scope changes, are not covered by this experiment.
