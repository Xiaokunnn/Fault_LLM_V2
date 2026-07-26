"""Strictly validate the targeted qwen3.7-max candidates with progress output."""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Mapping


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
    normalize_relation_direction,
    validate_candidate,
)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def _load_pages(
    input_dir: Path,
    needed: set[tuple[str, int]] | None = None,
) -> dict[tuple[str, int], dict[str, object]]:
    pages: dict[tuple[str, int], dict[str, object]] = {}
    for path in input_dir.glob("*.pages.v2.jsonl"):
        for page in _read_jsonl(path):
            key = (str(page["doc_id"]), int(page["pdf_page_number"]))
            if needed is None or key in needed:
                pages[key] = page
    return pages


def _bbox_list(value: object) -> list[float] | None:
    if not isinstance(value, Mapping):
        return None
    keys = ("x0", "top", "x1", "bottom")
    if any(value.get(key) is None for key in keys):
        return None
    return [float(value[key]) for key in keys]


def _cell_lookup(page: Mapping[str, object]) -> dict[str, dict[str, object]]:
    lookup: dict[str, dict[str, object]] = {}
    for table in page.get("tables", []) or []:
        if not isinstance(table, Mapping):
            continue
        for row in table.get("rows", []) or []:
            if not isinstance(row, Mapping):
                continue
            for cell in row.get("cells", []) or []:
                if not isinstance(cell, Mapping):
                    continue
                cell_id = str(cell.get("cell_id", ""))
                if not cell_id:
                    continue
                lookup[cell_id] = {
                    "cell_id": cell_id,
                    "table_id": str(cell.get("table_id", "")),
                    "row_id": str(cell.get("row_id", "")),
                    "row_group_id": cell.get("row_group_id"),
                    "column_name": str(cell.get("column_name", "")),
                    "role": cell.get("column_role"),
                    "text": str(
                        cell.get("page_text_source")
                        if cell.get("page_text_start") is not None
                        and cell.get("page_text_end") is not None
                        and cell.get("page_text_source") is not None
                        else cell.get("text", "")
                    ),
                    "start": (
                        int(cell["page_text_start"])
                        if cell.get("page_text_start") is not None
                        else -1
                    ),
                    "end": (
                        int(cell["page_text_end"])
                        if cell.get("page_text_end") is not None
                        else -1
                    ),
                    "bbox": _bbox_list(cell.get("bbox")),
                }
    return lookup


