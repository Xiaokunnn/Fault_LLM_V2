"""Freeze the evidence-only corpus gate after claim-scoped fault remapping.

This step is local-only: it never calls an external model and never changes
evidence spans, relation decisions, or Silver labels.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    CoverageThresholds,
    build_coverage_report,
    load_fault_ontology,
    map_fault_classes,
)


PIPE_CLASS = "pipe_or_valve_integrity_failure"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=(
            "data/interim/candidate_triples/"
            "final_semantic_gap_v1_auto_adjudicated/"
            "candidate_triples.auto_adjudicated_silver.jsonl"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "data/interim/candidate_triples/"
            "final_semantic_gap_v1_gate_frozen"
        ),
    )
    args = parser.parse_args()

    input_path = PROJECT_ROOT / args.input
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    ontology = load_fault_ontology(project_root=PROJECT_ROOT)
    records = read_jsonl(input_path)

    changed = 0
    pipe_removed = 0
    pipe_added = 0
    for record in records:
        old_ids = tuple(record.get("fault_class_ids", []) or [])
        evidence_valid = bool(
            (record.get("evidence_validation", {}) or {}).get("valid")
        )
        mapping = map_fault_classes(
            head_surface=str(record.get("head", "")),
            tail_surface=str(record.get("tail", "")),
            evidence_text=(
                str(record.get("evidence_text", ""))
                if evidence_valid
                else ""
            ),
            ontology=ontology,
            requested_fault_class_ids=old_ids,
        )
        new_ids = tuple(mapping.fault_class_ids)
        if old_ids != new_ids:
            changed += 1
        if PIPE_CLASS in old_ids and PIPE_CLASS not in new_ids:
            pipe_removed += 1
        if PIPE_CLASS not in old_ids and PIPE_CLASS in new_ids:
            pipe_added += 1
        record["fault_class_ids"] = list(new_ids)
        record["fault_class_mapping_version"] = mapping.mapping_version
        record["fault_class_mapping_rule_ids"] = {
            key: list(value)
            for key, value in mapping.matched_rule_ids.items()
        }
        record["fault_class_mapping_evidence"] = {
            key: list(value)
            for key, value in mapping.mapping_evidence.items()
        }
        record["fault_class_mapping_refresh"] = {
            "version": "marine_pump_mapping_refresh_v2_claim_scoped",
            "old_fault_class_ids": list(old_ids),
            "new_fault_class_ids": list(new_ids),
            "evidence_and_decision_unchanged": True,
        }

    frozen_path = output_dir / "candidate_triples.gate_frozen.jsonl"
    with frozen_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    fault_ids = [
        str(item["fault_id"]) for item in ontology["fault_classes"]
    ]
    thresholds = CoverageThresholds.from_ontology(ontology)
    evidence_coverage = build_coverage_report(
        records,
        fault_ids=fault_ids,
        thresholds=thresholds,
        require_chinese_graph_ready=False,
    )
    chinese_coverage = build_coverage_report(
        records,
        fault_ids=fault_ids,
        thresholds=thresholds,
        require_chinese_graph_ready=True,
    )
    write_json(output_dir / "coverage_evidence_only.json", evidence_coverage)
    write_json(output_dir / "coverage_chinese_release.json", chinese_coverage)

    decisions = Counter(str(record.get("decision", "")) for record in records)
    passed = int(evidence_coverage["fault_classes_passing_gate"])
    summary = {
        "version": "marine_pump_full_extraction_gate_freeze_v1",
        "input_artifact": str(input_path.relative_to(PROJECT_ROOT)),
        "frozen_artifact": str(frozen_path.relative_to(PROJECT_ROOT)),
        "mapping_version": ontology["version"],
        "input_records": len(records),
        "decisions": dict(sorted(decisions.items())),
        "records_with_changed_fault_classes": changed,
        "pipe_false_positive_mappings_removed": pipe_removed,
        "pipe_mappings_added": pipe_added,
        "evidence_changed": False,
        "decision_changed": False,
        "evidence_only_classes_passing": passed,
        "chinese_release_classes_passing": int(
            chinese_coverage["fault_classes_passing_gate"]
        ),
        "corpus_decision": (
            "start_full_extraction"
            if passed == len(fault_ids)
            else "do_not_start_full_extraction"
        ),
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    write_json(output_dir / "gate_freeze_summary.json", summary)

    print(
        f"[Gate Freeze] 记录={len(records)}，Silver="
        f"{decisions.get('silver_candidate', 0)}，映射变化={changed}",
        flush=True,
    )
    print(
        f"[Gate Freeze] 管路误映射移除={pipe_removed}，"
        f"证据门槛={passed}/{len(fault_ids)}",
        flush=True,
    )
    print(
        f"[Gate Freeze] 决策={summary['corpus_decision']}，"
        "无人工专家审核，全部仅称 Silver",
        flush=True,
    )


if __name__ == "__main__":
    main()
