#!/usr/bin/env python3
"""Create the paper table for the RP2 v6 local-verifier ablation."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize(rows: list[dict], queries: list[dict], config: dict) -> dict:
    query_by_id = {str(row["query_id"]): row for row in queries}
    scenario_by_id = {str(row["id"]): row for row in config["scenarios"]}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        method = str(row["method"])
        if method not in scenario_by_id:
            raise KeyError(f"Unknown verifier-ablation method: {method}")
        if row.get("quality_fusion") != "none" or int(
            row.get("canonical_quality_repeat", -1)
        ) != 0:
            raise ValueError(f"Invalid v6 quality protocol for {method}:{row['query_id']}")
        grouped[method].append(row)

    methods = {}
    for method, scenario in scenario_by_id.items():
        method_rows = grouped.get(method, [])
        answerable = [
            row
            for row in method_rows
            if query_by_id[str(row["query_id"])].get("relevant_evidence_ids")
        ]
        unanswerable = [row for row in method_rows if row not in answerable]
        citation_precision = [
            row.get("silver_evaluation", {}).get("silver_citation_precision")
            for row in answerable
            if row.get("silver_evaluation", {}).get("silver_citation_precision")
            is not None
        ]
        citation_f1 = [
            float(row.get("silver_evaluation", {}).get("silver_citation_f1") or 0.0)
            for row in answerable
        ]
        pipeline = [
            float(row.get("latency_breakdown_ms", {}).get("generation_pipeline_ms", 0.0))
            for row in method_rows
        ]
        calls = [
            float(row.get("model_metrics", {}).get("cascade_model_call_count", 0.0))
            for row in method_rows
        ]
        methods[method] = {
            "display_name": scenario.get("display_name", method),
            "verification_mode": scenario["verification_mode"],
            "queries": len(method_rows),
            "silver_citation_precision_macro_answered": (
                statistics.fmean(float(value) for value in citation_precision)
                if citation_precision
                else None
            ),
            "silver_citation_f1_macro_answerable": (
                statistics.fmean(citation_f1) if citation_f1 else None
            ),
            "answerable_answer_rate": (
                statistics.fmean(
                    float(row.get("validation", {}).get("status") == "answered")
                    for row in answerable
                )
                if answerable
                else None
            ),
            "unanswerable_abstention_rate": (
                statistics.fmean(
                    float(
                        row.get("validation", {}).get("status")
                        == "insufficient_evidence"
                    )
                    for row in unanswerable
                )
                if unanswerable
                else None
            ),
            "strict_contract_rate": (
                statistics.fmean(
                    float(bool(row.get("validation", {}).get("contract_valid")))
                    for row in method_rows
                )
                if method_rows
                else None
            ),
            "model_calls_mean": statistics.fmean(calls) if calls else None,
            "generation_pipeline_ms_mean": statistics.fmean(pipeline) if pipeline else None,
            "generation_pipeline_ms_p95": _percentile(pipeline, 0.95),
        }
    return {
        "protocol_id": config["protocol_id"],
        "retrieval_candidates_identical_across_methods": True,
        "methods": methods,
        "metric_boundary": "Development Silver evidence agreement; not expert factual correctness",
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", default="configs/rp2_graphrag_v6_verifier_ablation.json"
    )
    parser.add_argument(
        "--generation-results",
        default="results/experiments/research_point_2/graphrag_v6_verifier_ablation/generation_results.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        default="results/experiments/research_point_2/graphrag_v6_verifier_ablation/paper_summary",
    )
    args = parser.parse_args()
    config = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    queries = _read_jsonl(ROOT / config["benchmark_dir"] / "queries.jsonl")
    report = summarize(_read_jsonl(ROOT / args.generation_results), queries, config)
    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = [dict(method=method, **values) for method, values in report["methods"].items()]
    fields = list(rows[0])
    with (output / "table_verifier_ablation.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    markdown = [
        "| Method | Mode | Citation P | Citation F1 | Answer rate | Abstain rate | Calls | Gen. p95 ms |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        value = lambda key: "--" if row[key] is None else f"{float(row[key]):.3f}"
        markdown.append(
            f"| {row['display_name']} | {row['verification_mode']} | "
            f"{value('silver_citation_precision_macro_answered')} | "
            f"{value('silver_citation_f1_macro_answerable')} | "
            f"{value('answerable_answer_rate')} | {value('unanswerable_abstention_rate')} | "
            f"{value('model_calls_mean')} | {value('generation_pipeline_ms_p95')} |"
        )
    (output / "table_verifier_ablation.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8"
    )
    print(f"[RP2 v6 ablation] summary={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
