"""Run deterministic evidence-contract validation experiments for RP1.

This script performs two non-human, non-LLM evaluations against the frozen
full-corpus candidate file and the parser-preserved physical-page objects:

1. an all-candidate locator/provenance audit; and
2. controlled fault injection on release-qualified records.

The experiment tests executable contract behaviour only.  It does not assess
domain truth, factual accuracy, or expert agreement.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    load_provenance_schema,
    locate_surface,
    validate_relation_type,
)


EXPERIMENT_VERSION = "evidence_contract_validation_v1"
QUALIFIED_DECISIONS = {"silver_candidate", "accepted_silver"}
QUARANTINED_DECISIONS = {"candidate_needs_review", "context_only_reviewed"}
PROVENANCE_FIELDS = (
    "doc_id",
    "pdf_page_number",
    "publisher",
    "source_family_id",
    "source_url",
    "document_sha256",
    "page_text_sha256",
    "document_split",
    "source_language",
)
SOURCE_MATCH_FIELDS = (
    "doc_id",
    "pdf_page_number",
    "publisher",
    "source_family_id",
    "source_url",
    "document_sha256",
    "page_text_sha256",
    "document_split",
    "source_language",
)
HASH_FIELDS = ("document_sha256", "page_text_sha256")


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def valid_hash(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdefABCDEF" for char in text)


def valid_http_url(value: object) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def decision_group(record: Mapping[str, object]) -> str:
    decision = str(record.get("decision", ""))
    if decision in QUALIFIED_DECISIONS:
        return "evidence_qualified"
    if decision in QUARANTINED_DECISIONS:
        return "quarantined"
    return "rejected"


def load_pages(
    page_dir: Path,
) -> tuple[dict[tuple[str, int], dict[str, object]], list[dict[str, object]], list[Path]]:
    pages: dict[tuple[str, int], dict[str, object]] = {}
    duplicate_keys: list[dict[str, object]] = []
    paths = sorted(page_dir.glob("*.pages.v2.jsonl"))
    for path in paths:
        for page in read_jsonl(path):
            key = (str(page.get("doc_id", "")), int(page.get("pdf_page_number", 0) or 0))
            if key in pages:
                duplicate_keys.append({"doc_id": key[0], "pdf_page_number": key[1]})
            pages[key] = page
    return pages, duplicate_keys, paths


def parser_cells(page: Mapping[str, object]) -> dict[str, dict[str, object]]:
    cells: dict[str, dict[str, object]] = {}
    for table in page.get("tables", []) or []:
        for row in table.get("rows", []) or []:
            for cell in row.get("cells", []) or []:
                cell_id = str(cell.get("cell_id", ""))
                if cell_id:
                    cells[cell_id] = dict(cell)
    return cells


def bbox_values(value: object) -> tuple[float, float, float, float] | None:
    if isinstance(value, Mapping):
        try:
            return (
                float(value["x0"]),
                float(value["top"]),
                float(value["x1"]),
                float(value["bottom"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if len(value) != 4:
            return None
        try:
            return tuple(float(item) for item in value)  # type: ignore[return-value]
        except (TypeError, ValueError):
            return None
    return None


def bbox_in_page(
    bbox: tuple[float, float, float, float] | None,
    *,
    width: float,
    height: float,
) -> bool:
    if bbox is None:
        return False
    x0, top, x1, bottom = bbox
    return 0 <= x0 < x1 <= width and 0 <= top < bottom <= height


def bbox_equal(left: object, right: object, tolerance: float = 0.01) -> bool:
    left_values = bbox_values(left)
    right_values = bbox_values(right)
    if left_values is None or right_values is None:
        return False
    return all(abs(a - b) <= tolerance for a, b in zip(left_values, right_values))


def table_unit_references(record: Mapping[str, object]) -> list[dict[str, object]]:
    units = record.get("evidence_units") or []
    if isinstance(units, list) and units:
        return [dict(item) for item in units if isinstance(item, Mapping)]
    unit_ids = record.get("evidence_unit_ids") or []
    if isinstance(unit_ids, list):
        return [{"cell_id": str(item)} for item in unit_ids if str(item)]
    return []


def audit_record(
    record: Mapping[str, object],
    pages: Mapping[tuple[str, int], Mapping[str, object]],
    *,
    schema: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Independently cross-check a candidate against frozen parsed-page data."""

    doc_id = str(record.get("doc_id", ""))
    try:
        page_number = int(record.get("pdf_page_number", 0) or 0)
    except (TypeError, ValueError):
        page_number = 0
    key = (doc_id, page_number)
    page = pages.get(key)
    level = str(record.get("evidence_level", "") or "")
    checks: dict[str, bool | None] = {}
    checks["page_resolved"] = page is not None
    checks["provenance_fields_complete"] = all(
        record.get(field) not in (None, "") for field in PROVENANCE_FIELDS
    )
    checks["hash_fields_well_formed"] = all(valid_hash(record.get(field)) for field in HASH_FIELDS)
    checks["source_url_well_formed"] = valid_http_url(record.get("source_url"))
    schema = schema or load_provenance_schema(project_root=PROJECT_ROOT)
    checks["relation_schema_valid"] = validate_relation_type(
        relation=str(record.get("relation", "")),
        head_type=str(record.get("head_type", "")),
        tail_type=str(record.get("tail_type", "")),
        schema=schema,
    ).valid

    if page is None:
        checks.update(
            {
                "page_payload_hash_valid": False,
                "source_metadata_match": False,
                "evidence_located": False,
                "endpoints_located_in_evidence": False,
                "table_units_valid": None if level != "E2" else False,
            }
        )
    else:
        page_text = str(page.get("page_text", ""))
        computed_page_hash = hashlib.sha256(page_text.encode("utf-8")).hexdigest()
        checks["page_payload_hash_valid"] = computed_page_hash.casefold() == str(
            page.get("page_text_sha256", "")
        ).casefold()
        checks["source_metadata_match"] = all(
            str(record.get(field, "")) == str(page.get(field, ""))
            for field in SOURCE_MATCH_FIELDS
        )

        if level == "E2":
            references = table_unit_references(record)
            source_cells = parser_cells(page)
            resolved: list[tuple[dict[str, object], dict[str, object]]] = []
            missing_ids = False
            metadata_match = True
            recorded_bbox_match = True
            source_bbox_valid = True
            source_text_present = True
            width = float(page.get("page_width", 0.0) or 0.0)
            height = float(page.get("page_height", 0.0) or 0.0)
            for reference in references:
                cell_id = str(reference.get("cell_id", ""))
                cell = source_cells.get(cell_id)
                if not cell_id or cell is None:
                    missing_ids = True
                    continue
                resolved.append((reference, cell))
                for field in ("table_id", "row_id", "row_group_id"):
                    if reference.get(field) not in (None, "") and str(reference.get(field)) != str(
                        cell.get(field, "")
                    ):
                        metadata_match = False
                if reference.get("text") not in (None, "") and normalized(reference.get("text")) != normalized(
                    cell.get("text")
                ):
                    metadata_match = False
                if reference.get("bbox") is not None and not bbox_equal(
                    reference.get("bbox"), cell.get("bbox")
                ):
                    recorded_bbox_match = False
                if not bbox_in_page(
                    bbox_values(cell.get("bbox")), width=width, height=height
                ):
                    source_bbox_valid = False
                if not str(cell.get("text", "")).strip():
                    source_text_present = False

            actual_text = "\n--- CELL ---\n".join(
                str(cell.get("text", "")) for _, cell in resolved
            )
            table_ids = {str(cell.get("table_id", "")) for _, cell in resolved}
            row_ids = {str(cell.get("row_id", "")) for _, cell in resolved}
            row_groups = {str(cell.get("row_group_id", "")) for _, cell in resolved}
            aligned = bool(resolved) and len(table_ids) == 1 and (
                len(row_ids) == 1 or (len(row_groups) == 1 and "" not in row_groups)
            )
            units_valid = bool(references) and not missing_ids and len(resolved) == len(references)
            units_valid = units_valid and metadata_match and recorded_bbox_match
            units_valid = units_valid and source_bbox_valid and source_text_present and aligned
            checks["table_units_valid"] = units_valid
            checks["evidence_located"] = units_valid
            checks["endpoints_located_in_evidence"] = (
                locate_surface(actual_text, str(record.get("head_surface", record.get("head", ""))))
                is not None
                and locate_surface(
                    actual_text, str(record.get("tail_surface", record.get("tail", "")))
                )
                is not None
            )
        else:
            checks["table_units_valid"] = None
            evidence_text = str(record.get("evidence_text", "") or "")
            located = locate_surface(page_text, evidence_text) if evidence_text.strip() else None
            checks["evidence_located"] = located is not None
            if located is None:
                checks["endpoints_located_in_evidence"] = False
            else:
                checks["endpoints_located_in_evidence"] = (
                    locate_surface(
                        located.source_text,
                        str(record.get("head_surface", record.get("head", ""))),
                    )
                    is not None
                    and locate_surface(
                        located.source_text,
                        str(record.get("tail_surface", record.get("tail", ""))),
                    )
                    is not None
                )

    locator_contract_pass = all(
        checks[name] is True
        for name in (
            "page_resolved",
            "provenance_fields_complete",
            "hash_fields_well_formed",
            "source_url_well_formed",
            "relation_schema_valid",
            "page_payload_hash_valid",
            "source_metadata_match",
            "evidence_located",
            "endpoints_located_in_evidence",
        )
    ) and level in {"E1", "E2"}
    if level == "E2":
        locator_contract_pass = locator_contract_pass and checks["table_units_valid"] is True

    failed_checks = [name for name, value in checks.items() if value is False]
    return {
        "triple_id": record.get("triple_id"),
        "claim_id": record.get("claim_id"),
        "doc_id": doc_id,
        "pdf_page_number": page_number,
        "decision_group": decision_group(record),
        "legacy_decision": record.get("decision"),
        "evidence_level": level or None,
        "checks": checks,
        "locator_contract_pass": locator_contract_pass,
        "failed_checks": failed_checks,
    }


