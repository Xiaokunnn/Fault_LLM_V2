"""Dense-anchor GraphRAG v2 baselines and source-aware evidence selection."""

from __future__ import annotations

import math
import statistics
import time
from collections import defaultdict

from .dataset import EvidenceCandidate, SilverQuery
from .dense_index import DenseEvidenceIndex, Encoder
from .retrieval import RankedEvidence, RetrievalBudget, RetrievalIndex, RetrievalResult, _candidate_overlap


SUPPORTED = {"dense_topk", "dense_fixed_hop", "dense_adaptive", "dense_metapath", "dense_ours"}


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
) -> RetrievalResult:
    if method not in SUPPORTED:
        raise ValueError(f"unknown dense GraphRAG method: {method}")
    start = time.perf_counter_ns()
    hits = dense_index.search(query.question_zh, encoder, top_n=dense_top_n)
    score_by_id = {hit.evidence_id: hit.score for hit in hits}
    visited_nodes = visited_edges = 0
    if method in {"dense_fixed_hop", "dense_adaptive"}:
        evidence_ids, visited_nodes, visited_edges = _graph_pool(
            graph_index,
            [(hit.evidence_id, hit.score) for hit in hits[:anchor_evidence_count]],
            method,
            fixed_hops,
        )
        pool = [graph_index.by_id[eid] for eid in evidence_ids if eid in graph_index.by_id]
        generation_mode = method
    else:
        pool = [graph_index.by_id[hit.evidence_id] for hit in hits if hit.evidence_id in graph_index.by_id]
        generation_mode = "dense_full_graph"
    if method in {"dense_metapath", "dense_ours", "dense_fixed_hop", "dense_adaptive"}:
        role_rows = [item for item in pool if item.role == query.role]
        if role_rows:
            pool = role_rows
    scored = sorted(
        ((item, score_by_id.get(item.evidence_id, 0.0) + 0.10 * item.final_confidence) for item in pool),
        key=lambda row: (row[1], row[0].evidence_id),
        reverse=True,
    )[: budget.max_scored_candidates]
    if method != "dense_ours":
        selected = scored[: budget.max_selected_evidence]
    else:
        selected, remaining, family_counts = [], list(scored), {}
        while remaining and len(selected) < budget.max_selected_evidence:
            best_index, best_gain = -1, -math.inf
            for position, (item, base) in enumerate(remaining):
                family = item.source_family_id or "UNKNOWN"
                if family_counts.get(family, 0) >= budget.max_per_source_family:
                    continue
                novelty = 1.0 if family not in family_counts else 0.0
                redundancy = max((_candidate_overlap(item, old) for old, _ in selected), default=0.0)
                gain = base + budget.source_family_bonus * novelty - budget.redundancy_penalty * redundancy
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