def _structured_relation(
    candidate: Mapping[str, object],
    units: list[Mapping[str, object]],
) -> str | None:
    """Confirm only relations directly encoded by recognized table columns."""

    def normalized(value: object) -> str:
        return " ".join(
            unicodedata.normalize("NFKC", str(value)).casefold().split()
        )

    direction = normalize_relation_direction(
        head=str(candidate.get("head_surface") or candidate.get("head") or ""),
        head_type=str(candidate.get("head_type", "")),
        relation=str(candidate.get("relation", "")),
        tail=str(candidate.get("tail_surface") or candidate.get("tail") or ""),
        tail_type=str(candidate.get("tail_type", "")),
    )
    relation = direction.relation
    head = normalized(direction.head)
    tail = normalized(direction.tail)
    head_roles = {
        str(unit.get("role"))
        for unit in units
        if head and head in normalized(unit.get("text", ""))
    }
    tail_roles = {
        str(unit.get("role"))
        for unit in units
        if tail and tail in normalized(unit.get("text", ""))
    }
    if (
        relation == "causes"
        and "cause_or_mechanism" in head_roles
        and "fault_or_symptom" in tail_roles
    ):
        return relation
    if (
        relation in {"inspected_by", "mitigated_by", "maintained_by"}
        and "fault_or_symptom" in head_roles
        and "inspection_or_maintenance" in tail_roles
    ):
        return relation
    if (
        relation == "prevented_by"
        and "fault_or_symptom" in head_roles
        and "inspection_or_maintenance" in tail_roles
    ):
        prevention_text = " ".join(
            normalized(unit.get("column_name", ""))
            + " "
            + normalized(unit.get("text", ""))
            for unit in units
        )
        prevention_cues = (
            "prevent",
            "avoid",
            "must not",
            "should not",
            "never",
            "防止",
            "预防",
            "避免",
            "不得",
            "禁止",
        )
        if any(cue in prevention_text for cue in prevention_cues):
            return relation
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="configs/triple_extraction_qwen3_7_max_targeted_zh_v1.json",
    )
    parser.add_argument("--candidate-dir")
    parser.add_argument("--input-dir")
    parser.add_argument("--output-dir")
    parser.add_argument(
        "--schema",
        help="Explicit provenance schema; gap repair uses versioned schema v3.",
    )
    args = parser.parse_args()
    config = json.loads(
        (PROJECT_ROOT / args.config).read_text(encoding="utf-8")
    )
    candidate_dir = PROJECT_ROOT / str(
        args.candidate_dir or config["output_dir"]
    )
    candidate_path = candidate_dir / "candidate_triples.raw_zh.jsonl"
    if not candidate_path.exists():
        raise FileNotFoundError(
            f"Targeted candidate file not found: {candidate_path}. "
            "Run scripts/run_targeted_triple_extraction.py first."
        )
    output_dir = PROJECT_ROOT / str(
        args.output_dir
        or "data/interim/candidate_triples/"
        "qwen3_7_max_targeted_zh_v1_strict_v2"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = _read_jsonl(candidate_path)
    needed_pages = {
        (str(candidate["doc_id"]), int(candidate["pdf_page_number"]))
        for candidate in candidates
    }
    pages = _load_pages(
        PROJECT_ROOT / str(args.input_dir or config["input_page_dir"]),
        needed_pages,
    )
    schema = load_provenance_schema(
        PROJECT_ROOT / args.schema if args.schema else None,
        project_root=PROJECT_ROOT,
    )
    terminology = load_chinese_terminology(
        (
            PROJECT_ROOT / str(config["terminology_path"])
            if config.get("terminology_path")
            else None
        ),
        project_root=PROJECT_ROOT,
    )
    ontology = load_fault_ontology(project_root=PROJECT_ROOT)
    validated: list[dict[str, object]] = []
    started = time.perf_counter()
    print(f"[Stage 3] 开始严格校验：候选={len(candidates)}", flush=True)

    for index, candidate in enumerate(candidates, start=1):
        key = (
            str(candidate["doc_id"]),
            int(candidate["pdf_page_number"]),
        )
        if key not in pages:
            raise KeyError(f"Parsed page not found: {key[0]}:{key[1]}")
        page = pages[key]
        units = None
        structured_relation = None
        if candidate.get("evidence_mode") == "E2_table_cells":
            lookup = _cell_lookup(page)
            requested_ids = [
                str(value) for value in candidate.get("evidence_unit_ids", []) or []
            ]
            missing_ids = [value for value in requested_ids if value not in lookup]
            if missing_ids:
                candidate = dict(candidate)
                candidate["evidence_unit_resolution_errors"] = missing_ids
            else:
                units = [lookup[value] for value in requested_ids]
                structured_relation = _structured_relation(candidate, units)
        result = validate_candidate(
            candidate,
            page_text=str(page.get("page_text", "")),
            project_root=PROJECT_ROOT,
            schema=schema,
            ontology=ontology,
            terminology=terminology,
            table_evidence_units=units,
            structured_relation=structured_relation,
            visual_layout_checked=bool(page.get("visual_layout_checked", False)),
        )
        validated.append(result)
        if index == 1 or index % 10 == 0 or index == len(candidates):
            elapsed = time.perf_counter() - started
            counts = Counter(str(item["decision"]) for item in validated)
            print(
                f"[Stage 3][{index}/{len(candidates)}] "
                f"Silver={counts.get('silver_candidate', 0)}，"
                f"复核={counts.get('candidate_needs_review', 0)}，"
                f"拒绝={counts.get('rejected', 0)}，耗时={elapsed:.1f}s",
                flush=True,
            )

    deduplicated = deduplicate_triples(validated)
    strict_path = output_dir / "candidate_triples.strict_v2.jsonl"
    with strict_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in deduplicated.records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    fault_ids = [str(item["fault_id"]) for item in ontology["fault_classes"]]
    coverage = build_coverage_report(
        deduplicated.records,
        fault_ids=fault_ids,
        thresholds=CoverageThresholds.from_ontology(ontology),
        require_chinese_graph_ready=True,
    )
    evidence_only_coverage = build_coverage_report(
        deduplicated.records,
        fault_ids=fault_ids,
        thresholds=CoverageThresholds.from_ontology(ontology),
        require_chinese_graph_ready=False,
    )
    (output_dir / "strict_v2_coverage_report.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (
        output_dir / "strict_v2_coverage_evidence_only_audit.json"
    ).write_text(
        json.dumps(evidence_only_coverage, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    decisions = Counter(str(item["decision"]) for item in deduplicated.records)
    summary = {
        "version": "qwen3_7_max_targeted_zh_v1_strict_v2",
        "input_candidates": len(candidates),
        "output_candidates": len(deduplicated.records),
        "duplicates_removed": deduplicated.duplicates_removed,
        "decisions": dict(decisions),
        "chinese_graph_ready_silver_records": sum(
            item.get("decision") == "silver_candidate"
            and item.get("eligible_for_chinese_graph") is True
            for item in deduplicated.records
        ),
        "fault_classes_passing_gate": coverage["fault_classes_passing_gate"],
        "fault_classes_passing_evidence_only_audit": evidence_only_coverage[
            "fault_classes_passing_gate"
        ],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    (output_dir / "strict_v2_validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Stage 3] 完成：输出={len(deduplicated.records)}，"
        f"Silver={decisions.get('silver_candidate', 0)}，"
        f"中文图谱就绪={summary['chinese_graph_ready_silver_records']}，"
        f"证据过门类别={summary['fault_classes_passing_evidence_only_audit']}/10，"
        f"中文发布过门类别={summary['fault_classes_passing_gate']}/10，"
        f"总耗时={summary['elapsed_seconds']}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
