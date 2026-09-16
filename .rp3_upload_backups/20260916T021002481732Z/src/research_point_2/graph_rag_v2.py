"""Dense-anchor GraphRAG v2 baselines and source-aware evidence selection."""

from __future__ import annotations

import math
import statistics
import time
from collections import defaultdict

from .dataset import EvidenceCandidate, SilverQuery
from .dense_index import DenseEvidenceIndex, Encoder
from .retrieval import (
    RankedEvidence,
    RetrievalBudget,
    RetrievalIndex,
    RetrievalResult,
    _candidate_overlap,
    lexical_similarity,
)


SUPPORTED = {
    "dense_topk",
    "dense_fixed_hop",
    "dense_adaptive",
    "dense_metapath",
    "dense_ours",
    "dense_ours_no_graph",
    "dense_ours_no_source_family",
    "dense_ours_no_redundancy",
    "dense_ours_v4",
    "dense_ours_v4_no_graph",
}

NO_GRAPH_OURS_METHODS = {"dense_ours_no_graph", "dense_ours_v4_no_graph"}
FAULT_AFFINITY_METHODS = {"dense_ours_v4", "dense_ours_v4_no_graph"}


def _graph_pool(index: RetrievalIndex, seeds: list[tuple[str, float]], method: str, hops: int) -> tuple[set[str], int, int]:
    node_energy: dict[str, float] = defaultdict(float)
    for evidence_id, score in seeds:
        item = index.by_id[evidence_id]
        node_energy[item.head_entity_id] += max(score, 0.0)
        node_energy[item.tail_entity_id] += max(score, 0.0)
    if method == "dense_fixed_hop":
        visited, frontier, edges = set(node_energy), set(node_energy), 0
        for _ in range(hops):
            following = set()
            for node in frontier:
                neighbors = index.adjacency.get(node, ())
                edges += len(neighbors)
                following.update(neighbors)
            following -= visited
            visited.update(following)
            frontier = following
        evidence = {eid for node in visited for eid in index.incident_evidence.get(node, ())}
        return evidence, len(visited), edges

    total = sum(node_energy.values()) or 1.0
    restart = {node: value / total for node, value in node_energy.items()}
    energy, edges = dict(restart), 0
    for _ in range(30):
        following: dict[str, float] = defaultdict(float)
        for node, value in energy.items():
            neighbors = index.adjacency.get(node, ())
            edges += len(neighbors)
            if neighbors:
                share = 0.85 * value / len(neighbors)
                for neighbor in neighbors:
                    following[neighbor] += share
        for node, value in restart.items():
            following[node] += 0.15 * value
        delta = sum(abs(following.get(node, 0) - energy.get(node, 0)) for node in set(following) | set(energy))
        energy = dict(following)
        if delta < 1e-6:
            break
    values = list(energy.values())
    tau = statistics.fmean(values) + 0.5 * statistics.pstdev(values) if values else 0.0
    kept = {node for node, value in energy.items() if value >= tau} | set(restart)
    evidence = {eid for node in kept for eid in index.incident_evidence.get(node, ())}
    return evidence, len(energy), edges


def _budgeted_hop_pool(
    index: RetrievalIndex,
    seeds: list[tuple[str, float]],
    *,
    hops: int,
    decay: float,
) -> tuple[set[str], dict[str, float], int, int]:
    """Expand dense anchors over the graph and retain auditable proximity scores."""

    if hops <= 0:
        seed_scores = {evidence_id: max(float(score), 0.0) for evidence_id, score in seeds}
        return set(seed_scores), seed_scores, 0, 0
    node_scores: dict[str, float] = defaultdict(float)
    frontier: dict[str, float] = {}
    for evidence_id, score in seeds:
        item = index.by_id[evidence_id]
        value = max(float(score), 0.0)
        for node in (item.head_entity_id, item.tail_entity_id):
            if node:
                node_scores[node] = max(node_scores[node], value)
                frontier[node] = max(frontier.get(node, 0.0), value)
    visited = set(frontier)
    edge_visits = 0
    for _ in range(max(0, hops)):
        following: dict[str, float] = {}
        for node, score in frontier.items():
            neighbors = index.adjacency.get(node, ())
            edge_visits += len(neighbors)
            propagated = score * decay
            for neighbor in neighbors:
                if propagated > node_scores.get(neighbor, -math.inf):
                    node_scores[neighbor] = propagated
                if neighbor not in visited:
                    following[neighbor] = max(following.get(neighbor, 0.0), propagated)
        if not following:
            break
        visited.update(following)
        frontier = following
    evidence_ids = {
        evidence_id
        for node in visited
        for evidence_id in index.incident_evidence.get(node, ())
    }
    evidence_scores = {
        evidence_id: max(
            node_scores.get(index.by_id[evidence_id].head_entity_id, 0.0),
            node_scores.get(index.by_id[evidence_id].tail_entity_id, 0.0),
        )
        for evidence_id in evidence_ids
        if evidence_id in index.by_id
    }
    return evidence_ids, evidence_scores, len(visited), edge_visits


