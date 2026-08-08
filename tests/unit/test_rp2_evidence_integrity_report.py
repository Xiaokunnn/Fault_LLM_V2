from __future__ import annotations

import json
from pathlib import Path

from scripts.build_rp2_evidence_integrity_report import build_report


ROOT = Path(__file__).resolve().parents[2]


def test_validated_release_records_pass_all_seven_integrity_checks() -> None:
    source = (
        ROOT
        / "data/kg/marine_pump/triples/KG_v1_validated/source_records.jsonl"
    )
    records = [json.loads(line) for line in source.open(encoding="utf-8") if line.strip()]
    report, audit = build_report(records, source)
    assert report["records"] == 208
    assert report["all_checks_pass_rate"] == 1.0
    assert len(audit) == 208
    assert all(row["integrity_conjunction"] for row in audit)
    assert report["human_expert_reviewed"] is False
    assert report["label_policy"] == "Silver only; never Gold"


def test_e2_table_evidence_uses_same_row_bbox_page_anchor() -> None:
    source = (
        ROOT
        / "data/kg/marine_pump/triples/KG_v1_validated/source_records.jsonl"
    )
    records = [json.loads(line) for line in source.open(encoding="utf-8") if line.strip()]
    e2 = next(row for row in records if row["evidence_level"] == "E2")
    report, audit = build_report([e2], source)
    assert report["all_checks_pass_rate"] == 1.0
    assert audit[0]["page_grounded"] is True
