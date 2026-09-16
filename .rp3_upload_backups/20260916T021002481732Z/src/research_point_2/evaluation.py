"""Evaluation helpers for the development Silver evidence benchmark."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from itertools import combinations
from typing import Iterable

from .dataset import EvidenceCandidate, SilverQuery
from .retrieval import RetrievalResult


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


def evaluate_results(
    queries: Iterable[SilverQuery],
    candidates: Iterable[EvidenceCandidate],
    results: Iterable[RetrievalResult],
) -> dict:
    query_by_id = {query.query_id: query for query in queries}
    candidate_by_id = {item.evidence_id: item for item in candidates}
    grouped: dict[str, list[RetrievalResult]] = defaultdict(list)
    for result in results:
        grouped[result.method].append(result)

    methods: dict[str, dict] = {}
    for method, rows in sorted(grouped.items()):
        recalls: list[float] = []
        reciprocal_ranks: list[float] = []
        ndcgs: list[float] = []
        family_coverages: list[int] = []
        redundancies: list[float] = []
        endpoint_overlaps: list[float] = []
        latencies: list[float] = []
        scored_counts: list[int] = []
        selected_counts: list[int] = []
        visited_evidence_counts: list[int] = []
        visited_node_counts: list[int] = []
        visited_edge_counts: list[int] = []
        timeouts = 0
        first_by_query: dict[str, RetrievalResult] = {}
        for row in rows:
            first_by_query.setdefault(row.query_id, row)
            latencies.append(row.elapsed_ms)
            scored_counts.append(row.scored_candidates)
            selected_counts.append(row.selected_evidence)
            visited_evidence_counts.append(row.visited_evidence)
            visited_node_counts.append(row.visited_nodes)
            visited_edge_counts.append(row.visited_edges)
            timeouts += int(row.timed_out)
        for row in first_by_query.values():
            query = query_by_id[row.query_id]
            relevant = set(query.relevant_evidence_ids)
            if not relevant:
                continue
            ranked_ids = [item.evidence_id for item in row.ranked]
            hits = [1 if evidence_id in relevant else 0 for evidence_id in ranked_ids]
            recalls.append(sum(hits) / len(relevant))
            first_hit = next((index for index, hit in enumerate(hits, start=1) if hit), None)
            reciprocal_ranks.append(1.0 / first_hit if first_hit else 0.0)
            dcg = sum(hit / math.log2(index + 1) for index, hit in enumerate(hits, start=1))
            ideal_hits = min(len(relevant), len(ranked_ids))
            idcg = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
            ndcgs.append(dcg / idcg if idcg else 0.0)
            families = {
                candidate_by_id[evidence_id].source_family_id
                for evidence_id in ranked_ids
                if evidence_id in candidate_by_id
            }
            family_coverages.append(len(families))
            claims = [
                candidate_by_id[evidence_id].claim_id
                for evidence_id in ranked_ids
                if evidence_id in candidate_by_id
            ]
            redundancies.append(1.0 - len(set(claims)) / len(claims) if claims else 0.0)
            selected_candidates = [
                candidate_by_id[evidence_id]
                for evidence_id in ranked_ids
                if evidence_id in candidate_by_id
            ]
            pair_overlaps = []
            for left, right in combinations(selected_candidates, 2):
                left_endpoints = {left.head_entity_id, left.tail_entity_id} - {""}
                right_endpoints = {right.head_entity_id, right.tail_entity_id} - {""}
                pair_overlaps.append(
                    len(left_endpoints & right_endpoints)
                    / max(1, len(left_endpoints | right_endpoints))
                )
            endpoint_overlaps.append(
                statistics.fmean(pair_overlaps) if pair_overlaps else 0.0
            )
        methods[method] = {
            "evaluated_answerable_queries": len(recalls),
            "latency_samples": len(latencies),
            "recall_at_budget_macro": statistics.fmean(recalls) if recalls else 0.0,
            "mrr": statistics.fmean(reciprocal_ranks) if reciprocal_ranks else 0.0,
            "ndcg_at_budget_macro": statistics.fmean(ndcgs) if ndcgs else 0.0,
            "mean_source_family_coverage": statistics.fmean(family_coverages) if family_coverages else 0.0,
            "mean_exact_claim_redundancy": statistics.fmean(redundancies) if redundancies else 0.0,
            "mean_pairwise_endpoint_overlap": statistics.fmean(endpoint_overlaps) if endpoint_overlaps else 0.0,
            "latency_ms_p50": _percentile(latencies, 0.50),
            "latency_ms_p95": _percentile(latencies, 0.95),
            "mean_scored_candidates": statistics.fmean(scored_counts) if scored_counts else 0.0,
            "mean_selected_evidence": statistics.fmean(selected_counts) if selected_counts else 0.0,
            "mean_visited_evidence": statistics.fmean(visited_evidence_counts) if visited_evidence_counts else 0.0,
            "mean_visited_nodes": statistics.fmean(visited_node_counts) if visited_node_counts else 0.0,
            "mean_visited_edges": statistics.fmean(visited_edge_counts) if visited_edge_counts else 0.0,
            "timeout_count": timeouts,
        }
    return {
        "label_policy": "Silver only; never Gold",
        "human_expert_reviewed": False,
        "benchmark_scope": "development_only_not_held_out",
        "methods": methods,
    }
