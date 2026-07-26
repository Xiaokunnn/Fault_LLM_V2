"""Strict-v2 replay of the frozen four-page pilot candidates."""

from __future__ import annotations

import json
import sys
import csv
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    deduplicate_triples,
    build_coverage_report,
    CoverageThresholds,
    load_fault_ontology,
    load_provenance_schema,
    validate_candidate,
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def page_lookup() -> dict[tuple[str, int], str]:
    lookup: dict[tuple[str, int], str] = {}
    source_dir = (
        PROJECT_ROOT / "data/interim/parsed_pages/representative_pilot_v1"
    )
    for path in source_dir.glob("*.pages.jsonl"):
        for page in read_jsonl(path):
            lookup[(str(page["doc_id"]), int(page["pdf_page_number"]))] = str(
                page.get("page_text") or page.get("text") or ""
            )
    return lookup


def manifest_metadata() -> dict[str, dict[str, str]]:
    path = PROJECT_ROOT / "data/source_docs/marine_pump/source_manifest.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = {row["doc_id"]: row for row in rows}
    missing = [
        doc_id
        for doc_id, row in result.items()
        if not (row.get("source_family_id") or "").strip()
    ]
    if missing:
        raise ValueError(
            "Formal strict replay requires source_family_id in the manifest: "
            + ", ".join(missing)
        )
    return result


def main() -> None:
    candidate_path = (
        PROJECT_ROOT
        / "data/interim/candidate_triples/qwen3_7_max_triple_pilot_v1"
        / "candidate_triples.jsonl"
    )
    output_dir = (
        PROJECT_ROOT
        / "data/interim/candidate_triples/qwen3_7_max_triple_pilot_strict_v2"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = page_lookup()
    metadata = manifest_metadata()
    schema = load_provenance_schema(project_root=PROJECT_ROOT)
    ontology = load_fault_ontology(project_root=PROJECT_ROOT)
    validated: list[dict[str, object]] = []
    for candidate in read_jsonl(candidate_path):
        candidate = dict(candidate)
        candidate["source_family_id"] = metadata[str(candidate["doc_id"])][
            "source_family_id"
        ]
        key = (str(candidate["doc_id"]), int(candidate["pdf_page_number"]))
        if key not in pages:
            raise KeyError(f"Parsed page not found: {key}")
        validated.append(
            validate_candidate(
                candidate,
                page_text=pages[key],
                project_root=PROJECT_ROOT,
                schema=schema,
                ontology=ontology,
            )
        )
    deduplicated = deduplicate_triples(validated)
    output_path = output_dir / "candidate_triples.strict_v2.jsonl"
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in deduplicated.records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    decisions = Counter(
        str(record.get("decision")) for record in deduplicated.records
    )
    evidence_levels = Counter(
        str(record.get("evidence_level")) for record in deduplicated.records
    )
    # Recover the old state from source records for an explicit transition audit.
    source_candidates = read_jsonl(candidate_path)
    transitions = Counter(
        (
            str(source.get("validation_status")),
            str(target.get("decision")),
        )
        for source, target in zip(source_candidates, validated)
    )
    reason_counts = Counter(
        reason
        for record in deduplicated.records
        for reason in (
            list(record.get("review_reasons", []))
            + list(record.get("rejection_reasons", []))
        )
    )
    summary = {
        "version": "qwen3_7_max_triple_pilot_strict_v2_revalidation",
        "input_candidates": len(validated),
        "output_candidates": len(deduplicated.records),
        "duplicates_removed": deduplicated.duplicates_removed,
        "decisions": dict(decisions),
        "evidence_levels": dict(evidence_levels),
        "legacy_to_strict_transitions": {
            f"{old}->{new}": count for (old, new), count in transitions.items()
        },
        "reason_counts": dict(reason_counts),
        "interpretation": (
            "Strict-v2 local replay only. No external model was called. E2 table "
            "promotion requires parser-generated units and visual verification, so "
            "legacy candidates without those units remain E1/E3/review/rejected. "
            "Chinese graph readiness is evaluated separately after source-language "
            "evidence validation."
        ),
        "chinese_graph_ready_silver_records": sum(
            record.get("decision") == "silver_candidate"
            and record.get("eligible_for_chinese_graph") is True
            for record in deduplicated.records
        ),
        "graph_display_language": "zh-CN",
    }
    fault_ids = [str(item["fault_id"]) for item in ontology["fault_classes"]]
    coverage = build_coverage_report(
        deduplicated.records,
        fault_ids=fault_ids,
        thresholds=CoverageThresholds.from_ontology(ontology),
        require_chinese_graph_ready=True,
    )
    (output_dir / "strict_v2_coverage_report.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary["strict_build_silver_records"] = coverage[
        "eligible_build_silver_records"
    ]
    summary["fault_classes_passing_gate"] = coverage[
        "fault_classes_passing_gate"
    ]
    (output_dir / "strict_v2_revalidation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
