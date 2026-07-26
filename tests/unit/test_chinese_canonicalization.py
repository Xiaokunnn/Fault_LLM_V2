from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    load_chinese_terminology,
    load_fault_ontology,
    is_build_coverage_eligible,
    map_fault_classes,
    stable_entity_id,
    validate_candidate,
    validate_chinese_canonicalization,
    validate_relation_entailment,
)


class ChineseCanonicalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.terminology = load_chinese_terminology(project_root=PROJECT_ROOT)

    def test_type_scoped_dictionary_makes_english_claim_graph_ready(self) -> None:
        result = validate_chinese_canonicalization(
            head_surface="Cavitation",
            head_type="FaultMode",
            relation="causes",
            tail_surface="Heavy erosion",
            tail_type="Symptom",
            terminology=self.terminology,
        )
        self.assertTrue(result.graph_ready)
        self.assertEqual(result.head.canonical_label_zh, "汽蚀")
        self.assertEqual(result.tail.canonical_label_zh, "严重冲蚀")
        self.assertEqual(result.relation_label_zh, "导致")
        self.assertEqual(result.head.translation_status, "dictionary_approved")

    def test_unreviewed_model_translation_is_not_graph_ready(self) -> None:
        result = validate_chinese_canonicalization(
            head_surface="Unstable recirculation",
            head_type="FailureMechanism",
            relation="causes",
            tail_surface="Pressure fluctuation",
            tail_type="Symptom",
            candidate={
                "head_canonical_zh": "不稳定回流",
                "tail_canonical_zh": "压力波动",
            },
            terminology=self.terminology,
        )
        self.assertFalse(result.graph_ready)
        self.assertIn(
            "translation_status_not_graph_eligible",
            result.reasons,
        )

    def test_secondary_review_and_protected_term_retention(self) -> None:
        result = validate_chinese_canonicalization(
            head_surface="NPSH required",
            head_type="OperatingCondition",
            relation="causes",
            tail_surface="Pressure fluctuation",
            tail_type="Symptom",
            candidate={
                "head_canonical_zh": "必需汽蚀余量（NPSH）",
                "head_translation_status": "secondary_ai_verified",
                "tail_canonical_zh": "压力波动",
                "tail_translation_status": "secondary_ai_verified",
            },
            terminology=self.terminology,
        )
        self.assertTrue(result.head.protected_terms_valid)
        self.assertTrue(result.graph_ready)

    def test_chinese_source_surface_can_be_canonical_without_translation(self) -> None:
        result = validate_chinese_canonicalization(
            head_surface="泵体裂纹",
            head_type="FaultMode",
            relation="manifests_as",
            tail_surface="出口压力波动",
            tail_type="Symptom",
            terminology=self.terminology,
        )
        self.assertTrue(result.graph_ready)
        self.assertEqual(result.head.translation_status, "source_zh_exact")
        self.assertEqual(result.tail.translation_status, "source_zh_exact")

    def test_entity_id_uses_stable_terminology_id(self) -> None:
        first = stable_entity_id(
            "汽蚀",
            "FaultMode",
            terminology_id="MPTERM-FAULT-CAVITATION",
        )
        second = stable_entity_id(
            "气蚀",
            "FaultMode",
            terminology_id="MPTERM-FAULT-CAVITATION",
        )
        self.assertEqual(first, second)

    def test_pipeline_preserves_english_evidence_and_adds_chinese_projection(
        self,
    ) -> None:
        page = "Cavitation causes Heavy erosion."
        result = validate_candidate(
            {
                "head": "Cavitation",
                "head_type": "FaultMode",
                "relation": "causes",
                "tail": "Heavy erosion",
                "tail_type": "Symptom",
                "evidence_text": page,
                "model_confidence": 0.95,
                "source_tier": "A",
                "source_family_id": "TEST_SOURCE",
                "document_split": "build_train",
                "fault_class_ids": ["cavitation"],
            },
            page_text=page,
            project_root=PROJECT_ROOT,
        )
        self.assertEqual(result["evidence_text"], page)
        self.assertEqual(result["head_surface"], "Cavitation")
        self.assertEqual(result["head_canonical_zh"], "汽蚀")
        self.assertEqual(result["tail_canonical_zh"], "严重冲蚀")
        self.assertTrue(result["eligible_for_chinese_graph"])
        self.assertTrue(
            is_build_coverage_eligible(
                result,
                require_chinese_graph_ready=True,
            )
        )

    def test_direction_normalization_swaps_chinese_labels_together(self) -> None:
        page = (
            "A considerably smaller delivery head than expected causes Cavitation."
        )
        result = validate_candidate(
            {
                "head": "Cavitation",
                "head_type": "FaultMode",
                "head_canonical_zh": "汽蚀",
                "relation": "causes",
                "tail": "A considerably smaller delivery head than expected",
                "tail_type": "OperatingCondition",
                "tail_canonical_zh": "实际输送扬程显著低于预期",
                "evidence_text": page,
                "model_confidence": 0.95,
                "source_tier": "A",
                "source_family_id": "TEST_SOURCE",
                "document_split": "build_train",
            },
            page_text=page,
            project_root=PROJECT_ROOT,
        )
        self.assertEqual(
            result["head"],
            "A considerably smaller delivery head than expected",
        )
        self.assertEqual(
            result["head_canonical_zh"],
            "实际输送扬程显著低于预期",
        )
        self.assertEqual(result["tail"], "Cavitation")
        self.assertEqual(result["tail_canonical_zh"], "汽蚀")

    def test_untranslated_silver_evidence_cannot_fill_chinese_graph_gate(
        self,
    ) -> None:
        record = {
            "decision": "silver_candidate",
            "final_confidence": 0.95,
            "document_split": "build_train",
            "source_family_id": "SOURCE_A",
            "inferred_edge": False,
            "evidence_level": "E1",
            "relation_entailment_valid": True,
            "eligible_for_chinese_graph": False,
        }
        self.assertTrue(is_build_coverage_eligible(record))
        self.assertFalse(
            is_build_coverage_eligible(
                record,
                require_chinese_graph_ready=True,
            )
        )


