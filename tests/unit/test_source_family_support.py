from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage04_graph_build import (
    aggregate_claim_support,
    aggregate_document_naive_support,
    analyze_source_family_support,
    budget_sensitivity,
    file_sha256,
    filter_eligible_assertions,
    heuristic_assertion_score,
    multi_document_same_family_audit,
    replication_invariance_experiment,
    replication_pressure_experiment,
)


def _record(
    *,
    claim_id: str = "MPC-1",
    family: str = "FAMILY_A",
    doc_id: str = "MP001",
    assertion_id: str = "ASSERT-1",
    model_confidence: float = 0.9,
    evidence_level: str = "E1",
    decision: str = "silver_candidate",
    split: str = "build_train",
    inferred: bool = False,
    entailment_status: str = "entailed",
) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "head_canonical_zh": "机械密封磨损",
        "head_type": "FailureMechanism",
        "relation": "causes",
        "tail_canonical_zh": "泵泄漏",
        "tail_type": "Symptom",
        "fault_class_ids": ["seal_leakage"],
        "source_family_id": family,
        "doc_id": doc_id,
        "pdf_page_number": 7,
        "assertion_id": assertion_id,
        "evidence_id": assertion_id,
        "decision": decision,
        "document_split": split,
        "evidence_level": evidence_level,
        "model_confidence": model_confidence,
        "inferred_edge": inferred,
        "relation_type_valid": True,
        "relation_entailment_valid": entailment_status == "entailed",
        "relation_entailment_validation": {
            "valid": entailment_status == "entailed",
            "status": entailment_status,
            "silver_eligible": entailment_status == "entailed",
        },
        "evidence_validation": {
            "valid": True,
            "silver_eligible": evidence_level in {"E1", "E2"},
        },
    }


