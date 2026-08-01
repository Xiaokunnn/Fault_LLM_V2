from __future__ import annotations

import copy
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_research_point_1_graph_quality_v1 import (  # noqa: E402
    build_closure_summary,
)


VALIDATED_HASHES = {
    "entities.jsonl": "1" * 64,
    "claims.jsonl": "2" * 64,
    "evidence_assertions.jsonl": "3" * 64,
    "claim_evidence_links.jsonl": "4" * 64,
    "source_records.jsonl": "5" * 64,
}
RAW_SOURCE_SHA256 = "6" * 64
INPUT_REPORTS = {
    "cq_v1": {
        "path": "results/cq.json",
        "sha256": "a" * 64,
        "size_bytes": 100,
    },
    "source_family_support_v1": {
        "path": "results/support.json",
        "sha256": "b" * 64,
        "size_bytes": 200,
    },
    "constraint_report_v1": {
        "path": "results/constraints.json",
        "sha256": "c" * 64,
        "size_bytes": 300,
    },
}


def _reports() -> tuple[dict[str, object], ...]:
    cq = {
        "evaluation": {"graph_version": "KG_v1_validated"},
        "input_graph": {"file_sha256": dict(VALIDATED_HASHES)},
        "aggregate": {
            "overall": {
                "cq_count": 40,
                "answerable_cq_count": 39,
                "traceable_structure_answerability": 0.975,
            }
        },
        "task_results": [
            {
                "cq_id": "CQ-X",
                "fault_id": "fault",
                "fault_name_zh": "故障",
                "role": "inspection",
                "role_name_zh": "检查",
                "structurally_answerable": False,
                "unanswerable_reason_codes": [
                    "no_legal_semantic_path"
                ],
            }
        ],
    }
    support = {
        "budget": 2,
        "input_provenance": {
            "path": "data/kg/marine_pump/triples/KG_v1_raw/source_records.jsonl",
            "source_records_sha256": RAW_SOURCE_SHA256.upper(),
            "size_bytes": 123,
        },
        "claim_summary": {
            "eligible_assertion_count": 10,
            "claim_count": 9,
            "claims_with_at_least_two_families": 0,
            "support_index": {"mean": 0.4, "median": 0.45},
        },
        "replication_invariance_experiment": {
            "invariance_passed": True,
            "maximum_absolute_index_delta": 0.0,
        },
        "multi_document_same_family_audit": {
            "multiple_document_claim_count": 2,
            "multiple_document_single_family_claim_count": 2,
            "multiple_document_multiple_family_claim_count": 0,
            "all_observed_multiple_document_claims_are_single_family": True,
            "claims": [],
        },
    }
    constraints = {
        "validator_kind": "custom_python_graph_constraint_profile",
        "summary": {
            "checks": 36,
            "failed_checks": 1,
            "release_blocking_checks": 0,
            "release_blocked": False,
        },
        "packages": {
            "KG_v1_validated": {
                "input_files": {
                    layer: {"sha256": VALIDATED_HASHES[filename]}
                    for layer, filename in (
                        ("entities", "entities.jsonl"),
                        ("claims", "claims.jsonl"),
                        (
                            "evidence_assertions",
                            "evidence_assertions.jsonl",
                        ),
                        (
                            "claim_evidence_links",
                            "claim_evidence_links.jsonl",
                        ),
                        ("source_records", "source_records.jsonl"),
                    )
                }
            },
            "KG_v1_raw": {
                "input_files": {
                    "source_records": {
                        "sha256": RAW_SOURCE_SHA256
                    }
                }
            },
        },
    }
    return cq, support, constraints


class ResearchPointOneGraphQualityRunnerTests(unittest.TestCase):
    def test_summary_separates_pipeline_readiness_from_completion(
        self,
    ) -> None:
        cq, support, constraints = _reports()

        result = build_closure_summary(
            cq,
            support,
            constraints,
            input_reports=INPUT_REPORTS,
        )

        self.assertTrue(
            result["readiness"][
                "pipeline_ready_to_start_experiments"
            ]
        )
        self.assertFalse(result["readiness"]["method_evidence_complete"])
        self.assertFalse(result["readiness"]["research_point_1_complete"])
        self.assertNotIn(
            "ready_for_baseline_and_ablation_experiments",
            result["readiness"],
        )
        self.assertFalse(
            result["readiness"]["full_40_cq_structural_coverage"]
        )
        self.assertEqual(
            result["cq_v1"]["unanswerable_tasks"][0]["cq_id"],
            "CQ-X",
        )
        self.assertFalse(
            result["readiness"][
                "natural_cross_family_claim_corroboration_observed"
            ]
        )
        self.assertTrue(
            result["readiness"][
                "observed_same_family_multi_document_property_verified"
            ]
        )
        self.assertEqual(
            result["source_family_corroboration_v1"][
                "observed_multiple_document_single_family_claim_count"
            ],
            2,
        )
        self.assertTrue(
            result["cross_report_graph_input_consistency"]["passed"]
        )
        self.assertEqual(
            result["input_reports"]["cq_v1"]["sha256"],
            "a" * 64,
        )

    def test_graph_hash_mismatch_fails_closed(self) -> None:
        cq, support, constraints = _reports()
        changed = copy.deepcopy(constraints)
        changed["packages"]["KG_v1_validated"]["input_files"][
            "claims"
        ]["sha256"] = "f" * 64

        with self.assertRaisesRegex(
            ValueError,
            "Cross-report graph SHA-256 mismatch",
        ):
            build_closure_summary(
                cq,
                support,
                changed,
                input_reports=INPUT_REPORTS,
            )

    def test_missing_source_input_hash_fails_closed(self) -> None:
        cq, support, constraints = _reports()
        support.pop("input_provenance")

        with self.assertRaisesRegex(
            ValueError,
            "does not record the KG_v1_raw",
        ):
            build_closure_summary(
                cq,
                support,
                constraints,
                input_reports=INPUT_REPORTS,
            )

    def test_raw_source_hash_mismatch_fails_closed(self) -> None:
        cq, support, constraints = _reports()
        support["input_provenance"][
            "source_records_sha256"
        ] = "e" * 64

        with self.assertRaisesRegex(
            ValueError,
            "KG_v1_raw/source_records.jsonl",
        ):
            build_closure_summary(
                cq,
                support,
                constraints,
                input_reports=INPUT_REPORTS,
            )


if __name__ == "__main__":
    unittest.main()