def aggregate_audits(audits: Sequence[Mapping[str, object]]) -> dict[str, object]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for audit in audits:
        grouped[str(audit.get("decision_group", "unknown"))].append(audit)

    def summarize(items: Sequence[Mapping[str, object]]) -> dict[str, object]:
        check_names = sorted(
            {
                name
                for item in items
                for name in (item.get("checks") or {}).keys()
            }
        )
        checks: dict[str, dict[str, object]] = {}
        for name in check_names:
            applicable = [
                (item.get("checks") or {}).get(name)
                for item in items
                if (item.get("checks") or {}).get(name) is not None
            ]
            passed = sum(value is True for value in applicable)
            checks[name] = {
                "applicable": len(applicable),
                "passed": passed,
                "failed": len(applicable) - passed,
                "pass_rate": round(passed / len(applicable), 6) if applicable else None,
            }
        contract_passed = sum(item.get("locator_contract_pass") is True for item in items)
        return {
            "records": len(items),
            "locator_contract_passed": contract_passed,
            "locator_contract_pass_rate": round(contract_passed / len(items), 6)
            if items
            else None,
            "checks": checks,
        }

    return {
        "overall": summarize(audits),
        "by_decision_group": {
            group: summarize(items) for group, items in sorted(grouped.items())
        },
    }


