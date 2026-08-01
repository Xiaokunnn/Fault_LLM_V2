from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from research_point_1_graph_evidence.stage05_evaluation.rp1_b0_ours import (  # noqa: E402
    compute_cq_sensitivity,
    compute_stage_rows,
)


def _record(
    index: int,
    *,
    relation: bool = True,
    evidence: bool = True,
    entailment: bool = True,
    score: float = 0.95,
    chinese: bool = True,
) -> dict[str, object]:
    return {
        "assertion_id": f"A{index}",
        "claim_id": f"C{index}",
        "doc_id": "MP001",
        "document_split": "build_train",
        "source_family_id": "FAMILY",
        "pdf_page_number": 1,
        "source_url": "https://example.test/manual.pdf",
        "document_sha256": "a" * 64,
        "page_text_sha256": "b" * 64,
        "inferred_edge": False,
        "head_entity_id": f"H{index}",
        "tail_entity_id": f"T{index}",
        "fault_class_ids": ["fault"],
        "relation_type_valid": relation,
        "relation_type_validation": {"valid": relation},
        "evidence_level": "E1",
        "evidence_text": "evidence",
        "evidence_validation": {
            "valid": evidence,
            "silver_eligible": evidence,
        },
        "relation_entailment_valid": entailment,
        "relation_entailment_validation": {
            "valid": entailment,
            "silver_eligible": entailment,
            "status": "entailed" if entailment else "undetermined",
        },
        "model_confidence": score,
        "eligible_for_chinese_graph": chinese,
        "graph_release_status": (
            "core_silver_ready"
            if chinese
            else "candidate_needs_chinese_normalization"
        ),
        "head_terminology_id": "ZH-H" if chinese else None,
        "tail_terminology_id": "ZH-T" if chinese else None,
        "head_canonical_zh": "头" if chinese else None,
        "tail_canonical_zh": "尾" if chinese else None,
    }


class B0OursExperimentTests(unittest.TestCase):
    def test_cumulative_stage_counts(self) -> None:
        records = [
            _record(1),
            _record(2, relation=False),
            _record(3, evidence=False),
            _record(4, entailment=False),
            _record(5, score=0.7),
            _record(6, chinese=False),
        ]
        rows, _ = compute_stage_rows(
            records,
            build_doc_ids={"MP001"},
            score_threshold=0.8,
        )
        counts = {
            row["method_id"]: row["assertion_count"] for row in rows
        }
        self.assertEqual(
            counts,
            {"B0": 6, "B1": 5, "B2": 4, "B3": 2, "Ours": 1},
        )

    def test_cq_sensitivity(self) -> None:
        tasks = [
            {
                "answer_count": 3,
                "source_family_count": 2,
            },
            {
                "answer_count": 1,
                "source_family_count": 1,
            },
            {
                "answer_count": 0,
                "source_family_count": 0,
            },
        ]
        result = compute_cq_sensitivity(
            tasks,
            minimum_answers=[1, 2, 3],
            minimum_source_families=[1, 2],
        )
        self.assertEqual(
            [
                row["answerable_task_count"]
                for row in result["minimum_answers"]
            ],
            [2, 1, 1],
        )
        self.assertEqual(
            [
                row["answerable_task_count"]
                for row in result["minimum_source_families"]
            ],
            [2, 1],
        )


if __name__ == "__main__":
    unittest.main()
