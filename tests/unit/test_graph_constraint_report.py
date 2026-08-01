"""Tests for the executable KG_v1 graph constraint profile."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    generate_graph_constraint_report,
    render_graph_constraint_report_markdown,
    stable_claim_id,
    stable_entity_id,
    stable_evidence_id,
    stable_triple_id,
)


SCHEMA_PATH = (
    PROJECT_ROOT
    / "data"
    / "kg"
    / "marine_pump"
    / "schema"
    / "provenance_schema_v3.json"
)
TERMINOLOGY_PATH = (
    PROJECT_ROOT
    / "configs"
    / "entity_terminology_zh_marine_pump_v4_silver.json"
)
SPLIT_PATH = PROJECT_ROOT / "configs" / "document_split_marine_pump_v4.json"


def _valid_source_record(
    *,
    doc_id: str = "MP001",
    document_split: str = "build_train",
) -> dict[str, object]:
    evidence_text = "Cavitation manifests as high vibration."
    record: dict[str, object] = {
        "head": "Cavitation",
        "head_surface": "Cavitation",
        "head_canonical_zh": "汽蚀",
        "head_type": "FaultMode",
        "head_terminology_id": "MPTERM-FAULT-CAVITATION",
        "head_translation_status": "dictionary_approved",
        "relation": "manifests_as",
        "relation_label_zh": "表现为",
        "tail": "high vibration",
        "tail_surface": "high vibration",
        "tail_canonical_zh": "振动过大",
        "tail_type": "Symptom",
        "tail_terminology_id": "MPTERM-SYMPTOM-HIGH-VIBRATION",
        "tail_translation_status": "dictionary_approved",
        "head_type_label_zh": "故障模式",
        "tail_type_label_zh": "症状",
        "doc_id": doc_id,
        "document_split": document_split,
        "publisher": "Test pump manufacturer",
        "source_family_id": "ABS",
        "source_url": "https://example.org/pump-manual.pdf",
        "document_sha256": "A" * 64,
        "page_text_sha256": "b" * 64,
        "pdf_page_number": 5,
        "source_language": "en",
        "evidence_text": evidence_text,
        "evidence_level": "E1",
        "evidence_start": 0,
        "evidence_end": len(evidence_text),
        "evidence_units": [],
        "evidence_validation": {"valid": True},
        "relation_type_valid": True,
        "relation_entailment_valid": True,
        "inferred_edge": False,
        "eligible_for_chinese_graph": True,
        "graph_display_language": "zh-CN",
        "decision": "silver_candidate",
        "validation_status": "silver_candidate",
        "fault_class_ids": ["cavitation"],
        "applicability_scope": "marine pump system",
    }
    head_id = stable_entity_id(
        "汽蚀",
        "FaultMode",
        terminology_id="MPTERM-FAULT-CAVITATION",
    )
    tail_id = stable_entity_id(
        "振动过大",
        "Symptom",
        terminology_id="MPTERM-SYMPTOM-HIGH-VIBRATION",
    )
    claim_id = stable_claim_id(head_id, "manifests_as", tail_id)
    evidence_id = stable_evidence_id(record, claim_id=claim_id)
    record.update(
        {
            "head_entity_id": head_id,
            "tail_entity_id": tail_id,
            "claim_id": claim_id,
            "evidence_id": evidence_id,
            "assertion_id": evidence_id,
            "triple_id": stable_triple_id(claim_id, evidence_id),
        }
    )
    return record


def _layers(record: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    entities = [
        {
            "entity_id": record["head_entity_id"],
            "canonical_label_zh": record["head_canonical_zh"],
            "entity_type": record["head_type"],
            "terminology_id": record["head_terminology_id"],
            "graph_display_language": "zh-CN",
            "source_surfaces": [record["head_surface"]],
        },
        {
            "entity_id": record["tail_entity_id"],
            "canonical_label_zh": record["tail_canonical_zh"],
            "entity_type": record["tail_type"],
            "terminology_id": record["tail_terminology_id"],
            "graph_display_language": "zh-CN",
            "source_surfaces": [record["tail_surface"]],
        },
    ]
    claims = [
        {
            "claim_id": record["claim_id"],
            "head_entity_id": record["head_entity_id"],
            "relation": record["relation"],
            "relation_label_zh": record["relation_label_zh"],
            "tail_entity_id": record["tail_entity_id"],
            "fault_class_ids": record["fault_class_ids"],
        }
    ]
    evidence = [
        {
            "evidence_id": record["evidence_id"],
            "doc_id": record["doc_id"],
            "pdf_page_number": record["pdf_page_number"],
            "source_url": record["source_url"],
            "source_family_id": record["source_family_id"],
            "evidence_text": record["evidence_text"],
            "evidence_level": record["evidence_level"],
            "document_sha256": record["document_sha256"],
            "page_text_sha256": record["page_text_sha256"],
            "applicability_scope": record["applicability_scope"],
        }
    ]
    links = [
        {
            "assertion_id": record["evidence_id"],
            "claim_id": record["claim_id"],
            "evidence_id": record["evidence_id"],
            "decision": record["decision"],
            "eligible_for_chinese_graph": True,
            "inferred_edge": False,
            "relation_entailment_valid": True,
            "triple_id": record["triple_id"],
        }
    ]
    return {
        "source_records": [record],
        "entities": entities,
        "claims": claims,
        "evidence_assertions": evidence,
        "claim_evidence_links": links,
    }


def _write_package(
    graph_root: Path,
    version: str,
    record: dict[str, object],
) -> None:
    directory = graph_root / "triples" / version
    directory.mkdir(parents=True)
    for layer_name, records in _layers(record).items():
        path = directory / f"{layer_name}.jsonl"
        path.write_text(
            "".join(
                json.dumps(item, ensure_ascii=False) + "\n"
                for item in records
            ),
            encoding="utf-8",
        )


class GraphConstraintReportTests(unittest.TestCase):
    def _generate(
        self,
        graph_root: Path,
    ) -> dict[str, object]:
        return generate_graph_constraint_report(
            project_root=PROJECT_ROOT,
            graph_root=graph_root,
            schema_path=SCHEMA_PATH,
            terminology_path=TERMINOLOGY_PATH,
            split_path=SPLIT_PATH,
        )

    def test_valid_layered_packages_are_not_release_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            graph_root = Path(directory)
            record = _valid_source_record()
            _write_package(graph_root, "KG_v1_raw", copy.deepcopy(record))
            _write_package(
                graph_root,
                "KG_v1_validated",
                copy.deepcopy(record),
            )

            report = self._generate(graph_root)

        self.assertFalse(report["summary"]["release_blocked"])
        self.assertEqual(report["summary"]["release_blocking_checks"], 0)
        self.assertEqual(report["summary"]["failed_checks"], 0)
        markdown = render_graph_constraint_report_markdown(report)
        self.assertIn("不是完整JSON Schema验证、RDF验证或SHACL验证", markdown)
        self.assertIn("Silver only; never Gold", markdown)

    def test_heldout_leakage_and_missing_url_block_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            graph_root = Path(directory)
            raw_record = _valid_source_record()
            invalid_record = _valid_source_record(
                doc_id="MP009",
                document_split="held_out_test",
            )
            invalid_record["source_url"] = ""
            new_evidence_id = stable_evidence_id(
                invalid_record,
                claim_id=str(invalid_record["claim_id"]),
            )
            invalid_record.update(
                {
                    "evidence_id": new_evidence_id,
                    "assertion_id": new_evidence_id,
                    "triple_id": stable_triple_id(
                        str(invalid_record["claim_id"]),
                        new_evidence_id,
                    ),
                }
            )
            _write_package(graph_root, "KG_v1_raw", raw_record)
            _write_package(graph_root, "KG_v1_validated", invalid_record)

            report = self._generate(graph_root)

        self.assertTrue(report["summary"]["release_blocked"])
        failed_ids = {
            check["rule_id"]
            for check in report["checks"]
            if check["status"] == "fail"
        }
        self.assertIn("SPLIT001_PRIMARY_GRAPH_BUILD_ONLY", failed_ids)
        self.assertIn("PROV001_CORE_FIELDS_PRESENT", failed_ids)
        self.assertIn("PROV002_PAGE_URL_HASH_FORMAT", failed_ids)
        self.assertIn(
            "RELEASE001_VALIDATED_SUBSET_WITH_IMMUTABLE_EVIDENCE",
            failed_ids,
        )

    def test_missing_evidence_level_uses_powershell_safe_counter_key(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            graph_root = Path(directory)
            raw_record = _valid_source_record()
            raw_record["decision"] = "rejected"
            raw_record["validation_status"] = "rejected"
            raw_record["evidence_level"] = ""
            _write_package(graph_root, "KG_v1_raw", raw_record)
            _write_package(
                graph_root,
                "KG_v1_validated",
                _valid_source_record(),
            )

            report = self._generate(graph_root)

        levels = report["packages"]["KG_v1_raw"]["evidence_levels"]
        self.assertEqual(levels, {"MISSING": 1})
        self.assertNotIn("", levels)


if __name__ == "__main__":
    unittest.main()
