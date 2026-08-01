#!/usr/bin/env python3
"""Run RP2 budget sensitivity and produce development-only Pareto figures."""

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


def _run(
    queries: list[SilverQuery],
    candidates: list[EvidenceCandidate],
    index: RetrievalIndex,
    *,
    method: str,
    budget: RetrievalBudget,
    repeats: int,
) -> dict:
    results = []
    for _ in range(repeats):
        for query in queries:
            results.append(retrieve(query, index, method=method, budget=budget))
    return evaluate_results(queries, candidates, results)["methods"][method]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark-dir",
        default="data/kg/marine_pump/silver_evidencebench/rp2_development_v1",
    )
    parser.add_argument(
        "--output-dir",
        default="results/experiments/research_point_2/sensitivity_v1",
    )
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()

    benchmark = ROOT / args.benchmark_dir
    candidates = [_candidate(row) for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")]
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    index = RetrievalIndex(candidates)
    rows: list[dict] = []

    experiments = []
    for scored in (8, 16, 32, 64):
        experiments.append(("scored_candidates", scored, scored, 8, 2))
    for selected in (4, 8, 12):
        experiments.append(("selected_evidence", selected, 64, selected, 2))
    for family_cap in (1, 2, 4, 8):
        experiments.append(("source_family_cap", family_cap, 64, 8, family_cap))

    total = len(experiments) * 2
    done = 0
    for axis, value, scored, selected, family_cap in experiments:
        for method in ("metapath_topk", "ours"):
            done += 1
            print(
                f"[RP2 sensitivity][{done}/{total}] axis={axis}, value={value}, method={method}",
                flush=True,
            )
            budget = RetrievalBudget(
                max_scored_candidates=scored,
                max_selected_evidence=selected,
                max_per_source_family=family_cap,
            )
            metrics = _run(
                queries,
                candidates,
                index,
                method=method,
                budget=budget,
                repeats=args.repeats,
            )
            rows.append(
                {
                    "axis": axis,
                    "value": value,
                    "method": method,
                    "max_scored_candidates": scored,
                    "max_selected_evidence": selected,
                    "max_per_source_family": family_cap,
                    **metrics,
                }
            )

    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with (output / "sensitivity.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    (output / "sensitivity.json").write_text(
        json.dumps(
            {
                "label_policy": "Silver only; never Gold",
                "human_expert_reviewed": False,
                "benchmark_scope": "development_only_not_held_out",
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2))
    panels = (
        ("scored_candidates", "Scored candidate budget"),
        ("selected_evidence", "Returned evidence budget"),
        ("source_family_cap", "Per-family cap"),
    )
    colors = {"metapath_topk": "#64748b", "ours": "#0f766e"}
    for axis_plot, (axis_name, title) in zip(axes, panels):
        for method in ("metapath_topk", "ours"):
            subset = sorted(
                (row for row in rows if row["axis"] == axis_name and row["method"] == method),
                key=lambda row: row["value"],
            )
            axis_plot.plot(
                [row["value"] for row in subset],
                [row["recall_at_budget_macro"] for row in subset],
                marker="o",
                color=colors[method],
                label=method,
            )
        axis_plot.set_title(title)
        axis_plot.set_xlabel("Budget value")
        axis_plot.set_ylabel("Silver Recall@budget")
        axis_plot.grid(alpha=0.25)
    axes[0].legend(frameon=False)
    fig.suptitle("RP2 development sensitivity (not held-out)")
    fig.tight_layout()
    fig.savefig(output / "budget_sensitivity.png", dpi=200, bbox_inches="tight")
    fig.savefig(output / "budget_sensitivity.svg", bbox_inches="tight")
    plt.close(fig)
    print(f"[RP2 sensitivity] outputs={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
