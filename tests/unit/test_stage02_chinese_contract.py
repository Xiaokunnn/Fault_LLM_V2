from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage02_triple_extraction.chinese_extraction_contract import (  # noqa: E402
    SYSTEM_PROMPT_ZH_V1,
    SYSTEM_PROMPT_ZH_V2_GAP_REPAIR,
    SYSTEM_PROMPT_ZH_V3_SYMPTOM_REPAIR,
    build_user_prompt,
    normalize_model_candidate,
    system_prompt_for_version,
)


class ChineseExtractionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = {
            "doc_id": "MP016",
            "pdf_page_number": 4,
            "document_split": "build_train",
            "source_language": "en",
            "source_family_id": "XYLEM__JABSCO",
            "source_url": "https://example.test/manual.pdf",
            "source_tier": "A",
            "publisher": "Xylem / Jabsco",
            "document_sha256": "a" * 64,
            "page_text_sha256": "b" * 64,
            "pump_type": "flexible_impeller_pump",
            "service": "marine_engine_cooling",
            "applicability_scope": "柔性叶轮泵",
            "page_text": "Dry running causes impeller damage.",
            "tables": [],
        }

    def test_prompt_separates_source_surface_from_chinese_label(self) -> None:
        self.assertIn("head_surface", SYSTEM_PROMPT_ZH_V1)
        self.assertIn("head_canonical_zh", SYSTEM_PROMPT_ZH_V1)
        self.assertIn("不得翻译", SYSTEM_PROMPT_ZH_V1)
        prompt = build_user_prompt(self.page)
        self.assertIn("Dry running causes impeller damage.", prompt)
        self.assertIn("flexible_impeller_pump", prompt)

    def test_model_translation_defaults_to_needs_review(self) -> None:
        candidate = normalize_model_candidate(
            {
                "head_surface": "Dry running",
                "head_canonical_zh": "干运转",
                "head_type": "FaultMode",
                "relation": "causes",
                "tail_surface": "impeller damage",
                "tail_canonical_zh": "叶轮损坏",
                "tail_type": "FaultMode",
                "evidence_text": "Dry running causes impeller damage.",
                "evidence_role": "cause_or_mechanism",
                "model_confidence": 0.9,
            },
            page=self.page,
        )
        self.assertEqual(candidate["head"], "Dry running")
        self.assertEqual(candidate["head_canonical_zh"], "干运转")
        self.assertEqual(candidate["head_translation_status"], "needs_review")
        self.assertEqual(
            candidate["evidence_text"],
            "Dry running causes impeller damage.",
        )

    def test_gap_prompt_prioritizes_missing_roles_and_prevention(self) -> None:
        prompt = system_prompt_for_version(
            "marine_pump_gap_role_repair_prompt_v2"
        )
        self.assertEqual(prompt, SYSTEM_PROMPT_ZH_V2_GAP_REPAIR)
        self.assertIn("不得在抽到原因关系后停止", prompt)
        self.assertIn("prevented_by", prompt)
        self.assertIn("同一row_id", prompt)

    def test_prevented_by_is_accepted_by_v2_gap_contract(self) -> None:
        candidate = normalize_model_candidate(
            {
                "head_surface": "Dry running",
                "head_canonical_zh": "干运转",
                "head_type": "FaultMode",
                "relation": "prevented_by",
                "tail_surface": "fill the pump before starting",
                "tail_canonical_zh": "启动前灌泵",
                "tail_type": "MaintenanceAction",
                "evidence_text": (
                    "Dry running is prevented when operators "
                    "fill the pump before starting."
                ),
                "evidence_role": "maintenance",
                "model_confidence": 0.95,
            },
            page=self.page,
        )
        self.assertEqual(candidate["relation"], "prevented_by")

    def test_v3_prompt_forbids_component_manifestation_head(self) -> None:
        prompt = system_prompt_for_version(
            "marine_pump_symptom_role_repair_prompt_v3"
        )
        self.assertEqual(prompt, SYSTEM_PROMPT_ZH_V3_SYMPTOM_REPAIR)
        self.assertIn("Component不能作为manifests_as的头实体", prompt)
        self.assertIn("initial leakage", prompt)

    def test_non_chinese_canonical_label_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Han"):
            normalize_model_candidate(
                {
                    "head_surface": "Dry running",
                    "head_canonical_zh": "dry running",
                    "head_type": "FaultMode",
                    "relation": "causes",
                    "tail_surface": "impeller damage",
                    "tail_canonical_zh": "叶轮损坏",
                    "tail_type": "FaultMode",
                    "evidence_text": "Dry running causes impeller damage.",
                },
                page=self.page,
            )


if __name__ == "__main__":
    unittest.main()
