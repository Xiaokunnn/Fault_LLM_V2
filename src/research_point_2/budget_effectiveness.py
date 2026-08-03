"""Paired quality-latency effectiveness analysis for RP2 Silver experiments."""

from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _row_latency(row: dict) -> float:
    measured = row.get("end_to_end_inference_elapsed_ms")
    if measured is not None:
        return float(measured)
    metrics = row.get("model_metrics", {})
    return (
        float(row.get("retrieval_elapsed_ms", 0.0))
        + float(metrics.get("input_preparation_ms", 0.0))
        + float(metrics.get("elapsed_ms", 0.0))
    )


def _bootstrap_paired_delta(
    proposed: list[float],
    reference: list[float],
    *,
    statistic,
    iterations: int,
    seed: int,
) -> list[float]:
    if len(proposed) != len(reference) or not proposed:
        return []
    rng = random.Random(seed)
    size = len(proposed)
    values = []
    for _ in range(iterations):
        indexes = [rng.randrange(size) for _ in range(size)]
        left = [proposed[index] for index in indexes]
        right = [reference[index] for index in indexes]
        values.append(statistic(left) - statistic(right))
    return values


def analyze_budget_effectiveness(
    rows: list[dict],
    *,
    reference_id: str,
    proposed_ids: list[str],
    latency_noninferiority_margin: float = 0.05,
    minimum_quality_gain: float = 0.0,
    bootstrap_iterations: int = 2000,
    seed: int = 20260803,
) -> dict:
    """Test whether proposed scenarios improve Silver utility without latency overhead."""

    grouped: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        grouped[str(row["method"])][str(row["query_id"])] = row
    if reference_id not in grouped:
        raise ValueError(f"Missing reference scenario: {reference_id}")
    reference_queries = set(grouped[reference_id])
    scenario_metrics = {}
    for scenario_id, by_query in sorted(grouped.items()):
        common = sorted(reference_queries & set(by_query))
        utilities = [
            float(by_query[query_id].get("silver_evaluation", {}).get("silver_response_utility", 0.0))
            for query_id in common
        ]
        latencies = [_row_latency(by_query[query_id]) for query_id in common]
        prompt_tokens = [
            float(by_query[query_id].get("model_metrics", {}).get("prompt_tokens", 0.0))
            for query_id in common
        ]
        scenario_metrics[scenario_id] = {
            "paired_queries": len(common),
            "silver_response_utility_macro": statistics.fmean(utilities) if utilities else 0.0,
            "end_to_end_inference_latency_ms_p50": _percentile(latencies, 0.50),
            "end_to_end_inference_latency_ms_p95": _percentile(latencies, 0.95),
            "prompt_tokens_mean": statistics.fmean(prompt_tokens) if prompt_tokens else 0.0,
        }
    reference_rows = grouped[reference_id]
    comparisons = []
    for offset, proposed_id in enumerate(proposed_ids):
        if proposed_id not in grouped:
            continue
        common = sorted(reference_queries & set(grouped[proposed_id]))
        proposed_utility = [
            float(grouped[proposed_id][query_id].get("silver_evaluation", {}).get("silver_response_utility", 0.0))
            for query_id in common
        ]
        reference_utility = [
            float(reference_rows[query_id].get("silver_evaluation", {}).get("silver_response_utility", 0.0))
            for query_id in common
        ]
        proposed_latency = [_row_latency(grouped[proposed_id][query_id]) for query_id in common]
        reference_latency = [_row_latency(reference_rows[query_id]) for query_id in common]
        utility_delta = statistics.fmean(proposed_utility) - statistics.fmean(reference_utility)
        proposed_p95 = _percentile(proposed_latency, 0.95)
        reference_p95 = _percentile(reference_latency, 0.95)
        latency_ratio = proposed_p95 / reference_p95 if reference_p95 else math.inf
        quality_bootstrap = _bootstrap_paired_delta(
            proposed_utility,
            reference_utility,
            statistic=statistics.fmean,
            iterations=bootstrap_iterations,
            seed=seed + offset,
        )
        latency_bootstrap = _bootstrap_paired_delta(
            proposed_latency,
            reference_latency,
            statistic=lambda values: _percentile(values, 0.95),
            iterations=bootstrap_iterations,
            seed=seed + 1000 + offset,
        )
        quality_ci = [
            _percentile(quality_bootstrap, 0.025),
            _percentile(quality_bootstrap, 0.975),
        ]
        latency_ci = [
            _percentile(latency_bootstrap, 0.025),
            _percentile(latency_bootstrap, 0.975),
        ]
        point_quality_gate = utility_delta > minimum_quality_gain
        point_latency_gate = latency_ratio <= 1.0 + latency_noninferiority_margin
        quality_ci_gate = quality_ci[0] > minimum_quality_gain
        allowed_latency_delta_ms = latency_noninferiority_margin * reference_p95
        latency_ci_gate = latency_ci[1] <= allowed_latency_delta_ms
        answerable_pairs = [
            (
                float(grouped[proposed_id][query_id]["silver_evaluation"]["silver_citation_f1"]),
                float(reference_rows[query_id]["silver_evaluation"]["silver_citation_f1"]),
            )
            for query_id in common
            if grouped[proposed_id][query_id].get("silver_evaluation", {}).get("silver_citation_f1") is not None
            and reference_rows[query_id].get("silver_evaluation", {}).get("silver_citation_f1") is not None
        ]
        answerable_f1_delta = (
            statistics.fmean(left for left, _ in answerable_pairs)
            - statistics.fmean(right for _, right in answerable_pairs)
            if answerable_pairs else None
        )
        answerable_f1_bootstrap = _bootstrap_paired_delta(
            [left for left, _ in answerable_pairs],
            [right for _, right in answerable_pairs],
            statistic=statistics.fmean,
            iterations=bootstrap_iterations,
            seed=seed + 2000 + offset,
        )
        comparisons.append(
            {
                "reference_id": reference_id,
                "proposed_id": proposed_id,
                "paired_queries": len(common),
                "silver_utility_delta": utility_delta,
                "silver_utility_delta_bootstrap_95ci": quality_ci,
                "answerable_silver_citation_f1_delta": answerable_f1_delta,
                "answerable_silver_citation_f1_delta_bootstrap_95ci": [
                    _percentile(answerable_f1_bootstrap, 0.025),
                    _percentile(answerable_f1_bootstrap, 0.975),
                ] if answerable_f1_bootstrap else None,
                "end_to_end_p95_latency_delta_ms": proposed_p95 - reference_p95,
                "end_to_end_p95_latency_delta_bootstrap_95ci": latency_ci,
                "end_to_end_p95_latency_ratio": latency_ratio,
                "allowed_latency_delta_ms": allowed_latency_delta_ms,
                "point_estimate_quality_gate": point_quality_gate,
                "point_estimate_latency_gate": point_latency_gate,
                "point_estimate_joint_gate": point_quality_gate and point_latency_gate,
                "quality_improvement_gate": quality_ci_gate,
                "latency_noninferiority_gate": latency_ci_gate,
                "joint_effectiveness_gate": quality_ci_gate and latency_ci_gate,
            }
        )
    pareto_ids = []
    for candidate_id, candidate in scenario_metrics.items():
        dominated = any(
            other_id != candidate_id
            and other["silver_response_utility_macro"] >= candidate["silver_response_utility_macro"]
            and other["end_to_end_inference_latency_ms_p95"] <= candidate["end_to_end_inference_latency_ms_p95"]
            and (
                other["silver_response_utility_macro"] > candidate["silver_response_utility_macro"]
                or other["end_to_end_inference_latency_ms_p95"] < candidate["end_to_end_inference_latency_ms_p95"]
            )
            for other_id, other in scenario_metrics.items()
        )
        if not dominated:
            pareto_ids.append(candidate_id)
    return {
        "primary_hypothesis": (
            "Under the same local 7B generator and generation contract, the proposed retrieval "
            "improves frozen-Silver response utility while its p95 end-to-end inference latency "
            "is no more than the declared margin above Dense RAG."
        ),
        "reference_id": reference_id,
        "latency_noninferiority_margin": latency_noninferiority_margin,
        "minimum_quality_gain": minimum_quality_gain,
        "bootstrap_iterations": bootstrap_iterations,
        "scenario_metrics": scenario_metrics,
        "comparisons": comparisons,
        "quality_latency_pareto_scenarios": pareto_ids,
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
        "metric_boundary": "Silver response utility is not expert factual correctness",
    }
