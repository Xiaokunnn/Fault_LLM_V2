from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from research_point_1_graph_evidence.stage01_document_ingest.manifest_loader import (  # noqa: E402
    load_document_manifest,
    validate_local_file,
)
from research_point_1_graph_evidence.stage01_document_ingest.pdf_parser import (  # noqa: E402
    PdfDocumentParser,
    detect_source_language,
    infer_column_role,
)


class ColumnRoleTests(unittest.TestCase):
    def test_fault_cause_remedy_roles(self) -> None:
        self.assertEqual(infer_column_role("FAULT"), "fault_or_symptom")
        self.assertEqual(infer_column_role("Possible Cause"), "cause_or_mechanism")
        self.assertEqual(
            infer_column_role("REMEDY"),
            "inspection_or_maintenance",
        )
        self.assertEqual(infer_column_role("故障现象"), "fault_or_symptom")
        self.assertEqual(infer_column_role("可能原因"), "cause_or_mechanism")
        self.assertEqual(
            infer_column_role("检查与维修措施"),
            "inspection_or_maintenance",
        )

    def test_page_language_detection(self) -> None:
        self.assertEqual(
            detect_source_language("The pump has excessive vibration. " * 5)[0],
            "en",
        )
        self.assertEqual(
            detect_source_language("泵发生异常振动，应检查轴承和联轴器。" * 5)[0],
            "zh",
        )
        self.assertEqual(
            detect_source_language(
                ("泵发生振动并需要检查。 " * 5)
                + ("The pump vibrates and requires inspection. " * 5)
            )[0],
            "multilingual",
        )


class ManifestAndParserIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_document_manifest(
            PROJECT_ROOT,
            require_source_family=False,
        )

    def test_manifest_integrity_for_representative_document(self) -> None:
        errors = validate_local_file(PROJECT_ROOT, self.manifest["MP004"])
        self.assertEqual(errors, [])

    def test_post_gap_source_is_integrity_checked_and_build_only(self) -> None:
        document = self.manifest["MP022"]
        self.assertEqual(document.document_split, "build_train")
        self.assertEqual(document.source_family_id, "ALFA_LAVAL")
        self.assertEqual(document.pages, 52)
        self.assertEqual(validate_local_file(PROJECT_ROOT, document), [])

    def test_post_gap_troubleshooting_table_is_visually_gated(self) -> None:
        pages = PdfDocumentParser(PROJECT_ROOT).parse(
            self.manifest["MP022"],
            [22],
            printed_page_overrides={22: "22"},
            visual_layout_checked_pages={22},
        )
        self.assertEqual(len(pages), 1)
        self.assertTrue(pages[0].visual_layout_checked)
        self.assertTrue(pages[0].tables)
        page_text = pages[0].page_text.lower()
        self.assertIn("leaking shaft seal", page_text)
        self.assertIn("running dry", page_text)

    def test_manifest_rejects_unassigned_local_document(self) -> None:
        split = json.loads(
            (
                PROJECT_ROOT / "configs/document_split_marine_pump_v2.json"
            ).read_text(encoding="utf-8")
        )
        split["build_train_doc_ids"].remove("MP016")
        with tempfile.TemporaryDirectory() as directory:
            split_path = Path(directory) / "split.json"
            split_path.write_text(json.dumps(split), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "MP016 is not assigned"):
                load_document_manifest(PROJECT_ROOT, split_path=split_path)

    def test_fault_table_preserves_cell_coordinates_and_roles(self) -> None:
        pages = PdfDocumentParser(PROJECT_ROOT).parse(
            self.manifest["MP004"],
            [11],
            printed_page_overrides={11: "10"},
            visual_layout_checked_pages={11},
        )
        self.assertEqual(len(pages), 1)
        page = pages[0]
        self.assertEqual(page.pdf_page_number, 11)
        self.assertEqual(page.printed_page.value, "10")
        self.assertEqual(page.printed_page.method, "versioned_manual_override")
        self.assertTrue(page.visual_layout_checked)
        self.assertEqual(page.document_split, "build_train")
        self.assertTrue(page.pump_type)
        self.assertTrue(page.service)
        self.assertTrue(page.applicability_scope)
        self.assertEqual(page.source_language, "en")
        self.assertGreaterEqual(page.source_language_confidence, 0.9)
        self.assertTrue(page.tables)
        table = page.tables[0]
        self.assertEqual(
            table.column_roles[:3],
            [
                "fault_or_symptom",
                "cause_or_mechanism",
                "inspection_or_maintenance",
            ],
        )
        data_cells = [cell for row in table.rows[1:] for cell in row.cells]
        self.assertTrue(any("does not" in cell.text.lower() for cell in data_cells))
        self.assertTrue(all(cell.bbox.x1 > cell.bbox.x0 for cell in data_cells))
        located_cells = [cell for cell in data_cells if cell.page_text_start is not None]
        for cell in located_cells:
            self.assertEqual(
                page.page_text[cell.page_text_start : cell.page_text_end],
                cell.page_text_source,
            )
        self.assertTrue(all(cell.text and cell.bbox for cell in data_cells))

    def test_multicolumn_lines_are_not_merged_into_synthetic_sentences(self) -> None:
        if "MP016" not in self.manifest:
            self.skipTest("MP016 source intake has not completed")
        pages = PdfDocumentParser(PROJECT_ROOT).parse(self.manifest["MP016"], [4])
        blocks = pages[0].text_blocks
        page_midpoint = pages[0].page_width / 2
        cross_column_blocks = [
            block
            for block in blocks
            if block.bbox.x0 < page_midpoint - 20
            and block.bbox.x1 > page_midpoint + 20
        ]
        self.assertEqual(
            cross_column_blocks,
            [],
            "A text block must not concatenate unrelated left/right columns",
        )
        self.assertIn("flexible", (pages[0].pump_type or "").lower())
        self.assertIn("marine", (pages[0].service or "").lower())

    def test_merged_fault_cell_assigns_shared_row_group(self) -> None:
        pages = PdfDocumentParser(PROJECT_ROOT).parse(
            self.manifest["MP005"],
            [60],
            visual_layout_checked_pages={60},
        )
        table = pages[0].tables[0]
        fault_cell = next(
            cell
            for row in table.rows
            for cell in row.cells
            if "too low capacity" in cell.text.lower()
        )
        cause_cell = next(
            cell
            for row in table.rows
            for cell in row.cells
            if "piping system is choked" in cell.text.lower()
        )
        self.assertNotEqual(fault_cell.row_id, cause_cell.row_id)
        self.assertEqual(fault_cell.row_group_id, cause_cell.row_group_id)

    def test_out_of_page_table_bbox_is_clipped_without_aborting(self) -> None:
        pages = PdfDocumentParser(PROJECT_ROOT).parse(
            self.manifest["MP008"],
            [7],
        )
        self.assertEqual(len(pages), 1)
        self.assertTrue(pages[0].tables)
        self.assertTrue(
            any(
                "bbox_clipped_to_page" in warning
                for warning in pages[0].warnings
            )
        )
        for table in pages[0].tables:
            self.assertGreaterEqual(table.bbox.x0, 0)
            self.assertGreaterEqual(table.bbox.top, 0)
            self.assertLessEqual(table.bbox.x1, pages[0].page_width)
            self.assertLessEqual(table.bbox.bottom, pages[0].page_height)


if __name__ == "__main__":
    unittest.main()
