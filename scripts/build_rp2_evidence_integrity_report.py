#!/usr/bin/env python3
"""Build paper-facing Silver evidence-integrity metrics for the RP2 substrate.

The report evaluates deterministic release properties of every source record in
``KG_v1_validated``.  It deliberately does not claim human-expert factual
correctness.  Original evidence text, source-language surfaces, page numbers,
URLs, and hashes are read only and copied only as audit identifiers.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _present(row: dict[str, Any], *fields: str) -> bool:
    return all(row.get(field) not in (None, "", [], {}) for field in fields)


def _schema_legal(row: dict[str, Any]) -> bool:
    return bool(
        _present(
            row,
            "head_entity_id",
            "tail_entity_id",
            "claim_id",
            "evidence_id",
            "relation",
            "head_type",
            "tail_type",
        )
        and row.get("decision") == "silver_candidate"
        and row.get("graph_release_status") == "core_silver_ready"
        and row.get("eligible_for_chinese_graph") is True
        and row.get("relation_type_validation", {}).get("valid") is True
    )


def _entity_anchor(row: dict[str, Any]) -> bool:
    canonical = row.get("chinese_canonicalization", {})
    return bool(
        _present(
            row,
            "head_canonical_zh",
            "tail_canonical_zh",
            "head_terminology_id",
            "tail_terminology_id",
        )
        and canonical.get("graph_ready") is True
        and canonical.get("head", {}).get("graph_ready") is True
        and canonical.get("tail", {}).get("graph_ready") is True
    )


def _direct_relation_support(row: dict[str, Any]) -> bool:
    evidence = row.get("evidence_validation", {})
    entailment = row.get("relation_entailment_validation", {})
    return bool(
        _present(row, "evidence_text", "evidence_level")
        and evidence.get("valid") is True
        and evidence.get("silver_eligible") is True
        and entailment.get("valid") is True
        and entailment.get("status") == "entailed"
        and entailment.get("silver_eligible") is True
    )


def _direction_consistent(row: dict[str, Any]) -> bool:
    """Check direction after deterministic normalization, not expert semantics."""

    canonical = row.get("chinese_canonicalization", {})
    return bool(
        row.get("relation_type_valid") is True
        and row.get("relation_entailment_valid") is True
        and canonical.get("relation_code") == row.get("relation")
        and not row.get("relation_type_validation", {}).get("reasons")
        and not row.get("relation_entailment_validation", {}).get("hard_veto_reasons")
    )


def _non_inferred(row: dict[str, Any]) -> bool:
    return row.get("inferred_edge") is False


def _page_grounded(row: dict[str, Any]) -> bool:
    validation = row.get("evidence_validation", {})
    page = row.get("pdf_page_number")
    start = row.get("evidence_start")
    end = row.get("evidence_end")
    level = row.get("evidence_level")
    e1_anchor = (
        level == "E1"
        and isinstance(start, int)
        and isinstance(end, int)
        and 0 <= start < end
        and validation.get("match_method") not in (None, "")
    )
    units = validation.get("units", [])
    e2_anchor = (
        level == "E2"
        and bool(row.get("evidence_unit_ids"))
        and bool(units)
        and validation.get("alignment_method") not in (None, "")
        and all(
            unit.get("row_id")
            and isinstance(unit.get("bbox"), list)
            and len(unit["bbox"]) == 4
            for unit in units
        )
    )
    return bool(
        isinstance(page, int)
        and page > 0
        and validation.get("valid") is True
        and (e1_anchor or e2_anchor)
    )


def _provenance_complete(row: dict[str, Any]) -> bool:
    return bool(
        _present(
            row,
            "doc_id",
            "document_split",
            "source_family_id",
            "source_url",
            "publisher",
            "document_sha256",
            "page_text_sha256",
            "pdf_page_number",
            "evidence_text",
        )
        and str(row.get("source_url", "")).startswith(("http://", "https://"))
        and SHA256_RE.fullmatch(str(row.get("document_sha256", ""))) is not None
        and SHA256_RE.fullmatch(str(row.get("page_text_sha256", ""))) is not None
    )


CHECKS: tuple[tuple[str, str, Callable[[dict[str, Any]], bool]], ...] = (
    ("schema_legal", "Schema legality", _schema_legal),
    ("entity_anchor", "Chinese canonical entity anchoring", _entity_anchor),
    ("direct_relation_support", "Direct relation support", _direct_relation_support),
    ("direction_consistent", "Normalized direction consistency", _direction_consistent),
    ("non_inferred", "Non-inferred release edge", _non_inferred),
    ("page_grounded", "Page-grounded evidence span", _page_grounded),
    ("provenance_complete", "Provenance completeness", _provenance_complete),
)


def build_report(records: list[dict[str, Any]], source_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    audit_rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for row in records:
        flags = {check_id: bool(predicate(row)) for check_id, _, predicate in CHECKS}
        for check_id, passed in flags.items():
            counts[check_id] += int(passed)
        all_passed = all(flags.values())
        counts["integrity_conjunction"] += int(all_passed)
        audit_rows.append(
            {
                "evidence_id": row.get("evidence_id"),
                "claim_id": row.get("claim_id"),
                "doc_id": row.get("doc_id"),
                "pdf_page_number": row.get("pdf_page_number"),
                "source_family_id": row.get("source_family_id"),
                **flags,
                "integrity_conjunction": all_passed,
            }
        )

    total = len(records)
    metrics = [
        {
            "id": check_id,
            "name": name,
            "passed": counts[check_id],
            "evaluated": total,
            "rate": counts[check_id] / total if total else None,
        }
        for check_id, name, _ in CHECKS
    ]
    metrics.append(
        {
            "id": "integrity_conjunction",
            "name": "All seven deterministic release checks",
            "passed": counts["integrity_conjunction"],
            "evaluated": total,
            "rate": counts["integrity_conjunction"] / total if total else None,
        }
    )
    report = {
        "report_schema": "rp2_silver_evidence_integrity_v1",
        "definition": (
            "Integrity(t)=SchemaLegal AND EntityAnchor AND DirectRelationSupport "
            "AND DirectionConsistent AND NonInferred AND PageGrounded "
            "AND ProvenanceComplete"
        ),
        "scope": "KG_v1_validated release source records",
        "interpretation": (
            "Deterministic structural, grounding, and provenance integrity of Silver "
            "records; not human-expert factual correctness."
        ),
        "direction_check_boundary": (
            "Consistency of the released normalized relation direction with the "
            "validated claim and relation registry; not an independent expert judgment."
        ),
        "hash_check_boundary": (
            "This report validates SHA-256 field presence and format. It does not "
            "recompute copyrighted source-PDF or page-text hashes."
        ),
        "records": total,
        "documents": len({str(row.get("doc_id")) for row in records if row.get("doc_id")}),
        "source_families": len(
            {str(row.get("source_family_id")) for row in records if row.get("source_family_id")}
        ),
        "metrics": metrics,
        "all_checks_pass_rate": (
            counts["integrity_conjunction"] / total if total else None
        ),
        "input": {
            "path": source_path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(source_path),
        },
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    return report, audit_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-records",
        default="data/kg/marine_pump/triples/KG_v1_validated/source_records.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "results/experiments/research_point_2/"
            "evidence_integrity_v1"
        ),
    )
    args = parser.parse_args()
    source_path = ROOT / args.source_records
    output = ROOT / args.output_dir
    records = _read_jsonl(source_path)
    report, audit_rows = build_report(records, source_path)
    output.mkdir(parents=True, exist_ok=True)
    (output / "evidence_integrity_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output / "evidence_integrity_audit.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]) if audit_rows else [])
        if audit_rows:
            writer.writeheader()
            writer.writerows(audit_rows)
    lines = [
        "# RP2 Silver evidence-integrity report",
        "",
        f"- Records: {report['records']}",
        f"- Documents: {report['documents']}",
        f"- Source families: {report['source_families']}",
        "- Human expert reviewed: false",
        "- Label policy: Silver only; never Gold",
        "",
        "| Check | Passed | Evaluated | Rate |",
        "|---|---:|---:|---:|",
    ]
    for metric in report["metrics"]:
        rate = "N/A" if metric["rate"] is None else f"{metric['rate']:.4f}"
        lines.append(
            f"| {metric['name']} | {metric['passed']} | {metric['evaluated']} | {rate} |"
        )
    lines.extend(
        [
            "",
            "> These rates measure deterministic release integrity of Silver records,",
            "> not expert-confirmed factual accuracy. Hashes are format-checked here, not recomputed.",
        ]
    )
    (output / "evidence_integrity_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(
        f"[RP2 integrity] records={report['records']}, "
        f"all-seven={report['all_checks_pass_rate']:.4f}, output={output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