class SourceFamilySupportTest(unittest.TestCase):
    def test_heuristic_score_matches_equations_6_to_8(self) -> None:
        e1 = _record(model_confidence=0.9, evidence_level="E1")
        e2 = _record(model_confidence=0.9, evidence_level="E2")
        uncertain = _record(
            model_confidence=0.9,
            evidence_level="E1",
            entailment_status="undetermined",
        )

        self.assertEqual(heuristic_assertion_score(e1), 0.9)
        self.assertEqual(heuristic_assertion_score(e2), 0.855)
        self.assertEqual(heuristic_assertion_score(uncertain), 0.675)

    def test_filter_requires_build_e1_e2_noninferred_silver(self) -> None:
        eligible = _record(assertion_id="A0")
        held_out = _record(assertion_id="A1", split="held_out_test")
        e3 = _record(assertion_id="A2", evidence_level="E3")
        inferred = _record(assertion_id="A3", inferred=True)
        review = _record(assertion_id="A4", decision="candidate_needs_review")

        result = filter_eligible_assertions(
            [eligible, held_out, e3, inferred, review]
        )

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["assertion_id"], "A0")
        self.assertEqual(
            result.exclusion_counts["document_split_not_build_train"],
            1,
        )
        self.assertEqual(
            result.exclusion_counts["evidence_level_not_e1_e2"],
            1,
        )
        self.assertEqual(result.exclusion_counts["inferred_edge"], 1)
        self.assertEqual(result.exclusion_counts["decision_not_silver"], 1)

    def test_filter_enforces_frozen_build_document_whitelist(self) -> None:
        allowed = _record(assertion_id="A0", doc_id="MP022")
        development_disguised_as_build = _record(
            assertion_id="A1",
            doc_id="MP008",
            split="build_train",
        )

        result = filter_eligible_assertions(
            [allowed, development_disguised_as_build]
        )

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["doc_id"], "MP022")
        self.assertEqual(
            result.exclusion_counts["doc_id_not_frozen_build_set"],
            1,
        )

    def test_family_cap_uses_max_and_missing_budget_slots_are_zero(self) -> None:
        records = [
            _record(
                family="FAMILY_A",
                doc_id="DOC-A1",
                assertion_id="A1",
                model_confidence=0.9,
            ),
            _record(
                family="FAMILY_A",
                doc_id="DOC-A2",
                assertion_id="A2",
                model_confidence=0.95,
            ),
        ]

        row = aggregate_claim_support(records, budget=2)[0]

        self.assertEqual(row["assertion_count"], 2)
        self.assertEqual(row["doc_count"], 2)
        self.assertEqual(row["family_count"], 1)
        self.assertEqual(row["top_family_scores"], [0.95])
        self.assertEqual(row["padded_top_family_scores"], [0.95, 0.0])
        self.assertEqual(row["source_family_support_index"], 0.475)

    def test_top_b_families_ignore_lower_ranked_extra_family(self) -> None:
        records = [
            _record(
                family="FAMILY_A",
                assertion_id="A1",
                model_confidence=0.9,
            ),
            _record(
                family="FAMILY_B",
                doc_id="DOC-2",
                assertion_id="A2",
                model_confidence=0.8,
            ),
            _record(
                family="FAMILY_C",
                doc_id="DOC-3",
                assertion_id="A3",
                model_confidence=0.85,
            ),
        ]

        row = aggregate_claim_support(records, budget=2)[0]

        self.assertEqual(row["top_family_scores"], [0.9, 0.85])
        self.assertEqual(row["source_family_support_index"], 0.875)

    def test_same_family_replication_increases_docs_not_index(self) -> None:
        records = [
            _record(
                family="FAMILY_A",
                assertion_id="A1",
                model_confidence=0.95,
            ),
            _record(
                family="FAMILY_B",
                doc_id="MP002",
                assertion_id="A2",
                model_confidence=0.85,
            ),
        ]

        result = replication_invariance_experiment(
            records,
            budget=2,
            copies=2,
        )

        self.assertTrue(result["invariance_passed"])
        self.assertEqual(result["claims_with_changed_support_index"], 0)
        self.assertEqual(result["claims_with_changed_family_count"], 0)
        self.assertEqual(result["sum_claim_doc_counts_before"], 2)
        self.assertEqual(result["sum_claim_doc_counts_after"], 6)

    def test_replication_pressure_separates_document_and_family_counts(self) -> None:
        records = [
            _record(
                family="FAMILY_A",
                assertion_id="A1",
                model_confidence=0.9,
            )
        ]

        result = replication_pressure_experiment(
            records,
            multipliers=[1, 2, 4, 8],
            budget=2,
            decision_threshold=0.8,
        )

        self.assertTrue(result["family_invariance_passed"])
        self.assertTrue(result["document_baseline_exhibits_replication_inflation"])
        self.assertEqual(
            [row["family_support_mean"] for row in result["rows"]],
            [0.45, 0.45, 0.45, 0.45],
        )
        self.assertEqual(
            [row["document_naive_support_mean"] for row in result["rows"]],
            [0.45, 0.9, 0.9, 0.9],
        )
        self.assertEqual(
            aggregate_document_naive_support(records, budget=2)["MPC-1"],
            0.45,
        )

    def test_budget_sensitivity_uses_fixed_denominator(self) -> None:
        records = [
            _record(
                family="FAMILY_A",
                assertion_id="A1",
                model_confidence=0.9,
            )
        ]

        result = budget_sensitivity(records, budgets=[1, 2, 3])

        means = [
            item["support_index"]["mean"]
            for item in result
        ]
        self.assertEqual(means, [0.9, 0.45, 0.3])

    def test_full_analysis_does_not_relabel_records(self) -> None:
        records = [
            _record(
                claim_id="MPC-1",
                assertion_id="A1",
                model_confidence=0.9,
            ),
            _record(
                claim_id="MPC-2",
                family="FAMILY_B",
                doc_id="MP002",
                assertion_id="A2",
                model_confidence=0.85,
            ),
        ]
        original_decisions = [record["decision"] for record in records]

        rows, summary = analyze_source_family_support(records)

        self.assertEqual(len(rows), 2)
        self.assertFalse(summary["changes_existing_silver_labels"])
        self.assertEqual(
            [record["decision"] for record in records],
            original_decisions,
        )
        self.assertTrue(
            summary["replication_invariance_experiment"][
                "invariance_passed"
            ]
        )

    def test_claim_details_separate_surface_candidate_and_release(self) -> None:
        record = _record()
        record.update(
            {
                "head": "seal wear",
                "head_surface": "seal wear",
                "head_canonical_zh": "密封磨损",
                "head_terminology_id": "TERM-H",
                "head_translation_status": "needs_review",
                "tail": "leakage",
                "tail_surface": "leakage",
                "tail_canonical_zh": "泄漏",
                "tail_terminology_id": "TERM-T",
                "tail_translation_status": "secondary_ai_verified",
                "eligible_for_chinese_graph": False,
            }
        )

        row = aggregate_claim_support([record], budget=2)[0]

        self.assertNotIn("head", row)
        self.assertNotIn("tail", row)
        self.assertEqual(
            row["head_endpoint"]["source_surfaces"],
            ["seal wear"],
        )
        self.assertEqual(
            row["head_endpoint"]["canonical_zh_candidates"],
            ["密封磨损"],
        )
        self.assertEqual(
            row["head_endpoint"]["translation_statuses"],
            ["needs_review"],
        )
        self.assertFalse(row["chinese_release"]["has_eligible_assertion"])

    def test_real_multi_document_same_family_audit(self) -> None:
        rows = aggregate_claim_support(
            [
                _record(doc_id="MP001", assertion_id="A1"),
                _record(doc_id="MP002", assertion_id="A2"),
            ],
            budget=2,
        )

        audit = multi_document_same_family_audit(rows)

        self.assertEqual(audit["multiple_document_claim_count"], 1)
        self.assertEqual(
            audit["multiple_document_single_family_claim_count"],
            1,
        )
        self.assertEqual(
            audit["multiple_document_multiple_family_claim_count"],
            0,
        )
        self.assertTrue(
            audit["all_observed_multiple_document_claims_are_single_family"]
        )

    def test_file_sha256_binds_input_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "source_records.jsonl"
            path.write_bytes(b"marine-pump\n")
            self.assertEqual(
                file_sha256(path),
                "5EBF99137C3EB456A510D977F7423647"
                "B82D767A123E1C1A27ABE510972CA267",
            )

    def test_invalid_budget_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            aggregate_claim_support([_record()], budget=0)


if __name__ == "__main__":
    unittest.main()
