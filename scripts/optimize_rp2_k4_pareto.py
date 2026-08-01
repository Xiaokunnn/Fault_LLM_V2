#!/usr/bin/env python3
"""Tune RP2 K=4 on development data and freeze a constraint-based Pareto choice."""

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


def _evaluate(queries, candidates, index, method, budget, repeats):
    results = [
        retrieve(query, index, method=method, budget=budget)
        for _ in range(repeats)
        for query in queries
    ]
    return evaluate_results(queries, candidates, results)["methods"][method]


def _dominates(left: dict, right: dict) -> bool:
    objectives = (
        ("recall_at_budget_macro", 1),
        ("mean_source_family_coverage", 1),
        ("mean_exact_claim_redundancy", -1),
        ("latency_ms_p95", -1),
    )
    no_worse = all(left[key] * sign >= right[key] * sign for key, sign in objectives)
    better = any(left[key] * sign > right[key] * sign for key, sign in objectives)
    return no_worse and better


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-dir", default="data/kg/marine_pump/silver_evidencebench/rp2_development_v1")
    parser.add_argument("--output-dir", default="results/experiments/research_point_2/k4_pareto_v1")
    parser.add_argument("--repeats", type=int, default=30)
    args = parser.parse_args()
    benchmark = ROOT / args.benchmark_dir
    candidates = [_candidate(row) for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")]
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    index = RetrievalIndex(candidates)

    reference = _evaluate(
        queries, candidates, index, "metapath_topk",
        RetrievalBudget(max_scored_candidates=32, max_selected_evidence=4, max_per_source_family=4),
        args.repeats,
    )
    rows = []
    grid = [(bonus, penalty, cap) for bonus in (0.04, 0.08, 0.12, 0.16, 0.20) for penalty in (0.08, 0.16, 0.24, 0.32) for cap in (1, 2, 3)]
    for position, (bonus, penalty, cap) in enumerate(grid, start=1):
        print(f"[RP2 Pareto][{position}/{len(grid)}] bonus={bonus}, penalty={penalty}, cap={cap}", flush=True)
        metrics = _evaluate(
            queries, candidates, index, "ours",
            RetrievalBudget(
                max_scored_candidates=32,
                max_selected_evidence=4,
                max_per_source_family=cap,
                source_family_bonus=bonus,
                redundancy_penalty=penalty,
            ),
            args.repeats,
        )
        rows.append({"source_family_bonus": bonus, "redundancy_penalty": penalty, "max_per_source_family": cap, **metrics})
    for row in rows:
        row["pareto_optimal"] = not any(_dominates(other, row) for other in rows if other is not row)
        row["quality_constraint_passed"] = row["recall_at_budget_macro"] >= reference["recall_at_budget_macro"] - 0.01
    eligible = [row for row in rows if row["pareto_optimal"] and row["quality_constraint_passed"]]
    if not eligible:
        eligible = [row for row in rows if row["quality_constraint_passed"]]
    selected = max(
        eligible,
        key=lambda row: (
            row["mean_source_family_coverage"],
            -row["mean_exact_claim_redundancy"],
            -row["latency_ms_p95"],
        ),
    )
    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    with (output / "pareto_grid.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "label_policy": "Silver only; never Gold",
        "benchmark_scope": "development_only_not_held_out",
        "selection_rule": "Pareto non-dominated; recall >= metapath_topk@4 - 0.01; then maximize family coverage, minimize exact-claim redundancy, minimize p95 latency",
        "reference_metapath_topk_k4": reference,
        "selected": selected,
        "grid": rows,
    }
    (output / "pareto_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    for row in rows:
        ax.scatter(row["latency_ms_p95"], row["recall_at_budget_macro"], c="#0f766e" if row["pareto_optimal"] else "#cbd5e1", s=28 + 25 * row["mean_source_family_coverage"], alpha=0.85)
    ax.scatter(selected["latency_ms_p95"], selected["recall_at_budget_macro"], c="#dc2626", marker="*", s=220, label="frozen choice")
    ax.axhline(reference["recall_at_budget_macro"] - 0.01, color="#64748b", linestyle="--", label="quality floor")
    ax.set_xlabel("Online latency p95 (ms)")
    ax.set_ylabel("Silver Recall@4")
    ax.set_title("RP2 K=4 quality-diversity-latency Pareto")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output / "k4_pareto.png", dpi=200, bbox_inches="tight")
    fig.savefig(output / "k4_pareto.svg", bbox_inches="tight")
    plt.close(fig)
    print(json.dumps({"reference": reference, "selected": selected}, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
