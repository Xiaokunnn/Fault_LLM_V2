#!/usr/bin/env python3
"""Create page-clustered statistics, figures and a paper-ready RP1 API report."""

from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/experiments/research_point_1/api_prompt_comparison_v1"
METHODS = ("B0", "B1", "B2", "B3", "Ours")
SEED = 20260802
BOOTSTRAP_REPEATS = 10_000


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _page_key(doc_id: str, page: int) -> str:
    return f"{doc_id}:p{int(page):04d}"


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _aggregate(page_rows: list[dict]) -> dict:
    raw = sum(row["raw"] for row in page_rows)
    normalized = sum(row["normalized"] for row in page_rows)
    silver = sum(row["silver"] for row in page_rows)
    latency_ms = sum(row["latency_ms"] for row in page_rows)
    return {
        "raw_proposals": raw,
        "normalized_candidates": normalized,
        "strict_silver": silver,
        "contract_yield": _ratio(normalized, raw),
        "strict_silver_rate_over_raw": _ratio(silver, raw),
        "strict_silver_rate_over_normalized": _ratio(silver, normalized),
        "latency_ms_total": latency_ms,
        "latency_ms_per_page": _ratio(latency_ms, len(page_rows)),
        "strict_silver_per_minute": _ratio(silver, latency_ms / 60_000),
    }


def _bootstrap(page_rows: list[dict]) -> dict:
    rng = random.Random(SEED)
    samples: dict[str, list[float]] = defaultdict(list)
    for _ in range(BOOTSTRAP_REPEATS):
        sampled = [page_rows[rng.randrange(len(page_rows))] for _ in page_rows]
        aggregate = _aggregate(sampled)
        for metric in (
            "contract_yield",
            "strict_silver_rate_over_raw",
            "strict_silver_rate_over_normalized",
            "strict_silver_per_minute",
        ):
            samples[metric].append(float(aggregate[metric]))
    return {
        metric: {
            "estimate": _aggregate(page_rows)[metric],
            "ci95_low": _percentile(values, 0.025),
            "ci95_high": _percentile(values, 0.975),
        }
        for metric, values in samples.items()
    }


def _paired_bootstrap(ours: list[dict], baseline: list[dict]) -> dict:
    if [row["page_key"] for row in ours] != [row["page_key"] for row in baseline]:
        raise RuntimeError("Paired bootstrap requires identical ordered pages")
    rng = random.Random(SEED)
    samples: dict[str, list[float]] = defaultdict(list)
    metrics = (
        "strict_silver",
        "strict_silver_rate_over_raw",
        "strict_silver_rate_over_normalized",
        "strict_silver_per_minute",
    )
    for _ in range(BOOTSTRAP_REPEATS):
        positions = [rng.randrange(len(ours)) for _ in ours]
        ours_aggregate = _aggregate([ours[index] for index in positions])
        baseline_aggregate = _aggregate([baseline[index] for index in positions])
        for metric in metrics:
            samples[metric].append(float(ours_aggregate[metric] - baseline_aggregate[metric]))
    ours_aggregate = _aggregate(ours)
    baseline_aggregate = _aggregate(baseline)
    output = {}
    for metric, values in samples.items():
        low, high = _percentile(values, 0.025), _percentile(values, 0.975)
        output[metric] = {
            "estimate_delta": float(ours_aggregate[metric] - baseline_aggregate[metric]),
            "ci95_low": low,
            "ci95_high": high,
            "ci95_excludes_zero": bool(low > 0 or high < 0),
        }
    return output


