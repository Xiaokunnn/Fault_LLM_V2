#!/usr/bin/env python3
"""Evaluate graph expansion baselines and RP2 module ablations on development Silver queries."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import matplotlib.pyplot as plt  # noqa: E402

from research_point_2.dataset import EvidenceCandidate, SilverQuery, _read_jsonl  # noqa: E402
from research_point_2.evaluation import evaluate_results  # noqa: E402
from research_point_2.retrieval import RetrievalBudget, RetrievalIndex, retrieve  # noqa: E402


def _candidate(row: dict) -> EvidenceCandidate:
    payload = dict(row)
    payload["fault_class_ids"] = tuple(payload.get("fault_class_ids", []))
    return EvidenceCandidate(**payload)


def _query(row: dict) -> SilverQuery:
    payload = dict(row)
    payload["relevant_evidence_ids"] = tuple(payload.get("relevant_evidence_ids", []))
    payload["candidate_evidence_ids"] = tuple(payload.get("candidate_evidence_ids", []))
    return SilverQuery(**payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-dir", default="data/kg/marine_pump/silver_evidencebench/rp2_development_v1")
    parser.add_argument("--output-dir", default="results/experiments/research_point_2/graph_ablation_v1")
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--max-scored", type=int, default=32)
    args = parser.parse_args()

    benchmark = ROOT / args.benchmark_dir
    candidates = [_candidate(row) for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")]
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    index = RetrievalIndex(candidates)
    budget = RetrievalBudget(
        max_scored_candidates=args.max_scored,
        max_selected_evidence=args.k,
        max_per_source_family=2,
    )
    methods = (
        "fixed_hop", "adaptive_prune", "metapath_topk", "ours",
        "ours_no_index", "ours_no_role_gate", "ours_no_source_family",
        "ours_no_redundancy",
    )
    all_results = []
    for position, method in enumerate(methods, start=1):
        print(f"[RP2 ablation][{position}/{len(methods)}] {method}", flush=True)
        for repeat in range(args.repeats):
            all_results.extend(
                retrieve(query, index, method=method, budget=budget) for query in queries
            )
            if repeat == 0 or repeat + 1 == args.repeats or (repeat + 1) % 10 == 0:
                print(f"  repeat={repeat + 1}/{args.repeats}", flush=True)

    report = evaluate_results(queries, candidates, all_results)
    report["run_config"] = {
        "k": args.k,
        "max_scored_candidates": args.max_scored,
        "max_per_source_family": 2,
        "repeats": args.repeats,
        "fixed_hop_depth": 2,
        "adaptive_prune_rule": "tau=max(mean+0.5*std,p70)",
    }
    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [{"method": method, **metrics} for method, metrics in report["methods"].items()]
    with (output / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.4))
    labels = [row["method"].replace("ours_", "-") for row in rows]
    colors = ["#0f766e" if row["method"] == "ours" else "#64748b" for row in rows]
    axes[0].barh(labels, [row["recall_at_budget_macro"] for row in rows], color=colors)
    axes[0].set_xlabel("Silver Recall@4")
    axes[0].set_title("Quality and module ablation")
    axes[0].grid(axis="x", alpha=0.2)
    axes[1].scatter(
        [row["latency_ms_p95"] for row in rows],
        [row["mean_source_family_coverage"] for row in rows],
        c=colors,
        s=65,
    )
    for row, label in zip(rows, labels):
        axes[1].annotate(label, (row["latency_ms_p95"], row["mean_source_family_coverage"]), fontsize=8)
    axes[1].set_xlabel("Online latency p95 (ms)")
    axes[1].set_ylabel("Mean source-family coverage")
    axes[1].set_title("Latency-diversity trade-off")
    axes[1].grid(alpha=0.2)
    figure.suptitle("RP2 graph baselines and ablation (development only)")
    figure.tight_layout()
    figure.savefig(output / "graph_ablation.png", dpi=200, bbox_inches="tight")
    figure.savefig(output / "graph_ablation.svg", bbox_inches="tight")
    plt.close(figure)
    print(f"[RP2 ablation] outputs={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
