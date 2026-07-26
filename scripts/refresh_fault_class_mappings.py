"""Refresh fault-class mappings without changing evidence or Silver decisions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    load_fault_ontology,
    map_fault_classes,
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    input_path = (
        PROJECT_ROOT / args.input_dir / "candidate_triples.strict_v2.jsonl"
    )
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    ontology = load_fault_ontology(project_root=PROJECT_ROOT)
    records = read_jsonl(input_path)
    changed = 0
    class_counts: Counter[str] = Counter()
    for record in records:
        old_ids = tuple(record.get("fault_class_ids", []) or [])
        evidence_valid = bool(
            (record.get("evidence_validation", {}) or {}).get("valid")
        )
        mapping = map_fault_classes(
            head_surface=str(record.get("head", "")),
            tail_surface=str(record.get("tail", "")),
            evidence_text=(
                str(record.get("evidence_text", "")) if evidence_valid else ""
            ),
            ontology=ontology,
            requested_fault_class_ids=old_ids,
        )
        new_ids = tuple(mapping.fault_class_ids)
        if old_ids != new_ids:
            changed += 1
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
            "version": "marine_pump_mapping_refresh_v1",
            "old_fault_class_ids": list(old_ids),
            "new_fault_class_ids": list(new_ids),
            "evidence_and_decision_unchanged": True,
        }
        class_counts.update(new_ids)
    output_path = output_dir / "candidate_triples.strict_v2.jsonl"
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = {
        "version": "marine_pump_mapping_refresh_v1",
        "mapping_version": ontology["version"],
        "input_records": len(records),
        "records_with_changed_fault_classes": changed,
        "fault_class_record_counts": dict(sorted(class_counts.items())),
        "evidence_changed": False,
        "decision_changed": False,
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    (output_dir / "mapping_refresh_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Mapping Refresh] 完成：记录={len(records)}，"
        f"类别映射变化={changed}，版本={ontology['version']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