def mutate_record(record: Mapping[str, object], mutation: str) -> dict[str, object]:
    mutated = json.loads(json.dumps(record, ensure_ascii=False))
    if mutation == "evidence_payload_removed":
        mutated["evidence_text"] = ""
        mutated["evidence_units"] = []
        mutated["evidence_unit_ids"] = []
    elif mutation == "endpoint_evidence_truncated":
        mutated["evidence_text"] = str(mutated.get("head_surface", mutated.get("head", "")))
    elif mutation == "page_locator_shifted":
        mutated["pdf_page_number"] = int(mutated.get("pdf_page_number", 0) or 0) + 1
    elif mutation == "document_hash_corrupted":
        current = str(mutated.get("document_sha256", ""))
        mutated["document_sha256"] = ("0" if not current.startswith("0") else "1") + current[1:]
    elif mutation == "page_hash_corrupted":
        current = str(mutated.get("page_text_sha256", ""))
        mutated["page_text_sha256"] = ("0" if not current.startswith("0") else "1") + current[1:]
    elif mutation == "source_url_removed":
        mutated["source_url"] = ""
    elif mutation == "source_family_removed":
        mutated["source_family_id"] = ""
    elif mutation == "relation_tail_type_corrupted":
        mutated["tail_type"] = "__INVALID_ENTITY_TYPE__"
    elif mutation == "table_cell_id_corrupted":
        units = mutated.get("evidence_units") or []
        ids = mutated.get("evidence_unit_ids") or []
        if units:
            units[0]["cell_id"] = str(units[0].get("cell_id", "")) + ":CORRUPTED"
        if ids:
            ids[0] = str(ids[0]) + ":CORRUPTED"
    elif mutation == "table_bbox_out_of_bounds":
        units = mutated.get("evidence_units") or []
        if units:
            units[0]["bbox"] = [-10.0, -10.0, -1.0, -1.0]
    else:
        raise ValueError(f"Unknown mutation: {mutation}")
    return mutated


