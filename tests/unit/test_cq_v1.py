from __future__ import annotations

from copy import deepcopy
import json
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from evaluate_cq_v1 import (  # noqa: E402
    audit_primary_split,
    eligible_assertion_bundle,
    evaluate_task_units,
    validate_cq_config,
)


CONFIG_PATH = PROJECT_ROOT / "configs" / "competency_questions_marine_pump_v1.json"


def _source(
    *,
    evidence_id: str,
    doc_id: str,
    split: str,
    family: str,
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "assertion_id": evidence_id,
        "doc_id": doc_id,
        "pdf_page_number": 7,
        "document_split": split,
        "source_url": f"https://example.org/{doc_id}.pdf",
        "source_family_id": family,
        "document_sha256": "a" * 64,
        "page_text_sha256": "b" * 64,
        "evidence_text": "A traceable evidence sentence.",
        "evidence_level": "E1",
        "relation_type_valid": True,
        "evidence_validation": {
            "valid": True,
            "silver_eligible": True,
        },
        "relation_entailment_validation": {
            "silver_eligible": True,
        },
        "decision": "silver_candidate",
        "eligible_for_chinese_graph": True,
        "relation_entailment_valid": True,
        "inferred_edge": False,
    }


def _link(claim_id: str, evidence_id: str) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "evidence_id": evidence_id,
        "assertion_id": evidence_id,
        "decision": "silver_candidate",
        "eligible_for_chinese_graph": True,
        "relation_entailment_valid": True,
        "inferred_edge": False,
    }


