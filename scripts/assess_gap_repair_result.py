"""Decide whether gap repair permits full extraction or triggers dry-run sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DRY_CLASS = "dry_running_or_maintenance_induced_failure"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    coverage_path = PROJECT_ROOT / args.coverage
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    fault_coverage = coverage["fault_coverage"]
    failed = [
        fault_id
        for fault_id, entry in fault_coverage.items()
        if entry.get("gate_passed") is not True
    ]
    dry = fault_coverage[DRY_CLASS]
    dry_checks = dry["gate_checks"]
    dry_source_gap = dry_checks.get("source_families_at_least_2") is not True
    dry_symptom_gap = dry_checks.get("symptom_at_least_5") is not True
    dry_action_gap = (
        dry_checks.get("inspection_or_maintenance_at_least_2") is not True
    )
    supplement_dry_sources = bool(DRY_CLASS in failed and dry_source_gap)
    if not failed:
        corpus_decision = "start_full_extraction"
        next_action = "All 10 evidence-only classes pass the frozen gate."
    elif supplement_dry_sources:
        corpus_decision = "add_1_or_2_dry_running_maintenance_sources"
        next_action = (
            "Add only one or two independent dry-running/maintenance-failure "
            "documents, freeze them as post-gap build sources, and rerun this repair."
        )
    elif DRY_CLASS in failed and (dry_symptom_gap or dry_action_gap):
        corpus_decision = "repair_existing_dry_running_role_extraction"
        next_action = (
            "Independent-source coverage is already sufficient. Audit existing "
            "dry-running pages for symptom/action typing and mapping before adding "
            "another document."
        )
    else:
        corpus_decision = "do_not_start_full_extraction"
        next_action = (
            "Do not add broad documents; unresolved classes still require "
            "role/schema/evidence correction."
        )
    result = {
        "version": "marine_pump_gap_repair_decision_v2",
        "fault_classes_passing": int(coverage["fault_classes_passing_gate"]),
        "failed_fault_classes": failed,
        "corpus_decision": corpus_decision,
        "next_action": next_action,
        "dry_running_gap": {
            "symptom_evidence": dry["symptom_evidence"],
            "inspection_or_maintenance_evidence": dry[
                "inspection_or_maintenance_evidence"
            ],
            "source_families": len(dry["source_families"]),
            "symptom_gap": dry_symptom_gap,
            "inspection_or_maintenance_gap": dry_action_gap,
            "independent_source_gap": dry_source_gap,
            "supplement_1_or_2_documents": supplement_dry_sources,
        },
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Gap Decision] 覆盖={result['fault_classes_passing']}/10，"
        f"结论={corpus_decision}",
        flush=True,
    )
    print(
        "[Gap Decision] 干运转："
        f"症状={dry['symptom_evidence']}，"
        f"检维={dry['inspection_or_maintenance_evidence']}，"
        f"来源家族={len(dry['source_families'])}",
        flush=True,
    )
    print(f"[Gap Decision] 下一步：{next_action}", flush=True)


if __name__ == "__main__":
    main()