def mutation_types(record: Mapping[str, object]) -> list[str]:
    common = [
        "evidence_payload_removed",
        "page_locator_shifted",
        "document_hash_corrupted",
        "page_hash_corrupted",
        "source_url_removed",
        "source_family_removed",
        "relation_tail_type_corrupted",
    ]
    level = str(record.get("evidence_level", "") or "")
    if level == "E1":
        head = str(record.get("head_surface", record.get("head", "")))
        tail = str(record.get("tail_surface", record.get("tail", "")))
        # Truncating the evidence to the head is a valid injected violation
        # only when the tail is not already lexically contained in the head.
        # Otherwise both endpoints legitimately remain locatable.
        if head.strip() and tail.strip() and locate_surface(head, tail) is None:
            common.append("endpoint_evidence_truncated")
    if level == "E2" and table_unit_references(record):
        common.extend(["table_cell_id_corrupted", "table_bbox_out_of_bounds"])
    return common


def run_fault_injection(
    records: Sequence[Mapping[str, object]],
    audits: Sequence[Mapping[str, object]],
    pages: Mapping[tuple[str, int], Mapping[str, object]],
    *,
    schema: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    audit_by_id = {str(item.get("triple_id")): item for item in audits}
    baseline = [
        record
        for record in records
        if decision_group(record) == "evidence_qualified"
        and (audit_by_id.get(str(record.get("triple_id"))) or {}).get(
            "locator_contract_pass"
        )
        is True
    ]
    qualified_total = sum(decision_group(record) == "evidence_qualified" for record in records)
    results: list[dict[str, object]] = []
    for record in baseline:
        for mutation in mutation_types(record):
            mutated = mutate_record(record, mutation)
            audit = audit_record(mutated, pages, schema=schema)
            results.append(
                {
                    "source_triple_id": record.get("triple_id"),
                    "doc_id": record.get("doc_id"),
                    "pdf_page_number": record.get("pdf_page_number"),
                    "evidence_level": record.get("evidence_level"),
                    "mutation_type": mutation,
                    "detected": audit["locator_contract_pass"] is False,
                    "failed_checks": audit["failed_checks"],
                }
            )
    by_type: dict[str, dict[str, object]] = {}
    for mutation in sorted({str(item["mutation_type"]) for item in results}):
        items = [item for item in results if item["mutation_type"] == mutation]
        detected = sum(item["detected"] is True for item in items)
        by_type[mutation] = {
            "injected": len(items),
            "detected": detected,
            "missed": len(items) - detected,
            "detection_rate": round(detected / len(items), 6) if items else None,
        }
    detected_total = sum(item["detected"] is True for item in results)
    summary = {
        "qualified_records": qualified_total,
        "clean_qualified_records_passing_locator_contract": len(baseline),
        "clean_qualified_records_excluded": qualified_total - len(baseline),
        "injected_cases": len(results),
        "detected_cases": detected_total,
        "missed_cases": len(results) - detected_total,
        "overall_detection_rate": round(detected_total / len(results), 6)
        if results
        else None,
        "by_mutation_type": by_type,
    }
    return results, summary


def write_audit_csv(path: Path, summary: Mapping[str, object]) -> None:
    rows: list[dict[str, object]] = []
    for group, values in (summary.get("by_decision_group") or {}).items():
        row: dict[str, object] = {
            "decision_group": group,
            "records": values["records"],
            "locator_contract_passed": values["locator_contract_passed"],
            "locator_contract_pass_rate": values["locator_contract_pass_rate"],
        }
        for name, metric in values["checks"].items():
            row[f"{name}_applicable"] = metric["applicable"]
            row[f"{name}_passed"] = metric["passed"]
            row[f"{name}_pass_rate"] = metric["pass_rate"]
        rows.append(row)
    fieldnames = sorted({key for row in rows for key in row})
    preferred = [
        "decision_group",
        "records",
        "locator_contract_passed",
        "locator_contract_pass_rate",
    ]
    fieldnames = preferred + [name for name in fieldnames if name not in preferred]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_mutation_csv(path: Path, summary: Mapping[str, object]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("mutation_type", "injected", "detected", "missed", "detection_rate"),
        )
        writer.writeheader()
        for mutation, values in (summary.get("by_mutation_type") or {}).items():
            writer.writerow({"mutation_type": mutation, **values})


def percentage(value: object) -> str:
    return "N/A" if value is None else f"{100 * float(value):.2f}%"


def write_report(
    path: Path,
    *,
    audit_summary: Mapping[str, object],
    mutation_summary: Mapping[str, object],
) -> None:
    lines = [
        "# RP1 evidence-contract validation experiments",
        "",
        "This report evaluates executable evidence-contract behaviour only. It does not measure domain truth, factual accuracy, or expert agreement. No model API or human expert review was used.",
        "",
        "## Experiment A: all-candidate locator and provenance audit",
        "",
        "| Decision group | Records | Page resolved | Source metadata match | Evidence located | Endpoints located | Locator contract pass |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for group, values in (audit_summary.get("by_decision_group") or {}).items():
        checks = values["checks"]
        lines.append(
            "| {group} | {records} | {page} | {source} | {evidence} | {endpoints} | {contract} |".format(
                group=group,
                records=values["records"],
                page=percentage(checks["page_resolved"]["pass_rate"]),
                source=percentage(checks["source_metadata_match"]["pass_rate"]),
                evidence=percentage(checks["evidence_located"]["pass_rate"]),
                endpoints=percentage(checks["endpoints_located_in_evidence"]["pass_rate"]),
                contract=percentage(values["locator_contract_pass_rate"]),
            )
        )
    lines.extend(
        [
            "",
            "`locator_contract_pass` requires a current physical-page object, complete and matching provenance, valid page-text hash, locatable evidence, and both endpoints within that evidence. E2 records additionally require resolvable parser cell identifiers, aligned rows/row groups, and in-page bounding boxes.",
            "",
            "## Experiment B: controlled contract fault injection",
            "",
            "| Mutation type | Injected | Detected | Missed | Detection rate |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for mutation, values in (mutation_summary.get("by_mutation_type") or {}).items():
        lines.append(
            f"| {mutation} | {values['injected']} | {values['detected']} | {values['missed']} | {percentage(values['detection_rate'])} |"
        )
    lines.extend(
        [
            "",
            f"Overall, {mutation_summary['detected_cases']}/{mutation_summary['injected_cases']} injected violations were detected ({percentage(mutation_summary['overall_detection_rate'])}).",
            "",
            "## Interpretation boundary",
            "",
            "A detected mutation means that a deliberately broken structural, locator, or provenance requirement failed the executable contract. It does not show that the underlying engineering assertion is objectively true. Semantic errors outside the declared contract, including subtle negation, modality, or applicability-scope changes, are not covered by this experiment.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-file",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_evidence_repaired/"
            "candidate_triples.evidence_repaired.jsonl"
        ),
    )
    parser.add_argument("--page-dir", default="data/interim/parsed_pages/corpus_v2")
    parser.add_argument(
        "--schema",
        default="data/kg/marine_pump/schema/provenance_schema_v3.json",
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "results/experiments/research_point_1/"
            "evidence_contract_validation_v1"
        ),
    )
    args = parser.parse_args()

    candidate_path = PROJECT_ROOT / args.candidate_file
    page_dir = PROJECT_ROOT / args.page_dir
    schema_path = PROJECT_ROOT / args.schema
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    records = read_jsonl(candidate_path)
    candidate_documents = sorted({str(record.get("doc_id", "")) for record in records})
    candidate_pages = {
        (str(record.get("doc_id", "")), int(record.get("pdf_page_number", 0) or 0))
        for record in records
    }
    pages, duplicate_page_keys, page_paths = load_pages(page_dir)
    schema = load_provenance_schema(schema_path)
    audits = [audit_record(record, pages, schema=schema) for record in records]
    audit_summary = aggregate_audits(audits)
    audit_summary.update(
        {
            "experiment_version": EXPERIMENT_VERSION,
            "input_records": len(records),
            "candidate_documents": len(candidate_documents),
            "candidate_document_ids": candidate_documents,
            "candidate_referenced_physical_pages": len(candidate_pages),
            "parsed_pages": len(pages),
            "duplicate_page_keys": duplicate_page_keys,
            "human_expert_reviewed": False,
            "model_api_called": False,
            "epistemic_scope": "evidence_contract_behaviour_not_factual_accuracy",
        }
    )

    mutation_records, mutation_summary = run_fault_injection(
        records, audits, pages, schema=schema
    )
    mutation_summary.update(
        {
            "experiment_version": EXPERIMENT_VERSION,
            "human_expert_reviewed": False,
            "model_api_called": False,
            "epistemic_scope": "controlled_contract_violation_detection",
        }
    )

    write_jsonl(output_dir / "all_candidate_audit_records.jsonl", audits)
    write_json(output_dir / "all_candidate_audit_summary.json", audit_summary)
    write_audit_csv(output_dir / "all_candidate_audit_by_decision.csv", audit_summary)
    write_jsonl(output_dir / "fault_injection_records.jsonl", mutation_records)
    write_json(output_dir / "fault_injection_summary.json", mutation_summary)
    write_mutation_csv(output_dir / "fault_injection_summary.csv", mutation_summary)
    write_report(
        output_dir / "experiment_report.md",
        audit_summary=audit_summary,
        mutation_summary=mutation_summary,
    )
    manifest = {
        "experiment_version": EXPERIMENT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_file": candidate_path.relative_to(PROJECT_ROOT).as_posix(),
        "candidate_file_sha256": sha256_file(candidate_path),
        "page_directory": page_dir.relative_to(PROJECT_ROOT).as_posix(),
        "schema_file": schema_path.relative_to(PROJECT_ROOT).as_posix(),
        "schema_file_sha256": sha256_file(schema_path),
        "page_files": len(page_paths),
        "page_file_sha256": {
            path.relative_to(PROJECT_ROOT).as_posix(): sha256_file(path)
            for path in page_paths
        },
        "records": len(records),
        "candidate_documents": len(candidate_documents),
        "candidate_document_ids": candidate_documents,
        "candidate_referenced_physical_pages": len(candidate_pages),
        "parsed_pages": len(pages),
        "human_expert_reviewed": False,
        "model_api_called": False,
    }
    write_json(output_dir / "run_manifest.json", manifest)

    print(
        json.dumps(
            {
                "records": len(records),
                "qualified_locator_pass": audit_summary["by_decision_group"][
                    "evidence_qualified"
                ]["locator_contract_passed"],
                "qualified_records": audit_summary["by_decision_group"][
                    "evidence_qualified"
                ]["records"],
                "injected": mutation_summary["injected_cases"],
                "detected": mutation_summary["detected_cases"],
                "detection_rate": mutation_summary["overall_detection_rate"],
                "output_dir": output_dir.relative_to(PROJECT_ROOT).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
