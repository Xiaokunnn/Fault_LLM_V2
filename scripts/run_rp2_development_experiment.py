#!/usr/bin/env python3
"""Run initial RP2 retrieval baselines on the development Silver benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_point_2.dataset import (  # noqa: E402
    EvidenceCandidate,
    SilverQuery,
    _read_jsonl,
)
from research_point_2.evaluation import evaluate_results  # noqa: E402
from research_point_2.retrieval import RetrievalBudget, RetrievalIndex, retrieve  # noqa: E402


def _candidate(row: dict) -> EvidenceCandidate:
    row = dict(row)
    row["fault_class_ids"] = tuple(row.get("fault_class_ids", []))
    return EvidenceCandidate(**row)


def _query(row: dict) -> SilverQuery:
    row = dict(row)
    row["relevant_evidence_ids"] = tuple(row.get("relevant_evidence_ids", []))
    row["candidate_evidence_ids"] = tuple(row.get("candidate_evidence_ids", []))
    return SilverQuery(**row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark-dir",
        default="data/kg/marine_pump/silver_evidencebench/rp2_development_v1",
    )
    parser.add_argument(
        "--output-dir",
        default="results/experiments/research_point_2/development_v1",
    )
    parser.add_argument("--max-scored", type=int, default=64)
    parser.add_argument("--max-selected", type=int, default=8)
    parser.add_argument("--max-per-family", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=30)
    args = parser.parse_args()

    benchmark = ROOT / args.benchmark_dir
    candidates = [_candidate(row) for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")]
    index = RetrievalIndex(candidates)
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    budget = RetrievalBudget(
        max_scored_candidates=args.max_scored,
        max_selected_evidence=args.max_selected,
        max_per_source_family=args.max_per_family,
    )
    results = []
    methods = ("lexical_full_scan", "role_topk", "metapath_topk", "ours")
    for method in methods:
        print(f"[RP2] method={method}", flush=True)
        for repeat in range(args.repeats):
            for query in queries:
                results.append(retrieve(query, index, method=method, budget=budget))
            if repeat in {0, args.repeats - 1} or (repeat + 1) % 10 == 0:
                print(f"[RP2] {method} repeat={repeat + 1}/{args.repeats}", flush=True)

    metrics = evaluate_results(queries, candidates, results)
    metrics["run_config"] = {
        "max_scored_candidates": args.max_scored,
        "max_selected_evidence": args.max_selected,
        "max_per_source_family": args.max_per_family,
        "repeats": args.repeats,
    }
    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "retrieval_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
