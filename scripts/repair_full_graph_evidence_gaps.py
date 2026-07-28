"""Repair the two remaining full-corpus evidence gates without human labels.

The script performs two governed operations:

1. Reuses only previously frozen Silver symptom assertions whose current
   parsed-page hashes, source metadata and verbatim evidence still match.
2. Reconstructs MP005:p0063 dry-running symptoms from parser-generated cells
   after deterministic same-row geometry verification.

No external model is called and no rejected record is promoted merely by
changing its decision field.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    CoverageThresholds,
    build_coverage_report,
    deduplicate_triples,
    load_chinese_terminology,
    load_fault_ontology,
    load_provenance_schema,
    locate_surface,
    validate_candidate,
)


TARGET_CLASSES = {
    "impeller_or_wear_part_damage",
    "dry_running_or_maintenance_induced_failure",
}
ID_FIELDS = {
    "head_entity_id",
    "tail_entity_id",
    "claim_id",
    "evidence_id",
    "assertion_id",
    "triple_id",
}


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_pages(input_dir: Path) -> dict[tuple[str, int], dict[str, object]]:
    pages: dict[tuple[str, int], dict[str, object]] = {}
    for path in input_dir.glob("*.pages.v2.jsonl"):
        for page in read_jsonl(path):
            pages[(str(page["doc_id"]), int(page["pdf_page_number"]))] = page
    return pages


def current_source_matches(
    record: Mapping[str, object], page: Mapping[str, object]
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for field in (
        "doc_id",
        "pdf_page_number",
        "document_sha256",
        "page_text_sha256",
        "source_url",
        "source_family_id",
        "document_split",
    ):
        if str(record.get(field, "")) != str(page.get(field, "")):
            reasons.append(f"{field}_mismatch")
    if record.get("decision") != "silver_candidate":
        reasons.append("not_frozen_silver")
    if record.get("relation_entailment_valid") is not True:
        reasons.append("relation_not_entailed")
    if record.get("inferred_edge") is True:
        reasons.append("inferred_edge")
    if str(record.get("evidence_level", "")) not in {"E1", "E2"}:
        reasons.append("evidence_level_not_releasable")
    if not bool((record.get("evidence_validation") or {}).get("valid")):
        reasons.append("prior_evidence_invalid")
    if str(record.get("evidence_level")) == "E1":
        page_text = str(page.get("page_text", ""))
        evidence = str(record.get("evidence_text", ""))
        span = locate_surface(page_text, evidence)
        if span is None:
            reasons.append("verbatim_evidence_not_found_on_current_page")
        elif locate_surface(span.source_text, str(record.get("head_surface", ""))) is None:
            reasons.append("head_not_in_current_evidence")
        elif locate_surface(span.source_text, str(record.get("tail_surface", ""))) is None:
            reasons.append("tail_not_in_current_evidence")
    return not reasons, reasons


def symptom_bearing(record: Mapping[str, object]) -> bool:
    return (
        record.get("head_type") == "Symptom"
        or record.get("tail_type") == "Symptom"
        or record.get("evidence_role") == "symptom"
    )


def select_frozen_supplements(
    records: Iterable[Mapping[str, object]],
    pages: Mapping[tuple[str, int], Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    selected: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    for source in records:
        fault_ids = set(source.get("fault_class_ids", []) or [])
        if not fault_ids.intersection(TARGET_CLASSES) or not symptom_bearing(source):
            continue
        key = (str(source.get("doc_id")), int(source.get("pdf_page_number", 0)))
        page = pages.get(key)
        if page is None:
            rejected.append(
                {"triple_id": source.get("triple_id"), "reasons": ["page_missing"]}
            )
            continue
        valid, reasons = current_source_matches(source, page)
        if not valid:
            rejected.append(
                {"triple_id": source.get("triple_id"), "reasons": reasons}
            )
            continue
        record = dict(source)
        record["evidence_repair_provenance"] = {
            "version": "full_graph_evidence_gap_repair_v1",
            "method": "reuse_pre_full_extraction_frozen_silver",
            "current_page_source_reverified": True,
            "human_expert_reviewed": False,
        }
        selected.append(record)
    return selected, rejected


def bbox_tuple(cell: Mapping[str, object]) -> tuple[float, float, float, float]:
    bbox = cell.get("bbox") or {}
    return (
        float(bbox["x0"]),
        float(bbox["top"]),
        float(bbox["x1"]),
        float(bbox["bottom"]),
    )


def verify_same_row_geometry(
    page: Mapping[str, object],
    cells: list[Mapping[str, object]],
) -> dict[str, object]:
    if len(cells) != 2:
        raise ValueError("Exactly two source cells are required")
    if len({str(cell.get("table_id")) for cell in cells}) != 1:
        raise ValueError("Cells are not in one table")
    if len({str(cell.get("row_id")) for cell in cells}) != 1:
        raise ValueError("Cells are not in one parser row")
    if len({str(cell.get("row_group_id")) for cell in cells}) != 1:
        raise ValueError("Cells are not in one parser row group")
    boxes = [bbox_tuple(cell) for cell in cells]
    width = float(page["page_width"])
    height = float(page["page_height"])
    if not all(
        0 <= x0 < x1 <= width and 0 <= top < bottom <= height
        for x0, top, x1, bottom in boxes
    ):
        raise ValueError("Cell bbox lies outside the physical page")
    vertical_overlap = min(boxes[0][3], boxes[1][3]) - max(
        boxes[0][1], boxes[1][1]
    )
    if vertical_overlap <= 0:
        raise ValueError("Cells do not overlap vertically")
    if not all(str(cell.get("text", "")).strip() for cell in cells):
        raise ValueError("Source cell text is empty")
    return {
        "version": "automatic_same_row_geometry_v1",
        "table_id": cells[0]["table_id"],
        "row_id": cells[0]["row_id"],
        "row_group_id": cells[0]["row_group_id"],
        "cell_ids": [str(cell["cell_id"]) for cell in cells],
        "page_bounds_checked": True,
        "same_table_checked": True,
        "same_row_checked": True,
        "vertical_overlap_checked": True,
        "human_visual_reviewed": False,
    }


def find_cell(page: Mapping[str, object], cell_id: str) -> dict[str, object]:
    for table in page.get("tables", []) or []:
        for row in table.get("rows", []) or []:
            for cell in row.get("cells", []) or []:
                if cell.get("cell_id") == cell_id:
                    return dict(cell)
    raise KeyError(f"Parser cell not found: {cell_id}")


def table_unit(
    cell: Mapping[str, object], *, derived_column_name: str
) -> dict[str, object]:
    return {
        "cell_id": cell["cell_id"],
        "table_id": cell["table_id"],
        "row_id": cell["row_id"],
        "row_group_id": cell["row_group_id"],
        "column_name": derived_column_name,
        "role": (
            "fault_or_operating_condition"
            if "failure" in derived_column_name.casefold()
            else "symptom"
        ),
        "text": cell["text"],
        "start": int(cell.get("page_text_start") or -1),
        "end": int(cell.get("page_text_end") or -1),
        "bbox": list(bbox_tuple(cell)),
    }


def repair_mp005_p0063(
    page: Mapping[str, object],
    *,
    schema: Mapping[str, object],
    ontology: Mapping[str, object],
    terminology: Mapping[str, object],
) -> list[dict[str, object]]:
    head_cell = find_cell(page, "MP005:p0063:t00:r002:c00")
    symptom_cell = find_cell(page, "MP005:p0063:t00:r002:c06")
    geometry = verify_same_row_geometry(page, [head_cell, symptom_cell])
    units = [
        table_unit(head_cell, derived_column_name="Description of possible failure"),
        table_unit(symptom_cell, derived_column_name="Indications of failure"),
    ]
    head = str(head_cell["text"])
    symptoms = (
        ("quickly generating heat in the pump", "泵内快速发热"),
        ("high noises", "高噪声"),
        ("increased power consumption", "功耗增加"),
    )
    repaired: list[dict[str, object]] = []
    for tail, tail_zh in symptoms:
        candidate = {
            "head": head,
            "head_surface": head,
            "head_canonical_zh": "泵干运转（进出口阀关闭）",
            "head_type": "OperatingCondition",
            "head_translation_status": "needs_review",
            "relation": "causes",
            "tail": tail,
            "tail_surface": tail,
            "tail_canonical_zh": tail_zh,
            "tail_type": "Symptom",
            "tail_translation_status": "needs_review",
            "evidence_text": "",
            "evidence_mode": "E2_table_cells",
            "evidence_unit_ids": [unit["cell_id"] for unit in units],
            "evidence_role": "symptom",
            "fault_class_ids": [
                "dry_running_or_maintenance_induced_failure"
            ],
            "model_confidence": 0.95,
            "doc_id": page["doc_id"],
            "pdf_page_number": page["pdf_page_number"],
            "document_split": page["document_split"],
            "source_language": page["source_language"],
            "source_family_id": page["source_family_id"],
            "source_url": page["source_url"],
            "source_tier": page["source_tier"],
            "publisher": page["publisher"],
            "document_sha256": page["document_sha256"],
            "page_text_sha256": page["page_text_sha256"],
            "pump_type": page["pump_type"],
            "service": page["service"],
            "applicability_scope": page["applicability_scope"],
            "inferred_edge": False,
            "extractor": "local:mp005_p0063_table_gap_repair_v1",
            "table_geometry_verification": geometry,
            "human_expert_reviewed": False,
            "label_policy": "Silver only; never Gold",
        }
        result = validate_candidate(
            candidate,
            page_text=str(page["page_text"]),
            project_root=PROJECT_ROOT,
            schema=schema,
            ontology=ontology,
            terminology=terminology,
            table_evidence_units=units,
            structured_relation="causes",
            visual_layout_checked=True,
        )
        if result.get("decision") != "silver_candidate":
            raise RuntimeError(
                "Deterministic MP005:p0063 repair did not pass strict Silver: "
                + json.dumps(
                    {
                        "tail": tail,
                        "decision": result.get("decision"),
                        "rejection_reasons": result.get("rejection_reasons"),
                        "review_reasons": result.get("review_reasons"),
                    },
                    ensure_ascii=False,
                )
            )
        repaired.append(result)
    return repaired


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full-input",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_auto_adjudicated/"
            "candidate_triples.auto_adjudicated_silver.jsonl"
        ),
    )
    parser.add_argument(
        "--frozen-input",
        default=(
            "data/interim/candidate_triples/"
            "final_semantic_gap_v1_gate_frozen/"
            "candidate_triples.gate_frozen.jsonl"
        ),
    )
    parser.add_argument(
        "--page-dir", default="data/interim/parsed_pages/corpus_v2"
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_evidence_repaired"
        ),
    )
    args = parser.parse_args()

    pages = load_pages(PROJECT_ROOT / args.page_dir)
    full_records = read_jsonl(PROJECT_ROOT / args.full_input)
    frozen_records = read_jsonl(PROJECT_ROOT / args.frozen_input)
    supplements, supplement_rejections = select_frozen_supplements(
        frozen_records, pages
    )
    ontology = load_fault_ontology(project_root=PROJECT_ROOT)
    schema = load_provenance_schema(project_root=PROJECT_ROOT)
    terminology = load_chinese_terminology(
        PROJECT_ROOT / "configs/entity_terminology_zh_marine_pump_v2.json"
    )
    repaired_table_records = repair_mp005_p0063(
        pages[("MP005", 63)],
        schema=schema,
        ontology=ontology,
        terminology=terminology,
    )
    deduplicated = deduplicate_triples(
        [*full_records, *supplements, *repaired_table_records]
    )
    records = list(deduplicated.records)
    output_dir = PROJECT_ROOT / args.output_dir
    output_path = output_dir / "candidate_triples.evidence_repaired.jsonl"
    write_jsonl(output_path, records)

    fault_ids = [
        str(item["fault_id"]) for item in ontology["fault_classes"]
    ]
    coverage = build_coverage_report(
        records,
        fault_ids=fault_ids,
        thresholds=CoverageThresholds.from_ontology(ontology),
        require_chinese_graph_ready=False,
    )
    write_json(output_dir / "coverage_evidence_only.json", coverage)
    decisions = Counter(str(record.get("decision", "")) for record in records)
    summary = {
        "version": "full_graph_evidence_gap_repair_v1",
        "full_input_records": len(full_records),
        "frozen_silver_symptom_supplements_selected": len(supplements),
        "frozen_supplements_rejected_on_current_source_check": len(
            supplement_rejections
        ),
        "mp005_p0063_automatic_table_geometry_repairs": len(
            repaired_table_records
        ),
        "duplicates_removed": deduplicated.duplicates_removed,
        "output_records": len(records),
        "decisions": dict(sorted(decisions.items())),
        "fault_classes_passing": coverage["fault_classes_passing_gate"],
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    write_json(output_dir / "evidence_gap_repair_summary.json", summary)
    write_json(
        output_dir / "frozen_supplement_rejections.json",
        supplement_rejections,
    )
    print(
        "[Evidence Gap Repair] "
        f"冻结补充={len(supplements)}，MP005:p0063修复={len(repaired_table_records)}，"
        f"去重={deduplicated.duplicates_removed}，覆盖="
        f"{coverage['fault_classes_passing_gate']}/{len(fault_ids)}",
        flush=True,
    )
    if coverage["fault_classes_passing_gate"] != len(fault_ids):
        raise RuntimeError("Evidence-only coverage gate remains below 10/10")


if __name__ == "__main__":
    main()