class ChineseSourceValidationTests(unittest.TestCase):
    def test_chinese_relation_cue_is_supported(self) -> None:
        result = validate_relation_entailment(
            relation="causes",
            evidence_text="吸入管堵塞导致泵流量过低。",
            head_surface="吸入管堵塞",
            tail_surface="泵流量过低",
            evidence_level="E1",
        )
        self.assertTrue(result.valid)

    def test_chinese_fault_mapping_uses_validated_text(self) -> None:
        ontology = load_fault_ontology(project_root=PROJECT_ROOT)
        result = map_fault_classes(
            head_surface="吸入管堵塞",
            tail_surface="泵流量过低",
            evidence_text="吸入管堵塞导致泵流量过低。",
            ontology=ontology,
        )
        self.assertIn("hydraulic_blockage", result.fault_class_ids)


class ChineseGraphSchemaTests(unittest.TestCase):
    def test_schema_and_terminology_have_complete_chinese_display_maps(self) -> None:
        schema = json.loads(
            (
                PROJECT_ROOT
                / "data/kg/marine_pump/schema/provenance_schema_v2.json"
            ).read_text(encoding="utf-8")
        )
        terminology = load_chinese_terminology(project_root=PROJECT_ROOT)
        self.assertEqual(
            schema["schema_version"],
            "marine_pump_provenance_v2.1.0",
        )
        self.assertEqual(
            set(schema["node_type_registry"]),
            set(schema["node_type_labels_zh"]),
        )
        self.assertEqual(
            set(schema["relation_registry"]),
            set(terminology["relation_labels_zh"]),
        )
        self.assertTrue(
            all(
                definition.get("label_zh")
                for definition in schema["relation_registry"].values()
            )
        )
        entity_schema = schema["$defs"]["CanonicalEntity"]
        self.assertEqual(entity_schema["properties"]["language"]["const"], "zh")
        for field in (
            "source_forms",
            "terminology_id",
            "terminology_version",
            "translation_method",
            "translation_status",
        ):
            self.assertIn(field, entity_schema["required"])
        assertion_schema = schema["$defs"]["EvidenceAssertion"]
        for field in (
            "source_language",
            "raw_head_language",
            "raw_tail_language",
        ):
            self.assertIn(field, assertion_schema["required"])


if __name__ == "__main__":
    unittest.main()
