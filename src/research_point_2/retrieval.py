"""Low-latency evidence retrieval baselines and the budgeted selector."""

from __future__ import annotations

import math
import statistics
import time
from dataclasses import asdict, dataclass
from collections import defaultdict
from typing import Iterable

from .dataset import EvidenceCandidate, SilverQuery


def _char_bigrams(text: str) -> set[str]:
    compact = "".join(str(text or "").lower().split())
    if len(compact) < 2:
        return {compact} if compact else set()
    return {compact[index : index + 2] for index in range(len(compact) - 1)}


def lexical_similarity(left: str, right: str) -> float:
    a = _char_bigrams(left)
    b = _char_bigrams(right)
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


@dataclass(frozen=True)
class RetrievalBudget:
    max_scored_candidates: int = 64
    max_selected_evidence: int = 8
    max_per_source_family: int = 3
    deadline_ms: float | None = None
    minimum_marginal_gain: float = 0.0
    source_family_bonus: float = 0.12
    redundancy_penalty: float = 0.32


@dataclass(frozen=True)
class RankedEvidence:
    evidence_id: str
    score: float
    source_family_id: str
    claim_id: str
    role: str
    fault_match: bool
    role_match: bool


@dataclass(frozen=True)
class RetrievalResult:
    query_id: str
    method: str
    ranked: tuple[RankedEvidence, ...]
    elapsed_ms: float
    scored_candidates: int
    selected_evidence: int
    visited_evidence: int
    visited_nodes: int
    visited_edges: int
    generation_mode: str
    timed_out: bool
    early_stopped: bool

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["ranked"] = [asdict(item) for item in self.ranked]
        return payload


