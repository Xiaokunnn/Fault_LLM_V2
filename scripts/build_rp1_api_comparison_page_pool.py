#!/usr/bin/env python3
"""Freeze 20 evidence-rich build pages for the real API prompt comparison."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/kg/marine_pump/triples/KG_v1_raw/source_records.jsonl"
OUTPUT = ROOT / "configs/rp1_api_comparison_pages_v1.jsonl"


def main() -> int:
    rows = []
    with SOURCE.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("decision") != "silver_candidate":
                continue
            if row.get("document_split") != "build_train":
                continue
            if row.get("evidence_level") not in {"E1", "E2"}:
                continue
            if not row.get("fault_class_ids"):
                continue
            rows.append(row)

    page_rows: dict[tuple[str, int], dict] = {}
    by_fault_level: dict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
    for row in rows:
        key = (str(row["doc_id"]), int(row["pdf_page_number"]))
        item = page_rows.setdefault(
            key,
            {
                "doc_id": key[0],
                "pdf_page_number": key[1],
                "target_fault_classes": set(),
                "target_evidence_roles": set(),
                "evidence_levels": set(),
                "silver_record_count": 0,
            },
        )
        item["target_fault_classes"].update(str(v) for v in row.get("fault_class_ids", []))
        item["target_evidence_roles"].add(str(row.get("evidence_role") or ""))
        item["evidence_levels"].add(str(row.get("evidence_level") or ""))
        item["silver_record_count"] += 1
        for fault_id in row.get("fault_class_ids", []):
            by_fault_level[(str(fault_id), str(row["evidence_level"]))].append(key)

    selected: list[tuple[str, int]] = []
    faults = sorted({fault for fault, _ in by_fault_level})
    for fault_id in faults:
        for level in ("E1", "E2"):
            choices = sorted(
                set(by_fault_level.get((fault_id, level), [])),
                key=lambda key: (-page_rows[key]["silver_record_count"], key),
            )
            choice = next((key for key in choices if key not in selected), None)
            if choice is None and choices:
                choice = choices[0]
            if choice is not None and choice not in selected:
                selected.append(choice)

    remaining = sorted(
        (key for key in page_rows if key not in selected),
        key=lambda key: (-page_rows[key]["silver_record_count"], key),
    )
    selected.extend(remaining[: max(0, 20 - len(selected))])
    selected = selected[:20]
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        for key in selected:
            item = page_rows[key]
            payload = {
                "doc_id": item["doc_id"],
                "pdf_page_number": item["pdf_page_number"],
                "target_fault_classes": sorted(item["target_fault_classes"]),
                "target_evidence_roles": sorted(v for v in item["target_evidence_roles"] if v),
                "selection_evidence_levels": sorted(item["evidence_levels"]),
                "selection_silver_record_count": item["silver_record_count"],
                "selection_policy": "stratified_evidence_rich_build_page_not_corpus_random_sample",
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    print(f"[RP1 API pages] faults={len(faults)}, pages={len(selected)}, output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
