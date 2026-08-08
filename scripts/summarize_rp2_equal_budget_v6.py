#!/usr/bin/env python3
"""Summarize the RP2 v6 equal-budget experiment for paper reporting.

The v6 protocol makes one deterministic quality decision per query.  Three
interleaved executions are measurement repetitions only; they must not be
summed as online latency or fused into the answer.  This script consumes the
frozen JSONL outputs, recomputes Silver retrieval/citation metrics from the
benchmark labels, and writes paper-ready tables plus fault-class cluster
bootstrap confidence intervals.

All labels and reported quality measures remain Silver.  They are agreement
with the frozen evidence benchmark, not human-expert factual accuracy.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT = (
    ROOT
    / "results"
    / "experiments"
    / "research_point_2"
    / "graphrag_v6_equal_budget"
)
DEFAULT_QUERIES = (
    ROOT
    / "data"
    / "kg"
    / "marine_pump"
    / "silver_evidencebench"
    / "rp2_full_graph_development_v2"
    / "queries.jsonl"
)

METHOD_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "B1_dense_k3_equal",
        "label": "Dense K3",
        "budget": 3,
        "group": "equal_budget_main",
        "role": False,
        "graph": False,
        "fault_affinity": False,
        "source_novelty": False,
    },
    {
        "id": "B4_role_k3_equal",
        "label": "Role K3",
        "budget": 3,
        "group": "equal_budget_main",
        "role": True,
        "graph": False,
        "fault_affinity": False,
        "source_novelty": False,
    },
    {
        "id": "A2_role_graph_k3_equal",
        "label": "Role + Graph K3",
        "budget": 3,
        "group": "equal_budget_main",
        "role": True,
        "graph": True,
        "fault_affinity": False,
        "source_novelty": False,
    },
    {
        "id": "Ours_v6_k3_equal",
        "label": "Full K3",
        "budget": 3,
        "group": "equal_budget_main",
        "role": True,
        "graph": True,
        "fault_affinity": True,
        "source_novelty": True,
    },
    {
        "id": "B1_dense_k4_secondary",
        "label": "Dense K4",
        "budget": 4,
        "group": "cross_budget_secondary",
        "role": False,
        "graph": False,
        "fault_affinity": False,
        "source_novelty": False,
    },
)

QUALITY_METRICS = (
    "retrieval_recall_macro",
    "retrieval_ndcg_macro",
    "citation_precision_macro",
    "citation_recall_macro",
    "citation_f1_macro",
    "answer_precision",
    "answer_recall",
    "abstention_precision",
    "abstention_recall",
    "end_to_end_latency_ms_mean",
)

PAIRED_COMPARISONS = (
    ("Full_vs_Dense_K3", "B1_dense_k3_equal", "Ours_v6_k3_equal"),
    ("Full_vs_Role_K3", "B4_role_k3_equal", "Ours_v6_k3_equal"),
    (
        "Full_vs_RoleGraph_K3",
        "A2_role_graph_k3_equal",
        "Ours_v6_k3_equal",
    ),
    (
        "RoleGraph_vs_Role_K3",
        "B4_role_k3_equal",
        "A2_role_graph_k3_equal",
    ),
)

PAIRED_EFFECT_METRICS = (
    "retrieval_recall_macro",
    "retrieval_ndcg_macro",
    "citation_f1_macro",
    "end_to_end_latency_ms_mean",
)

LATENCY_STAGES = (
    "retrieval",
    "prompt_build",
    "stage1_verifier",
    "stage2_review",
    "render",
    "input_preparation",
    "model_inference",
    "generation_pipeline",
    "end_to_end",
)

LATENCY_ALIASES: dict[str, tuple[str, ...]] = {
    "retrieval": (
        "retrieval",
        "retrieval_ms",
        "retrieval_elapsed_ms",
    ),
    "prompt_build": (
        "prompt_build",
        "prompt_build_ms",
        "prompt",
        "prompt_ms",
        "input_preparation",
        "input_preparation_ms",
    ),
    "stage1_verifier": (
        "stage1_verifier",
        "stage1_verifier_ms",
        "stage1",
        "stage1_ms",
        "stage1_model_ms",
        "first_stage",
        "first_stage_ms",
        "precision_mask",
        "precision_mask_ms",
    ),
    "stage2_review": (
        "stage2_review",
        "stage2_review_ms",
        "stage2",
        "stage2_ms",
        "stage2_review_ms",
        "review",
        "review_ms",
        "recall_review",
        "recall_review_ms",
    ),
    "render": (
        "render",
        "render_ms",
        "guard_render",
        "guard_render_ms",
        "faithfulness_guard",
        "faithfulness_guard_ms",
    ),
    "generation_pipeline": (
        "generation_pipeline",
        "generation_pipeline_ms",
        "generation_only",
        "generation_only_ms",
    ),
    "input_preparation": (
        "input_preparation",
        "input_preparation_ms",
    ),
    "model_inference": (
        "model_inference",
        "model_inference_ms",
    ),
    "end_to_end": (
        "end_to_end",
        "end_to_end_ms",
        "end_to_end_inference",
        "end_to_end_inference_ms",
        "total",
        "total_ms",
    ),
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(payload)
    return rows


def _percentile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _mean(values: Iterable[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return statistics.fmean(clean) if clean else None


def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Mapping):
        for key in ("elapsed_ms", "latency_ms", "total_ms", "value"):
            if key in value:
                parsed = _numeric(value[key])
                if parsed is not None:
                    return parsed
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        parsed = [_numeric(item) for item in value]
        clean = [item for item in parsed if item is not None]
        return sum(clean) if clean else None
    return None


def _first_numeric(mapping: Mapping[str, Any], aliases: Sequence[str]) -> float | None:
    for key in aliases:
        if key in mapping:
            value = _numeric(mapping[key])
            if value is not None:
                return value
    return None


def _normalize_breakdown(mapping: Mapping[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for stage, aliases in LATENCY_ALIASES.items():
        value = _first_numeric(mapping, aliases)
        if value is not None:
            normalized[stage] = value
    return normalized


def _generation_pipeline_ms(breakdown: Mapping[str, float]) -> float | None:
    explicit = breakdown.get("generation_pipeline")
    if explicit is not None:
        return explicit
    stages = (
        "prompt_build",
        "stage1_verifier",
        "stage2_review",
        "render",
        "model_total_unsplit",
    )
    values = [breakdown[stage] for stage in stages if stage in breakdown]
    return sum(values) if values else None


def _latency_breakdown(
    row: Mapping[str, Any],
    fresh_retrieval_by_repeat: Mapping[int, float] | None = None,
) -> tuple[dict[str, float], dict[str, int]]:
    """Reduce v6 measurement repeats without using archived retrieval latency.

    Fresh retrieval timing is paired with generation timing by repeat index.
    ``retrieval_elapsed_ms`` embedded in replay/generation rows is deliberately
    ignored because it was captured under an earlier execution protocol.
    """

    top_level = row.get("latency_breakdown_ms")
    if isinstance(top_level, Mapping):
        result = _normalize_breakdown(top_level)
        result.pop("retrieval", None)
        result.pop("end_to_end", None)
    else:
        result = {}

    repeats = row.get("measurement_repeats")
    expected_repeats = 0
    matched_repeats = 0
    if isinstance(repeats, list) and repeats:
        repeat_breakdowns: list[tuple[int, dict[str, float]]] = []
        for repeat in repeats:
            if not isinstance(repeat, Mapping):
                continue
            repeat_index = int(repeat.get("repeat", len(repeat_breakdowns)))
            raw = repeat.get("latency_breakdown_ms", repeat)
            if isinstance(raw, Mapping):
                normalized = _normalize_breakdown(raw)
                normalized.pop("retrieval", None)
                normalized.pop("end_to_end", None)
                pipeline = _generation_pipeline_ms(normalized)
                if pipeline is not None:
                    normalized["generation_pipeline"] = pipeline
                repeat_breakdowns.append((repeat_index, normalized))
        expected_repeats = len(repeat_breakdowns)
        for stage in LATENCY_STAGES:
            if stage in {"retrieval", "end_to_end"}:
                continue
            values = [item[stage] for _, item in repeat_breakdowns if stage in item]
            median = _percentile(values, 0.50)
            if median is not None:
                result.setdefault(stage, median)
        fresh_values: list[float] = []
        end_to_end_values: list[float] = []
        for repeat_index, breakdown in repeat_breakdowns:
            if not fresh_retrieval_by_repeat:
                continue
            fresh = fresh_retrieval_by_repeat.get(repeat_index)
            pipeline = breakdown.get("generation_pipeline")
            if fresh is None or pipeline is None:
                continue
            matched_repeats += 1
            fresh_values.append(float(fresh))
            end_to_end_values.append(float(fresh) + pipeline)
        # A partial triplet is not a valid v6 timing sample.  Keep generation
        # stages reportable, but mark retrieval/E2E pending until every repeat
        # has a fresh, ranking-verified counterpart.
        if expected_repeats > 0 and matched_repeats == expected_repeats:
            fresh_median = _percentile(fresh_values, 0.50)
            end_to_end_median = _percentile(end_to_end_values, 0.50)
            if fresh_median is not None:
                result["retrieval"] = fresh_median
            if end_to_end_median is not None:
                result["end_to_end"] = end_to_end_median

    model_metrics = row.get("model_metrics", {})
    if isinstance(model_metrics, Mapping):
        preparation = _numeric(model_metrics.get("input_preparation_ms"))
        if preparation is not None:
            result.setdefault("prompt_build", preparation)
        model_elapsed = _numeric(model_metrics.get("elapsed_ms"))
        if model_elapsed is not None and not {
            "stage1_verifier",
            "stage2_review",
        }.intersection(result):
            # Legacy compatibility only. v6 should expose stage 1 and stage 2.
            result["model_total_unsplit"] = model_elapsed
    guard = row.get("faithfulness_guard")
    if isinstance(guard, Mapping):
        guard_elapsed = _numeric(guard.get("elapsed_ms"))
        if guard_elapsed is not None:
            result.setdefault("render", guard_elapsed)
    pipeline = _generation_pipeline_ms(result)
    if pipeline is not None:
        result.setdefault("generation_pipeline", pipeline)
    return result, {
        "expected_repeats": expected_repeats,
        "fresh_retrieval_matched_repeats": matched_repeats,
    }


def _ranked_ids(row: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    for item in row.get("ranked", []) or []:
        if isinstance(item, Mapping):
            evidence_id = item.get("evidence_id")
        else:
            evidence_id = item
        if evidence_id:
            ids.append(str(evidence_id))
    return ids


def _citation_ids(row: Mapping[str, Any]) -> set[str]:
    cited: set[str] = set()
    answer = row.get("answer", {})
    if not isinstance(answer, Mapping):
        return cited
    for point in answer.get("answer_points", []) or []:
        if not isinstance(point, Mapping):
            continue
        for evidence_id in point.get("evidence_ids", []) or []:
            if evidence_id:
                cited.add(str(evidence_id))
    return cited


def _status_and_contract(row: Mapping[str, Any]) -> tuple[str, bool]:
    validation = row.get("validation", {})
    answer = row.get("answer", {})
    status = None
    if isinstance(validation, Mapping):
        status = validation.get("status")
    if not status and isinstance(answer, Mapping):
        status = answer.get("status")
    contract_valid = True
    if isinstance(validation, Mapping) and "contract_valid" in validation:
        contract_valid = bool(validation["contract_valid"])
    return str(status or "invalid"), contract_valid


def _model_quantity(row: Mapping[str, Any], *keys: str) -> float | None:
    metrics = row.get("model_metrics", {})
    if isinstance(metrics, Mapping):
        for key in keys:
            value = _numeric(metrics.get(key))
            if value is not None:
                return value
    repeats = row.get("measurement_repeats")
    if isinstance(repeats, list):
        values: list[float] = []
        for repeat in repeats:
            if not isinstance(repeat, Mapping):
                continue
            for key in keys:
                value = _numeric(repeat.get(key))
                if value is not None:
                    values.append(value)
                    break
        return _percentile(values, 0.50)
    return None


def _query_record(
    query: Mapping[str, Any],
    retrieval: Mapping[str, Any],
    generation: Mapping[str, Any],
    fresh_retrieval_by_repeat: Mapping[int, float] | None = None,
) -> dict[str, Any]:
    relevant = {str(item) for item in query.get("relevant_evidence_ids", []) or []}
    ranked = _ranked_ids(retrieval)
    ranked_rows = [item for item in retrieval.get("ranked", []) if isinstance(item, Mapping)]
    source_families = {
        str(item["source_family_id"])
        for item in ranked_rows
        if item.get("source_family_id")
    }
    claim_ids = [str(item["claim_id"]) for item in ranked_rows if item.get("claim_id")]
    answerable = bool(relevant)
    hits = [int(item in relevant) for item in ranked]
    if answerable:
        retrieval_recall = sum(hits) / len(relevant)
        dcg = sum(hit / math.log2(rank + 1) for rank, hit in enumerate(hits, start=1))
        ideal_hits = min(len(relevant), len(ranked))
        idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
        retrieval_ndcg = dcg / idcg if idcg else 0.0
    else:
        retrieval_recall = None
        retrieval_ndcg = None

    status, contract_valid = _status_and_contract(generation)
    valid_answer = status == "answered" and contract_valid
    valid_abstention = status == "insufficient_evidence" and contract_valid
    cited = _citation_ids(generation) if contract_valid else set()
    if answerable:
        matched = cited & relevant
        citation_precision = len(matched) / len(cited) if cited else 0.0
        citation_recall = len(matched) / len(relevant)
        citation_f1 = (
            2.0 * citation_precision * citation_recall
            / (citation_precision + citation_recall)
            if citation_precision + citation_recall
            else 0.0
        )
    else:
        citation_precision = None
        citation_recall = None
        citation_f1 = None

    latency, latency_pairing = _latency_breakdown(
        generation, fresh_retrieval_by_repeat
    )
    return {
        "query_id": str(query["query_id"]),
        "fault_id": str(query.get("fault_id") or query["query_id"].split("-")[1]),
        "role": query.get("role"),
        "answerable": answerable,
        "valid_answer": valid_answer,
        "valid_abstention": valid_abstention,
        "contract_valid": contract_valid,
        "retrieval_recall": retrieval_recall,
        "retrieval_ndcg": retrieval_ndcg,
        "citation_precision": citation_precision,
        "citation_recall": citation_recall,
        "citation_f1": citation_f1,
        "citation_count": len(cited),
        "relevant_count": len(relevant),
        "matched_citation_count": len(cited & relevant),
        "source_family_coverage": len(source_families),
        "exact_claim_redundancy": (
            1.0 - len(set(claim_ids)) / len(claim_ids) if claim_ids else 0.0
        ),
        "model_calls": _model_quantity(
            generation,
            "model_call_count",
            "cascade_model_call_count",
        ),
        "prompt_tokens": _model_quantity(generation, "prompt_tokens"),
        "generated_tokens": _model_quantity(generation, "generated_tokens"),
        "latency_ms": latency,
        "latency_pairing": latency_pairing,
    }


def _aggregate(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    answerable = [row for row in records if row["answerable"]]
    unanswerable = [row for row in records if not row["answerable"]]
    valid_answers = [row for row in records if row["valid_answer"]]
    valid_abstentions = [row for row in records if row["valid_abstention"]]
    true_answerable_answers = sum(row["answerable"] for row in valid_answers)
    true_unanswerable_abstentions = sum(
        not row["answerable"] for row in valid_abstentions
    )

    latencies: dict[str, dict[str, float | None]] = {}
    latency_stage_names = list(LATENCY_STAGES)
    if any("model_total_unsplit" in row["latency_ms"] for row in records):
        latency_stage_names.insert(-1, "model_total_unsplit")
    for stage in latency_stage_names:
        values = [
            float(row["latency_ms"][stage])
            for row in records
            if stage in row["latency_ms"]
        ]
        latencies[stage] = {
            "samples": len(values),
            "mean_ms": _mean(values),
            "p50_ms": _percentile(values, 0.50),
            "p95_ms": _percentile(values, 0.95),
        }

    return {
        "queries": len(records),
        "fault_classes": len({row["fault_id"] for row in records}),
        "answerable_queries": len(answerable),
        "unanswerable_queries": len(unanswerable),
        "valid_answered_queries": len(valid_answers),
        "valid_abstained_queries": len(valid_abstentions),
        "invalid_contract_queries": sum(not row["contract_valid"] for row in records),
        "valid_contract_rate": _mean(float(row["contract_valid"]) for row in records),
        "retrieval_recall_macro": _mean(row["retrieval_recall"] for row in records),
        "retrieval_ndcg_macro": _mean(row["retrieval_ndcg"] for row in records),
        "citation_precision_macro": _mean(row["citation_precision"] for row in records),
        "citation_recall_macro": _mean(row["citation_recall"] for row in records),
        "citation_f1_macro": _mean(row["citation_f1"] for row in records),
        "source_family_coverage_mean": _mean(
            row.get("source_family_coverage", 0.0) for row in records
        ),
        "exact_claim_redundancy_mean": _mean(
            row.get("exact_claim_redundancy", 0.0) for row in records
        ),
        "answer_precision": _safe_ratio(true_answerable_answers, len(valid_answers)),
        "answer_recall": _safe_ratio(true_answerable_answers, len(answerable)),
        "answerable_coverage": _safe_ratio(true_answerable_answers, len(answerable)),
        "abstention_precision": _safe_ratio(
            true_unanswerable_abstentions, len(valid_abstentions)
        ),
        "abstention_recall": _safe_ratio(
            true_unanswerable_abstentions, len(unanswerable)
        ),
        "model_calls": _distribution(row["model_calls"] for row in records),
        "prompt_tokens": _distribution(row["prompt_tokens"] for row in records),
        "generated_tokens": _distribution(
            row["generated_tokens"] for row in records
        ),
        "latency": latencies,
        "end_to_end_latency_ms_mean": latencies["end_to_end"]["mean_ms"],
        "metric_boundary": (
            "Macro citation precision/recall/F1 are computed over all answerable "
            "queries; a valid abstention on an answerable query scores zero. "
            "These are Silver evidence-label agreement metrics."
        ),
    }


def _distribution(values: Iterable[float | None]) -> dict[str, float | int | None]:
    clean = [float(value) for value in values if value is not None]
    return {
        "samples": len(clean),
        "mean": _mean(clean),
        "p50": _percentile(clean, 0.50),
        "p95": _percentile(clean, 0.95),
    }


def _bootstrap_metric(records: Sequence[Mapping[str, Any]], metric: str) -> float | None:
    summary = _aggregate(records)
    value = summary.get(metric)
    return float(value) if value is not None else None


def _cluster_bootstrap(
    records_by_method: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    replicates: int,
    seed: int,
    confidence: float,
) -> dict[str, dict[str, dict[str, float | int | None]]]:
    if replicates <= 0:
        return {}
    all_clusters = sorted(
        {
            str(row["fault_id"])
            for records in records_by_method.values()
            for row in records
        }
    )
    if not all_clusters:
        return {}
    rng = random.Random(seed)
    cluster_samples = [
        [rng.choice(all_clusters) for _ in all_clusters]
        for _ in range(replicates)
    ]
    alpha = (1.0 - confidence) / 2.0
    output: dict[str, dict[str, dict[str, float | int | None]]] = {}
    for method, records in records_by_method.items():
        by_cluster: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in records:
            by_cluster[str(row["fault_id"])].append(row)
        point = _aggregate(records)
        output[method] = {}
        for metric in QUALITY_METRICS:
            estimates: list[float] = []
            for sample in cluster_samples:
                sampled_rows = [
                    row
                    for cluster in sample
                    for row in by_cluster.get(cluster, [])
                ]
                value = _bootstrap_metric(sampled_rows, metric)
                if value is not None:
                    estimates.append(value)
            output[method][metric] = {
                "point": point.get(metric),
                "ci_low": _percentile(estimates, alpha),
                "ci_high": _percentile(estimates, 1.0 - alpha),
                "replicates": len(estimates),
                "clusters": len(all_clusters),
            }
    return output


def _paired_cluster_bootstrap(
    records_by_method: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    comparisons: Sequence[tuple[str, str, str]],
    replicates: int,
    seed: int,
    confidence: float,
) -> dict[str, Any]:
    """Estimate paired method deltas by resampling the same fault clusters."""

    if replicates <= 0:
        return {}
    all_clusters = sorted(
        {
            str(row["fault_id"])
            for records in records_by_method.values()
            for row in records
        }
    )
    if not all_clusters:
        return {}
    rng = random.Random(seed)
    cluster_samples = [
        [rng.choice(all_clusters) for _ in all_clusters]
        for _ in range(replicates)
    ]
    by_method_cluster: dict[str, dict[str, list[Mapping[str, Any]]]] = {}
    for method, records in records_by_method.items():
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in records:
            grouped[str(row["fault_id"])].append(row)
        by_method_cluster[method] = grouped

    alpha = (1.0 - confidence) / 2.0
    output: dict[str, Any] = {}
    for comparison_id, reference, proposed in comparisons:
        if reference not in records_by_method or proposed not in records_by_method:
            continue
        reference_point = _aggregate(records_by_method[reference])
        proposed_point = _aggregate(records_by_method[proposed])
        metrics: dict[str, Any] = {}
        for metric in PAIRED_EFFECT_METRICS:
            reference_value = reference_point.get(metric)
            proposed_value = proposed_point.get(metric)
            point_delta = (
                float(proposed_value) - float(reference_value)
                if reference_value is not None and proposed_value is not None
                else None
            )
            deltas: list[float] = []
            for sample in cluster_samples:
                reference_rows = [
                    row
                    for cluster in sample
                    for row in by_method_cluster[reference].get(cluster, [])
                ]
                proposed_rows = [
                    row
                    for cluster in sample
                    for row in by_method_cluster[proposed].get(cluster, [])
                ]
                reference_sample = _bootstrap_metric(reference_rows, metric)
                proposed_sample = _bootstrap_metric(proposed_rows, metric)
                if reference_sample is not None and proposed_sample is not None:
                    deltas.append(proposed_sample - reference_sample)
            lower_is_better = metric == "end_to_end_latency_ms_mean"
            metrics[metric] = {
                "point_delta_proposed_minus_reference": point_delta,
                "ci_low": _percentile(deltas, alpha),
                "ci_high": _percentile(deltas, 1.0 - alpha),
                "favorable_direction": "negative" if lower_is_better else "positive",
                "bootstrap_favorable_probability": (
                    statistics.fmean(
                        float(delta < 0.0 if lower_is_better else delta > 0.0)
                        for delta in deltas
                    )
                    if deltas
                    else None
                ),
                "replicates": len(deltas),
                "clusters": len(all_clusters),
            }
        output[comparison_id] = {
            "reference": reference,
            "proposed": proposed,
            "metrics": metrics,
        }
    return output


def _method_spec(method: str) -> dict[str, Any] | None:
    return next((dict(item) for item in METHOD_SPECS if item["id"] == method), None)


def _round(value: Any, digits: int = 6) -> Any:
    return round(float(value), digits) if value is not None else None


def _console_number(value: Any, digits: int) -> str:
    return f"{float(value):.{digits}f}" if value is not None else "pending"


def _csv_row(
    spec: Mapping[str, Any],
    summary: Mapping[str, Any],
    intervals: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "method_id": spec["id"],
        "method": spec["label"],
        "budget_k": spec["budget"],
        "group": spec["group"],
        "role_filter": spec["role"],
        "graph_expansion": spec["graph"],
        "fault_affinity": spec["fault_affinity"],
        "source_novelty": spec["source_novelty"],
        "queries": summary["queries"],
        "answerable_queries": summary["answerable_queries"],
        "unanswerable_queries": summary["unanswerable_queries"],
        "source_family_coverage_mean": _round(
            summary["source_family_coverage_mean"]
        ),
        "exact_claim_redundancy_mean": _round(
            summary["exact_claim_redundancy_mean"]
        ),
    }
    metrics = (
        "retrieval_recall_macro",
        "retrieval_ndcg_macro",
        "citation_precision_macro",
        "citation_recall_macro",
        "citation_f1_macro",
        "answer_precision",
        "answer_recall",
        "abstention_precision",
        "abstention_recall",
    )
    for metric in metrics:
        interval = intervals.get(metric, {})
        row[metric] = _round(summary.get(metric))
        row[f"{metric}_ci_low"] = _round(interval.get("ci_low"))
        row[f"{metric}_ci_high"] = _round(interval.get("ci_high"))
    for metric in ("model_calls", "prompt_tokens", "generated_tokens"):
        distribution = summary[metric]
        row[f"{metric}_mean"] = _round(distribution["mean"], 3)
        row[f"{metric}_p95"] = _round(distribution["p95"], 3)
    latency = summary["latency"]["end_to_end"]
    row["end_to_end_latency_ms_mean"] = _round(latency["mean_ms"], 3)
    row["end_to_end_latency_ms_p50"] = _round(latency["p50_ms"], 3)
    row["end_to_end_latency_ms_p95"] = _round(latency["p95_ms"], 3)
    return row


def _ci_text(
    value: float | None,
    interval: Mapping[str, Any] | None,
    *,
    digits: int = 3,
) -> str:
    if value is None:
        return "--"
    if not interval or interval.get("ci_low") is None:
        return f"{value:.{digits}f}"
    return (
        f"{value:.{digits}f} "
        f"[{float(interval['ci_low']):.{digits}f}, "
        f"{float(interval['ci_high']):.{digits}f}]"
    )


def _markdown_rows(
    specs: Sequence[Mapping[str, Any]],
    summaries: Mapping[str, Mapping[str, Any]],
    intervals: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> str:
    headers = (
        "Method",
        "K",
        "Role",
        "Graph",
        "Fault",
        "Source",
        "Families",
        "Claim dup.",
        "Recall@K (95% CI)",
        "NDCG@K (95% CI)",
        "Citation P",
        "Citation R",
        "Citation F1 (95% CI)",
        "Answer P/R",
        "Abstain P/R",
        "Calls",
        "Prompt tok.",
        "E2E mean/p95 ms",
    )
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for spec in specs:
        method = str(spec["id"])
        summary = summaries[method]
        ci = intervals.get(method, {})
        values = (
            str(spec["label"]),
            str(spec["budget"]),
            "Y" if spec["role"] else "--",
            "Y" if spec["graph"] else "--",
            "Y" if spec["fault_affinity"] else "--",
            "Y" if spec["source_novelty"] else "--",
            _ci_text(summary["source_family_coverage_mean"], None, digits=2),
            _ci_text(summary["exact_claim_redundancy_mean"], None, digits=3),
            _ci_text(summary["retrieval_recall_macro"], ci.get("retrieval_recall_macro")),
            _ci_text(summary["retrieval_ndcg_macro"], ci.get("retrieval_ndcg_macro")),
            _ci_text(summary["citation_precision_macro"], None),
            _ci_text(summary["citation_recall_macro"], None),
            _ci_text(summary["citation_f1_macro"], ci.get("citation_f1_macro")),
            f"{_ci_text(summary['answer_precision'], None)}/{_ci_text(summary['answer_recall'], None)}",
            f"{_ci_text(summary['abstention_precision'], None)}/{_ci_text(summary['abstention_recall'], None)}",
            _ci_text(summary["model_calls"]["mean"], None, digits=2),
            _ci_text(summary["prompt_tokens"]["mean"], None, digits=1),
            (
                f"{_ci_text(summary['latency']['end_to_end']['mean_ms'], None, digits=1)}/"
                f"{_ci_text(summary['latency']['end_to_end']['p95_ms'], None, digits=1)}"
            ),
        )
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        return
    fields = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _validate_v6_protocol(generations: Sequence[Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for row in generations:
        query_id = row.get("query_id", "<unknown>")
        method = row.get("method", "<unknown>")
        fusion = row.get("quality_fusion", "none")
        canonical = row.get("canonical_quality_repeat", 0)
        if fusion != "none":
            raise ValueError(
                f"{method}:{query_id} uses quality_fusion={fusion!r}; "
                "v6 forbids majority-vote quality fusion"
            )
        if int(canonical) != 0:
            raise ValueError(
                f"{method}:{query_id} canonical_quality_repeat must be 0"
            )
        repeats = row.get("measurement_repeats")
        if not isinstance(repeats, list) or len(repeats) < 2:
            warnings.append(
                f"{method}:{query_id} has fewer than two measurement repetitions"
            )
    return sorted(set(warnings))


def summarize(
    *,
    queries: Sequence[Mapping[str, Any]],
    retrieval_rows: Sequence[Mapping[str, Any]],
    generation_rows: Sequence[Mapping[str, Any]],
    retrieval_latency_rows: Sequence[Mapping[str, Any]] = (),
    bootstrap_replicates: int,
    seed: int,
    confidence: float,
    method_specs: Sequence[Mapping[str, Any]] | None = None,
    paired_comparisons: Sequence[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    active_specs = [dict(spec) for spec in (method_specs or METHOD_SPECS)]
    active_comparisons = tuple(paired_comparisons or PAIRED_COMPARISONS)
    query_by_id = {str(row["query_id"]): row for row in queries}
    retrieval_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in retrieval_rows:
        key = (str(row["method"]), str(row["query_id"]))
        if key in retrieval_by_key:
            raise ValueError(f"Duplicate retrieval row: {key}")
        retrieval_by_key[key] = row
    generation_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in generation_rows:
        key = (str(row["method"]), str(row["query_id"]))
        if key in generation_by_key:
            raise ValueError(f"Duplicate generation row: {key}")
        generation_by_key[key] = row

    fresh_latency_by_key: dict[tuple[int, str, str], float] = {}
    for row in retrieval_latency_rows:
        key = (int(row["repeat"]), str(row["method"]), str(row["query_id"]))
        if key in fresh_latency_by_key:
            raise ValueError(f"Duplicate fresh retrieval latency row: {key}")
        if row.get("ranking_matches_immutable_replay") is not True:
            raise ValueError(f"Fresh retrieval ranking mismatch: {key}")
        latency = _numeric(row.get("retrieval_ms"))
        if latency is None:
            raise ValueError(f"Fresh retrieval latency missing retrieval_ms: {key}")
        fresh_latency_by_key[key] = latency

    warnings = _validate_v6_protocol(generation_rows)
    pending_e2e: list[tuple[str, str, int, int]] = []
    records_by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, generation in generation_by_key.items():
        method, query_id = key
        if method not in {str(spec["id"]) for spec in active_specs}:
            warnings.append(f"Ignored unregistered method: {method}")
            continue
        if query_id not in query_by_id:
            raise KeyError(f"Generation row references unknown query: {query_id}")
        retrieval = retrieval_by_key.get(key)
        if retrieval is None:
            source_method = generation.get("source_retrieval_method")
            if source_method is not None:
                retrieval = retrieval_by_key.get((str(source_method), query_id))
        if retrieval is None:
            raise KeyError(f"Missing retrieval row for {method}:{query_id}")
        repeat_latencies = {
            repeat: latency
            for (repeat, latency_method, latency_query), latency in fresh_latency_by_key.items()
            if latency_method == method and latency_query == query_id
        }
        record = _query_record(
            query_by_id[query_id],
            retrieval,
            generation,
            repeat_latencies,
        )
        pairing = record["latency_pairing"]
        if pairing["fresh_retrieval_matched_repeats"] < pairing["expected_repeats"]:
            pending_e2e.append(
                (
                    method,
                    query_id,
                    pairing["fresh_retrieval_matched_repeats"],
                    pairing["expected_repeats"],
                )
            )
        records_by_method[method].append(record)

    if pending_e2e:
        preview = ", ".join(
            f"{method}:{query_id}({matched}/{expected})"
            for method, query_id, matched, expected in pending_e2e[:5]
        )
        suffix = " ..." if len(pending_e2e) > 5 else ""
        warnings.append(
            f"E2E latency pending for {len(pending_e2e)} method-query rows; "
            f"fresh retrieval repeat pairs incomplete: {preview}{suffix}"
        )

    present_specs = [
        dict(spec) for spec in active_specs if spec["id"] in records_by_method
    ]
    missing = [spec["id"] for spec in active_specs if spec["id"] not in records_by_method]
    if missing:
        warnings.append("Missing expected methods: " + ", ".join(missing))
    summaries = {
        method: _aggregate(records) for method, records in records_by_method.items()
    }
    intervals = _cluster_bootstrap(
        records_by_method,
        replicates=bootstrap_replicates,
        seed=seed,
        confidence=confidence,
    )
    paired_effects = _paired_cluster_bootstrap(
        records_by_method,
        comparisons=active_comparisons,
        replicates=bootstrap_replicates,
        seed=seed,
        confidence=confidence,
    )
    return {
        "protocol_id": "rp2_equal_budget_paper_summary_v1",
        "label_policy": "Silver only; never Gold",
        "human_expert_reviewed": False,
        "quality_decision": (
            "canonical measurement repeat 0; interleaved repeats are timing "
            "measurements only and are not fused"
        ),
        "latency_policy": (
            "Fresh retrieval timings are paired with generation-only timings by "
            "(repeat, method, query_id). Archived retrieval_elapsed_ms values are "
            "never used. E2E is null when fresh timing is incomplete."
        ),
        "latency_pairing": {
            "method_query_rows": sum(len(rows) for rows in records_by_method.values()),
            "complete_method_query_rows": (
                sum(len(rows) for rows in records_by_method.values()) - len(pending_e2e)
            ),
            "pending_method_query_rows": len(pending_e2e),
            "status": "complete" if not pending_e2e else "pending",
        },
        "metric_boundary": (
            "Retrieval and citation metrics measure agreement with the frozen "
            "Silver evidence benchmark, not expert factual correctness."
        ),
        "bootstrap": {
            "unit": "fault_class",
            "method": "paired percentile cluster bootstrap",
            "seed": seed,
            "requested_replicates": bootstrap_replicates,
            "confidence": confidence,
            "intervals": intervals,
            "paired_comparisons": paired_effects,
        },
        "method_specs": present_specs,
        "methods": summaries,
        "warnings": sorted(set(warnings)),
    }


def _latency_table_rows(
    specs: Sequence[Mapping[str, Any]], summaries: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        method = str(spec["id"])
        for stage, values in summaries[method]["latency"].items():
            rows.append(
                {
                    "method_id": method,
                    "method": spec["label"],
                    "budget_k": spec["budget"],
                    "group": spec["group"],
                    "stage": stage,
                    "samples": values["samples"],
                    "mean_ms": _round(values["mean_ms"], 3),
                    "p50_ms": _round(values["p50_ms"], 3),
                    "p95_ms": _round(values["p95_ms"], 3),
                }
            )
    return rows


def _latency_markdown(rows: Sequence[Mapping[str, Any]]) -> str:
    headers = ("Method", "K", "Stage", "N", "Mean ms", "p50 ms", "p95 ms")
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        values = (
            row["method"],
            row["budget_k"],
            row["stage"],
            row["samples"],
            row["mean_ms"],
            row["p50_ms"],
            row["p95_ms"],
        )
        lines.append("| " + " | ".join(str(value) for value in values) + " |")
    return "\n".join(lines) + "\n"


def _paired_effect_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    comparisons = report["bootstrap"].get("paired_comparisons", {})
    for comparison_id, comparison in comparisons.items():
        for metric, values in comparison["metrics"].items():
            rows.append(
                {
                    "comparison": comparison_id,
                    "reference": comparison["reference"],
                    "proposed": comparison["proposed"],
                    "metric": metric,
                    "delta_proposed_minus_reference": _round(
                        values["point_delta_proposed_minus_reference"]
                    ),
                    "ci_low": _round(values["ci_low"]),
                    "ci_high": _round(values["ci_high"]),
                    "favorable_direction": values["favorable_direction"],
                    "bootstrap_favorable_probability": _round(
                        values["bootstrap_favorable_probability"]
                    ),
                    "clusters": values["clusters"],
                    "replicates": values["replicates"],
                }
            )
    return rows


def _resolve_input(experiment: Path, explicit: str | None, candidates: Sequence[str]) -> Path:
    if explicit:
        return Path(explicit).resolve()
    for name in candidates:
        path = experiment / name
        if path.is_file():
            return path
    return experiment / candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", default=str(DEFAULT_EXPERIMENT))
    parser.add_argument("--generation-results")
    parser.add_argument("--retrieval-results")
    parser.add_argument("--retrieval-latency-results")
    parser.add_argument("--queries", default=str(DEFAULT_QUERIES))
    parser.add_argument("--output-dir")
    parser.add_argument("--bootstrap-replicates", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument(
        "--config",
        help="Optional protocol config used to register non-default scenario IDs.",
    )
    args = parser.parse_args()

    experiment = Path(args.experiment_dir).resolve()
    generation_path = _resolve_input(
        experiment, args.generation_results, ("generation_results.jsonl",)
    )
    retrieval_path = _resolve_input(
        experiment,
        args.retrieval_results,
        ("retrieval_results.jsonl", "retrieval_replay.jsonl"),
    )
    retrieval_latency_path = (
        Path(args.retrieval_latency_results).resolve()
        if args.retrieval_latency_results
        else experiment / "retrieval_latency" / "retrieval_latency_runs.jsonl"
    )
    queries_path = Path(args.queries).resolve()
    output = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else experiment / "paper_summary"
    )
    for path in (generation_path, retrieval_path, queries_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.retrieval_latency_results and not retrieval_latency_path.is_file():
        raise FileNotFoundError(retrieval_latency_path)
    if args.bootstrap_replicates < 0:
        raise ValueError("--bootstrap-replicates must be non-negative")
    if not 0.0 < args.confidence < 1.0:
        raise ValueError("--confidence must be between 0 and 1")

    method_specs = None
    paired_comparisons = None
    if args.config:
        config = json.loads(Path(args.config).resolve().read_text(encoding="utf-8"))
        method_specs = []
        for scenario in config["scenarios"]:
            components = scenario.get("components", {})
            method_specs.append(
                {
                    "id": str(scenario["id"]),
                    "label": str(scenario.get("display_name", scenario["id"])),
                    "budget": int(scenario["max_selected_evidence"]),
                    "group": str(scenario.get("comparison_tier", "configured")),
                    "role": bool(components.get("role_filter")),
                    "graph": bool(components.get("graph_expansion")),
                    "fault_affinity": bool(components.get("fault_affinity")),
                    "source_novelty": bool(components.get("source_family_novelty")),
                }
            )
        primary = config.get("primary_comparison", {})
        if primary.get("reference") and primary.get("proposed"):
            paired_comparisons = (
                (
                    "Configured_primary_comparison",
                    str(primary["reference"]),
                    str(primary["proposed"]),
                ),
            )

    report = summarize(
        queries=_read_jsonl(queries_path),
        retrieval_rows=_read_jsonl(retrieval_path),
        generation_rows=_read_jsonl(generation_path),
        retrieval_latency_rows=(
            _read_jsonl(retrieval_latency_path)
            if retrieval_latency_path.is_file()
            else []
        ),
        bootstrap_replicates=args.bootstrap_replicates,
        seed=args.seed,
        confidence=args.confidence,
        method_specs=method_specs,
        paired_comparisons=paired_comparisons,
    )
    report["inputs"] = {
        "queries": str(queries_path),
        "retrieval_results": str(retrieval_path),
        "generation_results": str(generation_path),
        "fresh_retrieval_latency": (
            str(retrieval_latency_path) if retrieval_latency_path.is_file() else None
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    specs = report["method_specs"]
    summaries = report["methods"]
    intervals = report["bootstrap"]["intervals"]
    main_specs = [spec for spec in specs if spec["group"] == "equal_budget_main"]
    secondary_specs = [
        spec for spec in specs if spec["group"] == "cross_budget_secondary"
    ]
    for stem, selected in (
        ("table_equal_budget_main", main_specs),
        ("table_cross_budget_secondary", secondary_specs),
    ):
        rows = [
            _csv_row(spec, summaries[spec["id"]], intervals.get(spec["id"], {}))
            for spec in selected
        ]
        _write_csv(output / f"{stem}.csv", rows)
        (output / f"{stem}.md").write_text(
            _markdown_rows(selected, summaries, intervals), encoding="utf-8"
        )

    latency_rows = _latency_table_rows(specs, summaries)
    _write_csv(output / "table_latency_breakdown.csv", latency_rows)
    (output / "table_latency_breakdown.md").write_text(
        _latency_markdown(latency_rows), encoding="utf-8"
    )
    paired_rows = _paired_effect_rows(report)
    _write_csv(output / "table_paired_cluster_effects.csv", paired_rows)
    (output / "table_paired_cluster_effects.md").write_text(
        "| Comparison | Metric | Delta | 95% CI | Favorable probability |\n"
        "|---|---|---:|---:|---:|\n"
        + "".join(
            f"| {row['comparison']} | {row['metric']} | "
            f"{row['delta_proposed_minus_reference']} | "
            f"[{row['ci_low']}, {row['ci_high']}] | "
            f"{row['bootstrap_favorable_probability']} |\n"
            for row in paired_rows
        ),
        encoding="utf-8",
    )
    print(
        f"[RP2 v6 summary] methods={len(specs)}, "
        f"bootstrap={args.bootstrap_replicates}, output={output}",
        flush=True,
    )
    for spec in specs:
        summary = summaries[spec["id"]]
        p95 = summary["latency"]["end_to_end"]["p95_ms"]
        p95_text = f"{float(p95):.1f}ms" if p95 is not None else "pending"
        print(
            f"  {spec['label']}: "
            f"Recall={_console_number(summary['retrieval_recall_macro'], 3)}, "
            f"Citation-F1={_console_number(summary['citation_f1_macro'], 3)}, "
            f"E2E-p95={p95_text}",
            flush=True,
        )
    if report["warnings"]:
        print("[RP2 v6 summary] warnings:", flush=True)
        for warning in report["warnings"]:
            print(f"  - {warning}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
