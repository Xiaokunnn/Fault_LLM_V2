from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage02_triple_extraction.candidate_pool_builder import (  # noqa: E402
    build_candidate_pool,
)
from research_point_1_graph_evidence.stage02_triple_extraction.page_index import (  # noqa: E402
    create_index,
)


def _page(doc_id: str, split: str, text: str) -> dict[str, object]:
    return {
        "doc_id": doc_id,
        "pdf_page_number": 1,
        "document_split": split,
        "source_family_id": "DESMI" if split == "build_train" else "SULZER",
        "publisher": "Test",
        "pump_type": "centrifugal_pump",
        "service": "marine",
        "applicability_scope": "pump",
        "source_url": "https://example.test/manual.pdf",
        "page_text": text,
        "page_text_sha256": "a" * 64,
        "tables": [],
        "warnings": [],
    }


class CorpusCandidatePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ontology = json.loads(
            (
                PROJECT_ROOT / "configs/fault_ontology_marine_pump_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.config = json.loads(
            (
                PROJECT_ROOT
                / "configs/corpus_candidate_retrieval_marine_pump_v1.json"
            ).read_text(encoding="utf-8")
        )

    def test_index_and_retrieval_keep_build_pages_only(self) -> None:
        text = (
            "A clogged filter causes low pump flow. "
            "Inspect and clean the filter during maintenance."
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "pages.sqlite"
            result = create_index(
                database,
                [
                    _page("MP-BUILD", "build_train", text),
                    _page("MP-HELD", "held_out_test", text),
                ],
            )
            self.assertEqual(result["pages_indexed"], 2)
            pages, _excluded, summary = build_candidate_pool(
                database_path=database,
                ontology=self.ontology,
                config=self.config,
            )
        self.assertGreater(summary["candidate_pages"], 0)
        self.assertEqual({item["doc_id"] for item in pages}, {"MP-BUILD"})
        blockage = [
            item
            for item in pages
            if "hydraulic_blockage" in item["target_fault_classes"]
        ]
        self.assertTrue(blockage)
        self.assertIn("inspection", blockage[0]["target_evidence_roles"])
        self.assertIn("maintenance", blockage[0]["target_evidence_roles"])

    def test_table_of_contents_is_not_selected(self) -> None:
        toc = (
            "TABLE OF CONTENTS\n"
            "Clogged filter faults ........ 10\n"
            "Pump maintenance ........ 11\n"
            "Inspection procedure ........ 12\n"
            "Repair instructions ........ 13\n"
            "Cavitation ........ 14\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "pages.sqlite"
            create_index(database, [_page("MP-TOC", "build_train", toc)])
            pages, excluded, _summary = build_candidate_pool(
                database_path=database,
                ontology=self.ontology,
                config=self.config,
            )
        self.assertEqual(pages, [])
        self.assertTrue(
            any(item["reason"] == "table_of_contents" for item in excluded)
        )


if __name__ == "__main__":
    unittest.main()