class CompetencyQuestionV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_frozen_suite_is_exact_10_by_4_and_matches_schema(self) -> None:
        summary = validate_cq_config(self.config, project_root=PROJECT_ROOT)
        self.assertEqual(summary["fault_class_count"], 10)
        self.assertEqual(summary["role_count"], 4)
        self.assertEqual(summary["task_unit_count"], 40)
        self.assertEqual(summary["node_type_count"], 13)
        self.assertEqual(summary["relation_count"], 15)
        self.assertTrue(self.config["evaluation_semantics"]["not_accuracy"])

    def test_split_audit_detects_development_and_heldout_records(self) -> None:
        records = [
            _source(
                evidence_id="EV-BUILD",
                doc_id="MP001",
                split="build_train",
                family="FAMILY-A",
            ),
            _source(
                evidence_id="EV-DEV",
                doc_id="MP008",
                split="development",
                family="FAMILY-B",
            ),
            _source(
                evidence_id="EV-TEST",
                doc_id="MP009",
                split="held_out_test",
                family="FAMILY-C",
            ),
        ]
        result = audit_primary_split(records, self.config["split_policy"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["eligible_source_record_count"], 1)
        self.assertEqual(result["contaminated_record_count"], 2)

    def test_task_answers_count_only_traceable_build_evidence(self) -> None:
        entities = {
            "CAUSE-BUILD": {
                "entity_id": "CAUSE-BUILD",
                "canonical_label_zh": "构建集原因",
                "entity_type": "Cause",
            },
            "CAUSE-DEV": {
                "entity_id": "CAUSE-DEV",
                "canonical_label_zh": "开发集原因",
                "entity_type": "Cause",
            },
            "CAUSE-TEST": {
                "entity_id": "CAUSE-TEST",
                "canonical_label_zh": "保留测试集原因",
                "entity_type": "Cause",
            },
            "FAULT": {
                "entity_id": "FAULT",
                "canonical_label_zh": "汽蚀故障",
                "entity_type": "FaultMode",
            },
        }
        claims = {
            "CLAIM-BUILD": {
                "claim_id": "CLAIM-BUILD",
                "head_entity_id": "CAUSE-BUILD",
                "relation": "causes",
                "tail_entity_id": "FAULT",
                "fault_class_ids": ["cavitation"],
            },
            "CLAIM-DEV": {
                "claim_id": "CLAIM-DEV",
                "head_entity_id": "CAUSE-DEV",
                "relation": "causes",
                "tail_entity_id": "FAULT",
                "fault_class_ids": ["cavitation"],
            },
            "CLAIM-TEST": {
                "claim_id": "CLAIM-TEST",
                "head_entity_id": "CAUSE-TEST",
                "relation": "causes",
                "tail_entity_id": "FAULT",
                "fault_class_ids": ["cavitation"],
            },
        }
        sources = [
            _source(
                evidence_id="EV-BUILD",
                doc_id="MP001",
                split="build_train",
                family="FAMILY-A",
            ),
            _source(
                evidence_id="EV-DEV",
                doc_id="MP008",
                split="development",
                family="FAMILY-B",
            ),
            _source(
                evidence_id="EV-TEST",
                doc_id="MP009",
                split="held_out_test",
                family="FAMILY-C",
            ),
        ]
        package = {
            "entities": entities,
            "claims": claims,
            "evidence": {
                item["evidence_id"]: {
                    "evidence_id": item["evidence_id"],
                    "doc_id": item["doc_id"],
                    "pdf_page_number": item["pdf_page_number"],
                    "source_url": item["source_url"],
                    "source_family_id": item["source_family_id"],
                    "document_sha256": item["document_sha256"],
                    "page_text_sha256": item["page_text_sha256"],
                    "evidence_text": item["evidence_text"],
                    "evidence_level": item["evidence_level"],
                }
                for item in sources
            },
            "links": [
                _link("CLAIM-BUILD", "EV-BUILD"),
                _link("CLAIM-DEV", "EV-DEV"),
                _link("CLAIM-TEST", "EV-TEST"),
            ],
            "source_records": sources,
            "source_by_evidence": {item["evidence_id"]: item for item in sources},
        }

        results, context = evaluate_task_units(self.config, package)
        target = next(item for item in results if item["cq_id"] == "CQ-F01-CAUSE")
        self.assertEqual(target["semantic_path_answer_count_before_evidence_gate"], 3)
        self.assertEqual(target["answer_count"], 1)
        self.assertEqual(target["document_ids"], ["MP001"])
        self.assertEqual(target["source_family_ids"], ["FAMILY-A"])
        self.assertEqual(target["evidence_assertion_ids"], ["EV-BUILD"])
        self.assertTrue(target["structurally_answerable"])
        self.assertEqual(target["traceable_structure_answerability"], 1.0)
        self.assertEqual(
            context["rejected_link_reason_counts"]["document_split_not_build_train"],
            2,
        )
        no_path = next(
            item for item in results if item["cq_id"] == "CQ-F01-SYM"
        )
        self.assertFalse(no_path["structurally_answerable"])
        self.assertEqual(
            no_path["unanswerable_reason_codes"],
            ["no_legal_semantic_path"],
        )
        self.assertEqual(no_path["reason_codes"], ["no_legal_semantic_path"])
        self.assertIsInstance(no_path["unanswerable_reason"], str)

        package_without_build = {
            **package,
            "claims": {
                key: value
                for key, value in claims.items()
                if key in {"CLAIM-DEV", "CLAIM-TEST"}
            },
            "links": [
                _link("CLAIM-DEV", "EV-DEV"),
                _link("CLAIM-TEST", "EV-TEST"),
            ],
        }
        gated_results, _ = evaluate_task_units(
            self.config, package_without_build
        )
        gated = next(
            item for item in gated_results if item["cq_id"] == "CQ-F01-CAUSE"
        )
        self.assertEqual(gated["semantic_path_answer_count_before_evidence_gate"], 2)
        self.assertEqual(gated["answer_count"], 0)
        self.assertEqual(
            gated["reason_codes"],
            ["no_traceable_release_evidence"],
        )
        self.assertIsInstance(gated["unanswerable_reason"], str)

        gate_cases = [
            (
                "relation_type_valid",
                lambda source: source.__setitem__("relation_type_valid", False),
                "source_relation_type_invalid",
            ),
            (
                "evidence_validation.valid",
                lambda source: source["evidence_validation"].__setitem__(
                    "valid", False
                ),
                "source_evidence_validation_invalid",
            ),
            (
                "evidence_validation.silver_eligible",
                lambda source: source["evidence_validation"].__setitem__(
                    "silver_eligible", False
                ),
                "source_evidence_not_silver_eligible",
            ),
            (
                "relation_entailment_validation.silver_eligible",
                lambda source: source[
                    "relation_entailment_validation"
                ].__setitem__("silver_eligible", False),
                "source_entailment_not_silver_eligible",
            ),
        ]
        for label, mutate, expected_reason in gate_cases:
            with self.subTest(gate=label):
                gated_package = deepcopy(package)
                source = gated_package["source_by_evidence"]["EV-BUILD"]
                mutate(source)
                bundle, reasons = eligible_assertion_bundle(
                    gated_package["links"][0],
                    gated_package,
                    self.config,
                )
                self.assertIsNone(bundle)
                self.assertIn(expected_reason, reasons)

    def test_independent_gate_rejects_missing_explicit_silver_eligibility(self) -> None:
        source = _source(
            evidence_id="EV-BUILD",
            doc_id="MP001",
            split="build_train",
            family="FAMILY-A",
        )
        package = {
            "entities": {},
            "claims": {
                "CLAIM": {
                    "claim_id": "CLAIM",
                    "head_entity_id": "HEAD",
                    "relation": "causes",
                    "tail_entity_id": "TAIL",
                    "fault_class_ids": ["cavitation"],
                }
            },
            "evidence": {
                "EV-BUILD": {
                    key: source[key]
                    for key in (
                        "evidence_id",
                        "doc_id",
                        "pdf_page_number",
                        "source_url",
                        "source_family_id",
                        "document_sha256",
                        "page_text_sha256",
                        "evidence_text",
                        "evidence_level",
                    )
                }
            },
            "links": [_link("CLAIM", "EV-BUILD")],
            "source_records": [source],
            "source_by_evidence": {"EV-BUILD": source},
        }
        mutations = [
            (
                lambda item: item.pop("relation_type_valid"),
                "source_relation_type_invalid",
            ),
            (
                lambda item: item["evidence_validation"].pop("valid"),
                "source_evidence_validation_invalid",
            ),
            (
                lambda item: item["evidence_validation"].pop("silver_eligible"),
                "source_evidence_not_silver_eligible",
            ),
            (
                lambda item: item["relation_entailment_validation"].pop(
                    "silver_eligible"
                ),
                "source_entailment_not_silver_eligible",
            ),
        ]
        for mutate, expected_reason in mutations:
            with self.subTest(expected_reason=expected_reason):
                candidate = deepcopy(package)
                mutate(candidate["source_by_evidence"]["EV-BUILD"])
                bundle, reasons = eligible_assertion_bundle(
                    candidate["links"][0],
                    candidate,
                    self.config,
                )
                self.assertIsNone(bundle)
                self.assertIn(expected_reason, reasons)


if __name__ == "__main__":
    unittest.main()