class RetrievalIndex:
    """Offline read-only indexes; construction time is excluded from online latency."""

    def __init__(self, candidates: Iterable[EvidenceCandidate]) -> None:
        self.candidates = tuple(candidates)
        self.by_id = {item.evidence_id: item for item in self.candidates}
        grouped: dict[str, list[EvidenceCandidate]] = defaultdict(list)
        token_postings: dict[tuple[str, str], set[str]] = defaultdict(set)
        global_token_postings: dict[str, set[str]] = defaultdict(set)
        self.entity_labels: dict[str, str] = {}
        adjacency: dict[str, set[str]] = defaultdict(set)
        incident: dict[str, set[str]] = defaultdict(set)
        for item in self.candidates:
            grouped[item.role].append(item)
            for token in _char_bigrams(item.searchable_text):
                token_postings[(item.role, token)].add(item.evidence_id)
                global_token_postings[token].add(item.evidence_id)
            self.entity_labels[item.head_entity_id] = item.head_label_zh
            self.entity_labels[item.tail_entity_id] = item.tail_label_zh
            if item.head_entity_id and item.tail_entity_id:
                adjacency[item.head_entity_id].add(item.tail_entity_id)
                adjacency[item.tail_entity_id].add(item.head_entity_id)
            incident[item.head_entity_id].add(item.evidence_id)
            incident[item.tail_entity_id].add(item.evidence_id)
        self.by_role = {
            key: tuple(sorted(rows, key=lambda item: item.evidence_id))
            for key, rows in grouped.items()
        }
        self.by_role_token = {key: frozenset(ids) for key, ids in token_postings.items()}
        self.global_token_postings = {
            key: frozenset(ids) for key, ids in global_token_postings.items()
        }
        self.adjacency = {key: frozenset(values) for key, values in adjacency.items()}
        self.incident_evidence = {key: frozenset(values) for key, values in incident.items()}

    def _allowed(self, query: SilverQuery) -> set[str] | None:
        return set(query.candidate_evidence_ids) if query.candidate_evidence_ids else None

    def _anchor_scores(self, query: SilverQuery, limit: int = 3) -> list[tuple[str, float]]:
        ranked = sorted(
            (
                (entity_id, lexical_similarity(query.fault_name_zh, label))
                for entity_id, label in self.entity_labels.items()
            ),
            key=lambda row: (row[1], row[0]),
            reverse=True,
        )
        positive = [row for row in ranked if row[1] > 0]
        return (positive or ranked)[:limit]

    def _fixed_hop_pool(self, query: SilverQuery, max_hops: int = 2) -> "CandidatePool":
        anchors = [entity_id for entity_id, _ in self._anchor_scores(query)]
        visited = set(anchors)
        frontier = set(anchors)
        edge_visits = 0
        for _ in range(max_hops):
            following: set[str] = set()
            for node in frontier:
                neighbors = self.adjacency.get(node, ())
                edge_visits += len(neighbors)
                following.update(neighbors)
            following -= visited
            visited.update(following)
            frontier = following
            if not frontier:
                break
        allowed = self._allowed(query)
        evidence_ids = {
            evidence_id
            for node in visited
            for evidence_id in self.incident_evidence.get(node, ())
        }
        rows = [
            self.by_id[evidence_id]
            for evidence_id in sorted(evidence_ids)
            if evidence_id in self.by_id
            and (allowed is None or evidence_id in allowed)
            and self.by_id[evidence_id].role == query.role
        ]
        return CandidatePool(tuple(rows), len(visited), edge_visits, "fixed_hop_2")

    def _adaptive_pool(self, query: SilverQuery) -> "CandidatePool":
        anchors = self._anchor_scores(query)
        total = sum(score for _, score in anchors) or 1.0
        restart = {entity_id: score / total for entity_id, score in anchors}
        energy = dict(restart)
        edge_visits = 0
        for _ in range(30):
            following: dict[str, float] = defaultdict(float)
            for node, value in energy.items():
                neighbors = self.adjacency.get(node, ())
                edge_visits += len(neighbors)
                if not neighbors:
                    following[node] += 0.85 * value
                    continue
                share = 0.85 * value / len(neighbors)
                for neighbor in neighbors:
                    following[neighbor] += share
            for node, value in restart.items():
                following[node] += 0.15 * value
            delta = sum(abs(following.get(node, 0.0) - energy.get(node, 0.0)) for node in set(following) | set(energy))
            energy = dict(following)
            if delta < 1e-6:
                break
        values = [value for value in energy.values() if value > 0]
        if values:
            ordered = sorted(values)
            percentile = ordered[max(0, math.ceil(0.70 * len(ordered)) - 1)]
            tau = max(statistics.fmean(values) + 0.5 * statistics.pstdev(values), percentile)
        else:
            tau = 0.0
        kept = {node for node, value in energy.items() if value >= tau}
        kept.update(entity_id for entity_id, _ in anchors)
        allowed = self._allowed(query)
        evidence_ids = {
            evidence_id
            for node in kept
            for evidence_id in self.incident_evidence.get(node, ())
        }
        rows = [
            self.by_id[evidence_id]
            for evidence_id in sorted(evidence_ids)
            if evidence_id in self.by_id
            and (allowed is None or evidence_id in allowed)
            and self.by_id[evidence_id].role == query.role
        ]
        if len(rows) < 4:
            fallback = list(self.by_role.get(query.role, ()))
            if allowed is not None:
                fallback = [item for item in fallback if item.evidence_id in allowed]
            known = {item.evidence_id for item in rows}
            rows.extend(
                [item for item in fallback if item.evidence_id not in known][
                    : max(0, 4 - len(rows))
                ]
            )
        return CandidatePool(tuple(rows), len(energy), edge_visits, "adaptive_energy_prune")

    def query_pool(self, query: SilverQuery, method: str) -> "CandidatePool":
        if method == "fixed_hop":
            return self._fixed_hop_pool(query)
        if method == "adaptive_prune":
            return self._adaptive_pool(query)
        allowed = self._allowed(query)
        if method in {"role_topk", "metapath_topk", "ours", "ours_no_source_family", "ours_no_redundancy", "ours_no_index"}:
            indexed = list(self.by_role.get(query.role, ()))
            if allowed is not None:
                indexed = [item for item in indexed if item.evidence_id in allowed]
            if method in {"metapath_topk", "ours", "ours_no_source_family", "ours_no_redundancy"} and indexed:
                query_tokens = _char_bigrams(query.question_zh)
                posting_hits: dict[str, int] = defaultdict(int)
                for token in query_tokens:
                    for evidence_id in self.by_role_token.get((query.role, token), ()):
                        if allowed is None or evidence_id in allowed:
                            posting_hits[evidence_id] += 1
                matched = [item for item in indexed if posting_hits.get(item.evidence_id, 0) > 0]
                if matched:
                    matched.sort(
                        key=lambda item: (posting_hits[item.evidence_id], item.final_confidence, item.evidence_id),
                        reverse=True,
                    )
                    return CandidatePool(tuple(matched), 0, 0, "inverted_metapath")
            if indexed:
                return CandidatePool(tuple(indexed), 0, 0, "role_gate")
        if method == "ours_no_role_gate":
            query_tokens = _char_bigrams(query.question_zh)
            hits: dict[str, int] = defaultdict(int)
            for token in query_tokens:
                for evidence_id in self.global_token_postings.get(token, ()):
                    if allowed is None or evidence_id in allowed:
                        hits[evidence_id] += 1
            matched = [self.by_id[evidence_id] for evidence_id in hits]
            matched.sort(key=lambda item: (hits[item.evidence_id], item.final_confidence, item.evidence_id), reverse=True)
            if matched:
                return CandidatePool(tuple(matched), 0, 0, "inverted_no_role_gate")
        if allowed is not None:
            rows = tuple(self.by_id[evidence_id] for evidence_id in query.candidate_evidence_ids if evidence_id in self.by_id)
            return CandidatePool(rows, 0, 0, "candidate_pool")
        return CandidatePool(self.candidates, 0, 0, "full_graph")