def retrieve_dense_graph(
    query: SilverQuery,
    candidates: list[EvidenceCandidate],
    graph_index: RetrievalIndex,
    dense_index: DenseEvidenceIndex,
    encoder: Encoder,
    *,
    method: str,
    budget: RetrievalBudget,
    dense_top_n: int = 64,
    anchor_evidence_count: int = 8,
    fixed_hops: int = 2,
    ours_graph_hops: int = 1,
    ours_graph_decay: float = 0.70,
    graph_score_weight: float = 0.12,
    fault_affinity_weight: float = 0.0,
    fault_affinity_floor: float = 0.0,
) -> RetrievalResult:
    if method not in SUPPORTED:
        raise ValueError(f"unknown dense GraphRAG method: {method}")
    start = time.perf_counter_ns()
    hits = dense_index.search(query.question_zh, encoder, top_n=dense_top_n)
    score_by_id = {hit.evidence_id: hit.score for hit in hits}
    visited_nodes = visited_edges = 0
    graph_score_by_id: dict[str, float] = {}
    if method in {"dense_fixed_hop", "dense_adaptive"}:
        evidence_ids, visited_nodes, visited_edges = _graph_pool(
            graph_index,
            [(hit.evidence_id, hit.score) for hit in hits[:anchor_evidence_count]],
            method,
            fixed_hops,
        )
        pool = [graph_index.by_id[eid] for eid in evidence_ids if eid in graph_index.by_id]
        generation_mode = method
    elif method.startswith("dense_ours") and method not in NO_GRAPH_OURS_METHODS:
        evidence_ids, graph_score_by_id, visited_nodes, visited_edges = _budgeted_hop_pool(
            graph_index,
            [(hit.evidence_id, hit.score) for hit in hits[:anchor_evidence_count]],
            hops=ours_graph_hops,
            decay=ours_graph_decay,
        )
        evidence_ids.update(score_by_id)
        pool = [graph_index.by_id[eid] for eid in evidence_ids if eid in graph_index.by_id]
        generation_mode = f"dense_budgeted_graph_h{ours_graph_hops}"
    else:
        pool = [graph_index.by_id[hit.evidence_id] for hit in hits if hit.evidence_id in graph_index.by_id]
        generation_mode = (
            "dense_no_graph_same_constraints"
            if method == "dense_ours_v4_no_graph"
            else "dense_full_graph"
        )
    if method in {
        "dense_metapath",
        "dense_fixed_hop",
        "dense_adaptive",
        "dense_ours",
        "dense_ours_no_graph",
        "dense_ours_no_source_family",
        "dense_ours_no_redundancy",
        "dense_ours_v4",
        "dense_ours_v4_no_graph",
    }:
        role_rows = [item for item in pool if item.role == query.role]
        if role_rows:
            pool = role_rows
    if method in FAULT_AFFINITY_METHODS and fault_affinity_floor > 0.0:
        pool = [
            item
            for item in pool
            if max(
                lexical_similarity(query.fault_name_zh, item.head_label_zh),
                lexical_similarity(query.fault_name_zh, item.tail_label_zh),
            ) >= fault_affinity_floor
        ]
        generation_mode += f"_visible_fault_floor_{fault_affinity_floor:g}"
    scored = sorted(
        (
            (
                item,
                score_by_id.get(item.evidence_id, 0.0)
                + graph_score_weight * graph_score_by_id.get(item.evidence_id, 0.0)
                + 0.10 * item.final_confidence
                + (
                    fault_affinity_weight
                    * max(
                        lexical_similarity(query.fault_name_zh, item.head_label_zh),
                        lexical_similarity(query.fault_name_zh, item.tail_label_zh),
                    )
                    if method in FAULT_AFFINITY_METHODS
                    else 0.0
                ),
            )
            for item in pool
        ),
        key=lambda row: (row[1], row[0].evidence_id),
        reverse=True,
    )[: budget.max_scored_candidates]
    if not method.startswith("dense_ours"):
        selected = scored[: budget.max_selected_evidence]
    else:
        selected, remaining, family_counts = [], list(scored), {}
        while remaining and len(selected) < budget.max_selected_evidence:
            best_index, best_gain = -1, -math.inf
            for position, (item, base) in enumerate(remaining):
                family = item.source_family_id or "UNKNOWN"
                use_source_family = method != "dense_ours_no_source_family"
                if use_source_family and family_counts.get(family, 0) >= budget.max_per_source_family:
                    continue
                novelty = 1.0 if use_source_family and family not in family_counts else 0.0
                redundancy = max((_candidate_overlap(item, old) for old, _ in selected), default=0.0)
                redundancy_weight = (
                    0.0 if method == "dense_ours_no_redundancy" else budget.redundancy_penalty
                )
                gain = base + budget.source_family_bonus * novelty - redundancy_weight * redundancy
                if gain > best_gain:
                    best_index, best_gain = position, gain
            if best_index < 0:
                break
            item, _ = remaining.pop(best_index)
            selected.append((item, best_gain))
            family = item.source_family_id or "UNKNOWN"
            family_counts[family] = family_counts.get(family, 0) + 1
    ranked = tuple(
        RankedEvidence(
            evidence_id=item.evidence_id,
            score=float(score),
            source_family_id=item.source_family_id,
            claim_id=item.claim_id,
            role=item.role,
            fault_match=query.fault_id in item.fault_class_ids,
            role_match=query.role == item.role,
        )
        for item, score in selected
    )
    elapsed = (time.perf_counter_ns() - start) / 1_000_000
    return RetrievalResult(
        query_id=query.query_id,
        method=method,
        ranked=ranked,
        elapsed_ms=elapsed,
        scored_candidates=len(scored),
        selected_evidence=len(ranked),
        visited_evidence=len(pool),
        visited_nodes=visited_nodes,
        visited_edges=visited_edges,
        generation_mode=generation_mode,
        timed_out=False,
        early_stopped=len(ranked) < len(scored),
    )
