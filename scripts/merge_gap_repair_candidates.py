"""Merge source-v3 Silver governance records with newly validated gap repairs."""

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
    deduplicate_triples,
)


DEFAULT_BASE = (
    "data/interim/candidate_triples/"
    "qwen3_7_max_corpus_retrieval_v3_source_supplement_"
    "strict_v4_auto_adjudicated/"
    "candidate_triples.auto_adjudicated_silver.jsonl"
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--gap-strict-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    base_path = PROJECT_ROOT / args.base
    gap_path = (
        PROJECT_ROOT / args.gap_strict_dir / "candidate_triples.strict_v2.jsonl"
    )
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    base = read_jsonl(base_path)
    gap = read_jsonl(gap_path)
    combined = deduplicate_triples([*base, *gap])
    output_path = output_dir / "candidate_triples.strict_v2.jsonl"
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in combined.records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    decisions = Counter(str(record.get("decision")) for record in combined.records)
    summary = {
        "version": "marine_pump_gap_repair_merge_v1",
        "base_records": len(base),
        "gap_records": len(gap),
        "merged_records": len(combined.records),
        "duplicates_removed": combined.duplicates_removed,
        "decisions_before_gap_adjudication": dict(decisions),
        "base_source": base_path.relative_to(PROJECT_ROOT).as_posix(),
        "gap_source": gap_path.relative_to(PROJECT_ROOT).as_posix(),
        "label_policy": "Silver only; never Gold",
    }
    (output_dir / "gap_merge_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Gap Merge] 完成：base={len(base)}，gap={len(gap)}，"
        f"merged={len(combined.records)}，去重={combined.duplicates_removed}",
        flush=True,
    )


if __name__ == "__main__":
    main()