@dataclass(frozen=True)
class CandidatePool:
    items: tuple[EvidenceCandidate, ...]
    visited_nodes: int = 0
    visited_edges: int = 0
    generation_mode: str = "iterable"


def _base_score(query: SilverQuery, candidate: EvidenceCandidate, method: str) -> float:
    lexical = lexical_similarity(query.question_zh, candidate.searchable_text)
    if method == "lexical_full_scan":
        return lexical
    role_match = float(query.role == candidate.role)
    confidence = max(0.0, min(1.0, candidate.final_confidence))
    return 0.65 * lexical + 0.25 * role_match + 0.10 * confidence


def _candidate_overlap(left: EvidenceCandidate, right: EvidenceCandidate) -> float:
    if left.claim_id and left.claim_id == right.claim_id:
        return 1.0
    endpoint_left = {left.head_entity_id, left.tail_entity_id} - {""}
    endpoint_right = {right.head_entity_id, right.tail_entity_id} - {""}
    endpoint_overlap = len(endpoint_left & endpoint_right) / max(1, len(endpoint_left | endpoint_right))
    return endpoint_overlap


def _pool_for_query(
    query: SilverQuery,
    candidates: Iterable[EvidenceCandidate] | RetrievalIndex,
    method: str,
) -> CandidatePool:
    if isinstance(candidates, RetrievalIndex):
        return candidates.query_pool(query, method)
    candidate_list = list(candidates)
    if query.candidate_evidence_ids:
        allowed = set(query.candidate_evidence_ids)
        candidate_list = [item for item in candidate_list if item.evidence_id in allowed]
    if method in {
        "role_topk", "metapath_topk", "ours", "ours_no_source_family",
        "ours_no_redundancy", "ours_no_index",
    }:
        gated = [
            item
            for item in candidate_list
            if query.role == item.role
        ]
        if gated:
            return CandidatePool(tuple(gated), generation_mode="role_gate")
    return CandidatePool(tuple(candidate_list))


