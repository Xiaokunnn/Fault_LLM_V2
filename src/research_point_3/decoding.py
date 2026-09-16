"""Fail-closed decoding for the RP3 evidence controller.

Decoding never fabricates an evidence pointer.  Candidate IDs must exist in the
frozen compact memory and be marked available by the intervention mask before a
pointer can reach the diagnosis-card renderer or a downstream language model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet, Sequence

from .contracts import CARD_SLOT_ROLES, CardFieldState, DiagnosticRole, RouteAction
from .model import (
    CARD_FIELD_STATES,
    ROUTE_ACTIONS,
    EvidenceControllerOutput,
    require_torch,
)

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None


@dataclass(frozen=True)
class DecodedCardField:
    role: DiagnosticRole
    state: CardFieldState
    cardinality: int


@dataclass(frozen=True)
class DecodedEvidenceDecision:
    """Safe symbolic decision passed to evidence resolution and rendering."""

    selected_evidence_ids: tuple[str, ...]
    direct_support_evidence_ids: tuple[str, ...]
    ranked_evidence_ids: tuple[str, ...]
    # Scores remain aligned with the original candidate-ID order.  The separate
    # ranked_evidence_ids permutation carries the predicted ordering.
    candidate_order_rank_scores: tuple[float, ...]
    support_probabilities: tuple[float, ...]
    card_fields: tuple[DecodedCardField, ...]
    route_action: RouteAction
    route_confidence: float
    rejected_evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


def _candidate_rows(
    candidate_evidence_ids: Sequence[Sequence[str]] | Sequence[str],
    batch_size: int,
) -> tuple[tuple[str, ...], ...]:
    if batch_size == 1 and (
        not candidate_evidence_ids
        or isinstance(candidate_evidence_ids[0], str)  # type: ignore[index]
    ):
        return (tuple(str(value) for value in candidate_evidence_ids),)  # type: ignore[arg-type]
    rows = tuple(tuple(str(value) for value in row) for row in candidate_evidence_ids)  # type: ignore[arg-type]
    if len(rows) != batch_size:
        raise ValueError("candidate_evidence_ids must provide one row per batch item")
    return rows


def _safe_card_fields(
    output: EvidenceControllerOutput,
    batch_index: int,
    direct_count_by_role: dict[DiagnosticRole, int],
) -> tuple[DecodedCardField, ...]:
    fields: list[DecodedCardField] = []
    state_indices = output.field_state_logits[batch_index].argmax(dim=-1).tolist()
    cardinalities = output.cardinality_logits[batch_index].argmax(dim=-1).tolist()
    for field_index, role in enumerate(CARD_SLOT_ROLES):
        state = CardFieldState(CARD_FIELD_STATES[int(state_indices[field_index])])
        cardinality = int(cardinalities[field_index])
        # Constrained decoding is the only place that may lower an impossible
        # field prediction.  The renderer later consumes this STOP/cardinality
        # plan verbatim and rejects any mismatch.
        if state in {
            CardFieldState.INSUFFICIENT,
            CardFieldState.NOT_APPLICABLE,
        }:
            cardinality = 0
        else:
            cardinality = min(cardinality, direct_count_by_role.get(role, 0))
            if cardinality == 0 or (
                state == CardFieldState.CONFLICT and cardinality < 2
            ):
                state = CardFieldState.INSUFFICIENT
                cardinality = 0
        fields.append(
            DecodedCardField(role=role, state=state, cardinality=cardinality)
        )
    return tuple(fields)


def decode_evidence_controller_output(
    output: EvidenceControllerOutput,
    candidate_evidence_ids: Sequence[Sequence[str]] | Sequence[str],
    candidate_roles: Sequence[Sequence[DiagnosticRole | str]]
    | Sequence[DiagnosticRole | str],
    known_evidence_ids: AbstractSet[str],
    *,
    selection_budget: int,
    support_threshold: float = 0.5,
    minimum_route_confidence: float = 0.0,
) -> tuple[DecodedEvidenceDecision, ...]:
    """Decode a batch while rejecting unknown and unavailable pointers.

    The function is deliberately conservative:

    * duplicate, blank, unknown, or unavailable IDs are never selected;
    * only candidates predicted as directly supported can be selected;
    * field-state/cardinality heads impose per-role STOP quotas and context
      candidates can never become diagnosis-card pointers;
    * an ``answer`` prediction is downgraded to ``fallback`` when safe pointers
      are absent, and to ``abstain`` when no known available candidate exists;
    * low route confidence also prevents an edge answer.
    """

    require_torch()
    if selection_budget < 1:
        raise ValueError("selection_budget must be >= 1")
    if not 0.0 <= support_threshold <= 1.0:
        raise ValueError("support_threshold must be in [0, 1]")
    if not 0.0 <= minimum_route_confidence <= 1.0:
        raise ValueError("minimum_route_confidence must be in [0, 1]")

    tensors = (
        output.rank_logits,
        output.support_logits,
        output.field_state_logits,
        output.cardinality_logits,
        output.route_logits,
        output.availability_mask,
    )
    batch_size = output.rank_logits.shape[0]
    if output.rank_logits.ndim != 2:
        raise ValueError("rank_logits must have shape [batch, candidates]")
    if output.support_logits.shape != output.rank_logits.shape:
        raise ValueError("support_logits must align with rank_logits")
    if output.availability_mask.shape != output.rank_logits.shape:
        raise ValueError("availability_mask must align with rank_logits")
    if any(tensor.shape[0] != batch_size for tensor in tensors):
        raise ValueError("all output heads must have the same batch dimension")
    if output.field_state_logits.shape[1] != len(CARD_SLOT_ROLES):
        raise ValueError("field_state_logits do not match the frozen card schema")
    if output.cardinality_logits.shape[1] != len(CARD_SLOT_ROLES):
        raise ValueError("cardinality_logits do not match the frozen card schema")
    if output.route_logits.shape[-1] != len(ROUTE_ACTIONS):
        raise ValueError("route_logits do not match RouteAction")

    rows = _candidate_rows(candidate_evidence_ids, batch_size)
    role_rows = _candidate_rows(candidate_roles, batch_size)
    candidate_count = output.rank_logits.shape[1]
    if any(len(row) != candidate_count for row in rows):
        raise ValueError("every candidate ID row must align with the candidate logits")
    if any(len(row) != candidate_count for row in role_rows):
        raise ValueError("every candidate role row must align with the candidate logits")
    known = {str(value) for value in known_evidence_ids if str(value)}

    decoded: list[DecodedEvidenceDecision] = []
    for batch_index, ids in enumerate(rows):
        try:
            roles = tuple(DiagnosticRole(value) for value in role_rows[batch_index])
        except ValueError as exc:
            raise ValueError("candidate_roles contains an unknown diagnostic role") from exc
        mask = output.availability_mask[batch_index].to(dtype=torch.bool).tolist()
        support_probabilities = torch.sigmoid(
            output.support_logits[batch_index]
        ).tolist()
        rank_order = output.rank_logits[batch_index].argsort(descending=True).tolist()

        rejected: list[str] = []
        safe_available: set[int] = set()
        seen: set[str] = set()
        for index, evidence_id in enumerate(ids):
            if (
                not evidence_id
                or evidence_id in seen
                or evidence_id not in known
                or not bool(mask[index])
            ):
                if evidence_id:
                    rejected.append(evidence_id)
                continue
            seen.add(evidence_id)
            safe_available.add(index)

        direct_indices = {
            index
            for index in safe_available
            if float(support_probabilities[index]) >= support_threshold
        }
        direct_count_by_role = {
            role: sum(
                index in direct_indices and roles[index] == role
                for index in range(len(ids))
            )
            for role in CARD_SLOT_ROLES
        }
        fields = _safe_card_fields(
            output,
            batch_index,
            direct_count_by_role=direct_count_by_role,
        )
        remaining_by_role = {field.role: field.cardinality for field in fields}
        selected_indices: list[int] = []
        for index in rank_order:
            if len(selected_indices) >= selection_budget:
                break
            role = roles[index]
            if (
                index in direct_indices
                and role in CARD_SLOT_ROLES
                and remaining_by_role[role] > 0
            ):
                selected_indices.append(index)
                remaining_by_role[role] -= 1
        actual_by_role = {
            role: sum(roles[index] == role for index in selected_indices)
            for role in CARD_SLOT_ROLES
        }
        # A total budget can truncate lower-ranked field quotas.  Preserve STOP
        # semantics by lowering the symbolic plan to the actual safe pointers.
        fields = tuple(
            DecodedCardField(
                role=field.role,
                state=(
                    field.state
                    if actual_by_role[field.role] == field.cardinality
                    else (
                        CardFieldState.CONFLICT
                        if field.state == CardFieldState.CONFLICT
                        and actual_by_role[field.role] >= 2
                        else CardFieldState.SUPPORTED
                        if actual_by_role[field.role] >= 1
                        else CardFieldState.INSUFFICIENT
                    )
                ),
                cardinality=actual_by_role[field.role],
            )
            for field in fields
        )
        selected_ids = tuple(ids[index] for index in selected_indices)
        direct_ids = tuple(
            ids[index]
            for index in rank_order
            if index in direct_indices
        )

        route_probability = torch.softmax(output.route_logits[batch_index], dim=-1)
        route_index = int(route_probability.argmax().item())
        route = RouteAction(ROUTE_ACTIONS[route_index])
        confidence = float(route_probability[route_index].item())
        reasons: list[str] = []
        if rejected:
            reasons.append("unknown_duplicate_or_unavailable_pointer_rejected")
        if len(selected_ids) < selection_budget:
            reasons.append("active_underfill")
        if not safe_available:
            route = RouteAction.ABSTAIN
            reasons.append("no_known_available_evidence")
        elif route == RouteAction.ANSWER and not selected_ids:
            route = RouteAction.FALLBACK
            reasons.append("answer_blocked_without_direct_support")
        elif route == RouteAction.ANSWER and confidence < minimum_route_confidence:
            route = RouteAction.FALLBACK
            reasons.append("answer_blocked_by_route_confidence")
        if not reasons:
            reasons.append("decoded_with_evidence_contract")

        decoded.append(
            DecodedEvidenceDecision(
                selected_evidence_ids=selected_ids,
                direct_support_evidence_ids=direct_ids,
                ranked_evidence_ids=tuple(ids[index] for index in rank_order),
                candidate_order_rank_scores=tuple(
                    float(output.rank_logits[batch_index, index].item())
                    for index in range(len(ids))
                ),
                support_probabilities=tuple(
                    float(value) for value in support_probabilities
                ),
                card_fields=fields,
                route_action=route,
                route_confidence=confidence,
                rejected_evidence_ids=tuple(dict.fromkeys(rejected)),
                reason_codes=tuple(reasons),
            )
        )
    return tuple(decoded)


__all__ = [
    "DecodedCardField",
    "DecodedEvidenceDecision",
    "decode_evidence_controller_output",
]