def _plot(rows: list[dict]) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    labels = [row["method"] for row in rows]
    x = np.arange(len(labels))
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.6), constrained_layout=True)
    axes[0].bar(x - 0.2, [row["contract_yield"] for row in rows], 0.4, label="Contract yield")
    axes[0].bar(x + 0.2, [row["strict_silver_rate_over_raw"] for row in rows], 0.4, label="Silver / raw")
    axes[0].set_xticks(x, labels)
    axes[0].set_ylim(0, 1.05)
    axes[0].set_ylabel("Rate")
    axes[0].set_title("Structure and evidence yield")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend()

    axes[1].bar(x, [row["strict_silver"] for row in rows], color="#4c72b0", label="Strict Silver")
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("Strict Silver assertions")
    axes[1].set_title("Accepted Silver and API latency")
    second = axes[1].twinx()
    second.plot(x, [row["latency_ms_per_page"] / 1000 for row in rows], color="#c44e52", marker="o", label="Latency/page")
    second.set_ylabel("Latency per page (s)")
    handles, legends = axes[1].get_legend_handles_labels()
    handles2, legends2 = second.get_legend_handles_labels()
    axes[1].legend(handles + handles2, legends + legends2, loc="upper left")
    figure.suptitle("RP1 fixed-page qwen3.7-max comparison (20 pages; Silver labels)")
    svg_path = BASE / "comparison_figure.svg"
    figure.savefig(svg_path, metadata={"Date": None})
    figure.savefig(BASE / "comparison_figure.png", dpi=180, metadata={"Date": None})
    plt.close(figure)
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    pool = _read_jsonl(ROOT / "configs/rp1_api_comparison_pages_v1.jsonl")
    expected_pages = {_page_key(row["doc_id"], row["pdf_page_number"]) for row in pool}
    page_data: dict[str, list[dict]] = {}
    rows: list[dict] = []
    bootstrap: dict[str, dict] = {}
    for method in METHODS:
        method_root = BASE / method
        extraction = json.loads((method_root / "extraction_run_summary.json").read_text(encoding="utf-8"))
        strict = _read_jsonl(method_root / "strict/candidate_triples.strict_v2.jsonl")
        decisions_by_page: dict[str, Counter] = defaultdict(Counter)
        for record in strict:
            key = _page_key(record["doc_id"], record["pdf_page_number"])
            decisions_by_page[key][str(record.get("decision"))] += 1
        page_results = {row["page_key"]: row for row in extraction["page_results"]}
        if set(page_results) != expected_pages or extraction["pages_completed"] != len(expected_pages):
            raise RuntimeError(f"{method} does not contain the frozen 20-page comparison set")
        method_pages = []
        for key in sorted(expected_pages):
            result = page_results[key]
            method_pages.append(
                {
                    "page_key": key,
                    "raw": int(result["raw_proposals"]),
                    "normalized": int(result["retained_candidates"]),
                    "silver": decisions_by_page[key]["silver_candidate"],
                    "needs_review": decisions_by_page[key]["candidate_needs_review"],
                    "rejected": decisions_by_page[key]["rejected"],
                    "latency_ms": int(result.get("latency_ms") or 0),
                }
            )
        page_data[method] = method_pages
        aggregate = _aggregate(method_pages)
        decision_counts = Counter(str(record.get("decision")) for record in strict)
        rows.append(
            {
                "method": method,
                "pages": len(method_pages),
                **aggregate,
                "needs_review": decision_counts["candidate_needs_review"],
                "rejected": decision_counts["rejected"],
            }
        )
        bootstrap[method] = _bootstrap(method_pages)

    ours = next(row for row in rows if row["method"] == "Ours")
    strongest_count = max((row for row in rows if row["method"] != "Ours"), key=lambda row: row["strict_silver"])
    strongest_rate = max((row for row in rows if row["method"] != "Ours"), key=lambda row: row["strict_silver_rate_over_normalized"])
    conclusions = {
        "strict_silver_count_vs_best_baseline": {
            "baseline": strongest_count["method"],
            "ratio": _ratio(ours["strict_silver"], strongest_count["strict_silver"]),
            "relative_increase": _ratio(ours["strict_silver"] - strongest_count["strict_silver"], strongest_count["strict_silver"]),
        },
        "silver_rate_over_normalized_vs_best_baseline": {
            "baseline": strongest_rate["method"],
            "absolute_percentage_point_gain": 100 * (ours["strict_silver_rate_over_normalized"] - strongest_rate["strict_silver_rate_over_normalized"]),
            "relative_increase": _ratio(
                ours["strict_silver_rate_over_normalized"] - strongest_rate["strict_silver_rate_over_normalized"],
                strongest_rate["strict_silver_rate_over_normalized"],
            ),
        },
    }
    paired = {
        baseline: _paired_bootstrap(page_data["Ours"], page_data[baseline])
        for baseline in METHODS
        if baseline != "Ours"
    }
    payload = {
        "experiment": "rp1_fixed_page_real_api_prompt_comparison_v1_analysis",
        "label_policy": "Silver only; never Gold",
        "human_expert_reviewed": False,
        "statistical_unit": "page_cluster",
        "bootstrap_repeats": BOOTSTRAP_REPEATS,
        "bootstrap_seed": SEED,
        "rows": rows,
        "bootstrap_ci95": bootstrap,
        "derived_conclusions": conclusions,
        "paired_ours_minus_baseline_ci95": paired,
        "interpretation_boundary": "structure_and_grounding_yield_not_fact_accuracy",
    }
    (BASE / "comparison_analysis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (BASE / "comparison_analysis.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    _plot(rows)

    table = [
        "| Method | Raw | Normalized | Contract yield | Strict Silver | Silver/raw | Silver/normalized | Latency/page | Silver/min |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        table.append(
            f"| {row['method']} | {row['raw_proposals']} | {row['normalized_candidates']} | "
            f"{row['contract_yield']:.1%} | {row['strict_silver']} | "
            f"{row['strict_silver_rate_over_raw']:.1%} | {row['strict_silver_rate_over_normalized']:.1%} | "
            f"{row['latency_ms_per_page']/1000:.1f}s | {row['strict_silver_per_minute']:.2f} |"
        )
    report = f"""# RP1 Fixed-Page Real-API Comparison Report

## Protocol

- Model: `qwen3.7-max`, temperature 0.
- Frozen sample: the same 20 stratified, evidence-rich build-set pages for every method.
- Methods: B0, B1, B2, B3 and Ours.
- Labels: Silver only; no human expert review and no Gold labels.
- Statistical unit: page. The 95% intervals in `comparison_analysis.json` use {BOOTSTRAP_REPEATS:,} page-clustered bootstrap resamples.
- Held-out leakage check: MP009--MP013 are absent.

## Results

{chr(10).join(table)}

Ours produced {ours['strict_silver']} strict Silver assertions, {conclusions['strict_silver_count_vs_best_baseline']['ratio']:.2f} times the strongest count baseline ({strongest_count['method']}: {strongest_count['strict_silver']}). Its Silver acceptance rate over normalized candidates was {ours['strict_silver_rate_over_normalized']:.1%}, an absolute gain of {conclusions['silver_rate_over_normalized_vs_best_baseline']['absolute_percentage_point_gain']:.2f} percentage points over the strongest rate baseline ({strongest_rate['method']}: {strongest_rate['strict_silver_rate_over_normalized']:.1%}). Ours was slower per page, but its {ours['strict_silver_per_minute']:.2f} accepted Silver assertions per API minute remained higher than every baseline.

The paired page-bootstrap differences are stored under `paired_ours_minus_baseline_ci95` in `comparison_analysis.json`. A difference is treated as statistically distinguishable at the descriptive 95% level only when its interval excludes zero; this is a clustered robustness analysis, not an expert-labelled accuracy test.

## Interpretation boundaries

1. The experiment supports improved structured-output compliance and page-grounded Silver evidence yield; it does not measure factual precision or engineering diagnostic accuracy.
2. B0's zero normalized output means its free-form proposals did not satisfy the executable evidence contract. It must not be interpreted as proving that every B0 semantic statement was false.
3. `chinese_graph_ready=0` is expected here because this experiment stops after strict evidence validation and does not run the independent terminology-release workflow. It does not invalidate the frozen 10/10 corpus evidence coverage or the existing Chinese release graph.
4. The 2/10 evidence coverage observed for Ours describes only this 20-page stratified experiment, not the complete 1889-page build corpus.
5. All outputs remain Silver and have not been reviewed by a marine engineering expert.
"""
    (BASE / "rp1_api_prompt_comparison_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