def retrieve(
    query: SilverQuery,
    candidates: Iterable[EvidenceCandidate] | RetrievalIndex,
    *,
    method: str,
    budget: RetrievalBudget | None = None,
) -> RetrievalResult:
    supported = {
        "lexical_full_scan", "role_topk", "metapath_topk", "fixed_hop",
        "adaptive_prune", "ours", "ours_no_source_family",
        "ours_no_redundancy", "ours_no_index", "ours_no_role_gate",
    }
    if method not in supported:
        raise ValueError(f"unknown retrieval method: {method}")
    budget = budget or RetrievalBudget()
    start = time.perf_counter_ns()
    deadline_ns = (
        start + int(budget.deadline_ms * 1_000_000)
        if budget.deadline_ms is not None
        else None
    )
    candidate_pool = _pool_for_query(query, candidates, method)
    pool = list(candidate_pool.items)
    scored: list[tuple[EvidenceCandidate, float]] = []
    timed_out = False
    for item in pool:
        if len(scored) >= budget.max_scored_candidates:
            break
        if deadline_ns is not None and time.perf_counter_ns() >= deadline_ns:
            timed_out = True
            break
        scored.append((item, _base_score(query, item, method)))
    scored.sort(key=lambda row: (row[1], row[0].final_confidence, row[0].evidence_id), reverse=True)

    is_ours = method.startswith("ours")
    if not is_ours:
        chosen = scored[: budget.max_selected_evidence]
        ranked = tuple(
            RankedEvidence(
                evidence_id=item.evidence_id,
                score=score,
                source_family_id=item.source_family_id,
                claim_id=item.claim_id,
                role=item.role,
                fault_match=query.fault_id in item.fault_class_ids,
                role_match=query.role == item.role,
            )
            for item, score in chosen
        )
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        return RetrievalResult(
            query_id=query.query_id,
            method=method,
            ranked=ranked,
            elapsed_ms=elapsed_ms,
            scored_candidates=len(scored),
            selected_evidence=len(ranked),
            visited_evidence=len(pool),
            visited_nodes=candidate_pool.visited_nodes,
            visited_edges=candidate_pool.visited_edges,
            generation_mode=candidate_pool.generation_mode,
            timed_out=timed_out,
            early_stopped=len(chosen) < len(scored),
        )

    remaining = scored[:]
    selected: list[tuple[EvidenceCandidate, float]] = []
    family_counts: dict[str, int] = {}
    early_stopped = False
    while remaining and len(selected) < budget.max_selected_evidence:
        if deadline_ns is not None and time.perf_counter_ns() >= deadline_ns:
            timed_out = True
            early_stopped = True
            break
        best_index = -1
        best_gain = -math.inf
        for index, (item, base_score) in enumerate(remaining):
            family = item.source_family_id or "UNKNOWN"
            apply_family_cap = method != "ours_no_source_family"
            if apply_family_cap and family_counts.get(family, 0) >= budget.max_per_source_family:
                continue
            novelty = 1.0 if family not in family_counts and method != "ours_no_source_family" else 0.0
            redundancy = max(
                (_candidate_overlap(item, chosen) for chosen, _ in selected),
                default=0.0,
            )
            redundancy_weight = (
                0.0 if method == "ours_no_redundancy" else budget.redundancy_penalty
            )
            gain = base_score + budget.source_family_bonus * novelty - redundancy_weight * redundancy
            if gain > best_gain:
                best_gain = gain
                best_index = index
        if best_index < 0 or best_gain < budget.minimum_marginal_gain:
            early_stopped = True
            break
        item, _ = remaining.pop(best_index)
        selected.append((item, best_gain))
        family = item.source_family_id or "UNKNOWN"
        family_counts[family] = family_counts.get(family, 0) + 1

    ranked = tuple(
        RankedEvidence(
            evidence_id=item.evidence_id,
            score=score,
            source_family_id=item.source_family_id,
            claim_id=item.claim_id,
            role=item.role,
            fault_match=query.fault_id in item.fault_class_ids,
            role_match=query.role == item.role,
        )
        for item, score in selected
    )
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    return RetrievalResult(
        query_id=query.query_id,
        method=method,
        ranked=ranked,
        elapsed_ms=elapsed_ms,
        scored_candidates=len(scored),
        selected_evidence=len(ranked),
        visited_evidence=len(pool),
        visited_nodes=candidate_pool.visited_nodes,
        visited_edges=candidate_pool.visited_edges,
        generation_mode=candidate_pool.generation_mode,
        timed_out=timed_out,
        early_stopped=early_stopped,
    )
