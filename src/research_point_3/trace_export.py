"""Adapters for exporting complete RP2 teacher decisions into RP3 traces.

The RP2 v6 archived replay contains only the final top-three rows.  It is useful for
compatibility checks but is deliberately rejected as rank-distillation input.  A
model-capable machine must first export the full top-32 candidate list and the final
two-stage support mask on the frozen strict-208 teacher.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .contracts import (
    CARD_SLOT_ROLES,
    CardFieldState,
    CardStatus,
    CompactEvidenceRecord,
    ContractError,
    DataSplit,
    DiagnosticRole,
    QueryContext,
    RouteAction,
    RouteDecision,
    SupportVerdict,
    TeacherEvidenceDecision,
    TeacherTrace,
)
from .renderer import (
    DeterministicDiagnosisCardRenderer,
    RenderEvidenceDecision,
    RenderFieldPlan,
)


TRACE_EXPORT_SCHEMA = "rp3_teacher_candidate_trace_v1"
TEACHER_TRACE_BUNDLE_SOURCE_SCHEMA = "rp3_teacher_trace_bundle_source_v1"


@dataclass(frozen=True)
class CandidateTraceExport:
    query_id: str
    candidate_ids: tuple[str, ...]
    decisions: tuple[TeacherEvidenceDecision, ...]
    availability_mask: tuple[bool, ...]
    selection_budget: int
    underfill_reason_codes: tuple[str, ...]
    source_teacher_method: str


def route_from_teacher_row(
    row: Mapping[str, Any],
    *,
    default_student_cost: float,
    default_teacher_cost: float,
    default_abstention_cost: float,
) -> tuple[RouteDecision, dict[str, float]]:
    """Read an explicit three-action route label and its realized action costs.

    The route is intentionally not inferred from ``selected_evidence_ids``.
    A teacher export must record the outcome/cost policy that produced ANSWER,
    FALLBACK, or ABSTAIN; otherwise the route head would be trained on a hidden
    heuristic rather than reproducible teacher supervision.
    """

    raw_route = row.get("route")
    if not isinstance(raw_route, Mapping):
        raise ContractError("teacher row must contain an explicit route object")
    route = RouteDecision.from_dict(raw_route)
    raw_costs = row.get("route_action_costs")
    if not isinstance(raw_costs, Mapping):
        raise ContractError(
            "teacher row must contain explicit answer/fallback/abstain route_action_costs"
        )
    defaults = {
        RouteAction.ANSWER.value: float(default_student_cost),
        RouteAction.FALLBACK.value: float(default_teacher_cost),
        RouteAction.ABSTAIN.value: float(default_abstention_cost),
    }
    normalized: dict[str, float] = {}
    if {str(key) for key in raw_costs} != set(defaults):
        raise ContractError(
            "route_action_costs must contain exactly answer, fallback, and abstain"
        )
    for action, declared_default in defaults.items():
        value = float(raw_costs[action])
        if not math.isfinite(value) or value < 0:
            raise ContractError("route_action_costs must be finite and non-negative")
        normalized[action] = value
        # Defaults document the protocol but never replace per-row realized
        # costs.  Preserve both so the exported label remains auditable.
        if not math.isfinite(declared_default) or declared_default < 0:
            raise ContractError("default route costs must be finite and non-negative")
    return route, normalized


def export_candidate_decisions(
    row: Mapping[str, Any],
    *,
    require_complete_top_n: int = 32,
    maximum_selected: int = 3,
    required_teacher_method: str = "Ours_v6_k3_equal",
    allowed_evidence_ids: Iterable[str] | None = None,
    candidate_count_policy: str = "exact",
) -> CandidateTraceExport:
    """Validate a full teacher row and convert it to ordered decisions."""

    query_id = str(row.get("query_id") or "").strip()
    method = str(row.get("teacher_method") or row.get("method") or row.get("source_method") or "").strip()
    candidates = row.get("candidates", row.get("ranked"))
    if not query_id or not method or not isinstance(candidates, list):
        raise ContractError("teacher candidate row requires query_id, method, and candidates")
    if method != required_teacher_method:
        raise ContractError(
            f"teacher candidate row uses method={method!r}; required {required_teacher_method!r}"
        )
    if candidate_count_policy not in {"exact", "at_most"}:
        raise ContractError("unknown candidate count policy")
    if (len(candidates) != require_complete_top_n if candidate_count_policy == "exact"
        else len(candidates) > require_complete_top_n):
        raise ContractError(
            f"{query_id} exposes {len(candidates)} candidates; full top-{require_complete_top_n} "
            "teacher trace is required for rank distillation"
        )
    ids = tuple(str(item.get("evidence_id") or "").strip() for item in candidates)
    if not all(ids) or len(set(ids)) != len(ids):
        raise ContractError(f"{query_id} candidate evidence IDs must be unique and non-empty")
    if allowed_evidence_ids is not None:
        allowed = {str(value) for value in allowed_evidence_ids}
        outside = sorted(set(ids) - allowed)
        if outside:
            raise ContractError(
                f"{query_id} contains IDs outside the frozen strict-208 graph: "
                + ", ".join(outside)
            )
    availability = tuple(bool(item.get("available", True)) for item in candidates)
    if any(type(item.get("available", True)) is not bool for item in candidates):
        raise ContractError("candidate availability values must be JSON booleans")
    final_support = row.get("final_support_by_evidence_id", {})
    selected_ids = tuple(str(value) for value in row.get("selected_evidence_ids", ()))
    if not isinstance(final_support, Mapping):
        raise ContractError("final_support_by_evidence_id must be an object")
    if not set(selected_ids).issubset(ids):
        raise ContractError("selected evidence IDs must be present in full candidates")
    if len(selected_ids) > maximum_selected:
        raise ContractError("teacher selected evidence exceeds the RP3 selection budget")
    if any(not availability[ids.index(evidence_id)] for evidence_id in selected_ids):
        raise ContractError("teacher selected an unavailable evidence ID")
    decisions = []
    for rank, (evidence_id, candidate) in enumerate(zip(ids, candidates), start=1):
        raw_support = final_support.get(evidence_id)
        if raw_support in (1, True, "1", "direct"):
            support = SupportVerdict.DIRECT
        elif raw_support in (0, False, "0", "irrelevant"):
            support = SupportVerdict.IRRELEVANT
        elif raw_support in ("indirect",):
            support = SupportVerdict.INDIRECT
        elif raw_support is None:
            support = SupportVerdict.NOT_ASSESSED
        else:
            raise ContractError(f"invalid final support value for {evidence_id}: {raw_support!r}")
        selected = evidence_id in selected_ids
        if selected and support != SupportVerdict.DIRECT:
            raise ContractError("every selected teacher pointer must have direct support")
        decisions.append(
            TeacherEvidenceDecision(
                evidence_id=evidence_id,
                rank=rank,
                teacher_score=float(candidate.get("score", 0.0)),
                support=support,
                selected=selected,
            )
        )
    underfill = tuple(str(value) for value in row.get("underfill_reason_codes", ()))
    if len(selected_ids) < maximum_selected and not underfill:
        raise ContractError("an underfilled teacher trace must declare a reason")
    if len(selected_ids) == maximum_selected and underfill:
        raise ContractError("a full teacher selection cannot declare underfill reasons")
    return CandidateTraceExport(
        query_id=query_id,
        candidate_ids=ids,
        decisions=tuple(decisions),
        availability_mask=availability,
        selection_budget=maximum_selected,
        underfill_reason_codes=underfill,
        source_teacher_method=method,
    )


def assert_top3_replay_not_used_for_rank_training(rows: Iterable[Mapping[str, Any]]) -> None:
    for row in rows:
        candidates = row.get("candidates", row.get("ranked", ()))
        if len(candidates) <= 3:
            raise ContractError(
                "RP2 top-3 replay is a compatibility artifact, not a complete rank-"
                "distillation trace; rebuild and export top-32 teacher candidates"
            )


def assemble_single_role_teacher_trace(
    *,
    trace_id: str,
    query: QueryContext,
    candidate_trace: CandidateTraceExport,
    records_by_id: Mapping[str, CompactEvidenceRecord],
    route: RouteDecision,
    route_action_costs: Mapping[RouteAction | str, float],
    split: DataSplit,
    teacher_graph_id: str,
    teacher_replay_id: str,
    perturbation_id: str = "original",
    metadata: Mapping[str, Any] | None = None,
) -> TeacherTrace:
    """Compile one RP2 role query into a complete-schema RP3 trace.

    RP2 v6 evaluates one known fault and one diagnostic role per query.  RP3
    retains that supervision granularity: the requested role is populated from
    direct, selected evidence and every other card slot is explicitly marked
    insufficient.  Four role traces can later be combined by the deterministic
    card assembler; no language model is allowed to fill the missing slots.

    Label-leakage groups are derived from the selected/cited evidence.  Full
    top-32 candidate provenance remains in metadata so a separate inductive
    document/source-family holdout can be built without pretending that the
    shared fixed-memory validation split is an unseen-corpus experiment.
    """

    if not isinstance(query, QueryContext):
        query = QueryContext.from_dict(query)
    if query.query_id != candidate_trace.query_id:
        raise ContractError("query_id disagrees with the candidate trace")
    if query.requested_role not in CARD_SLOT_ROLES:
        raise ContractError(
            "an RP2 teacher trace must request one concrete diagnostic role"
        )
    if not isinstance(route, RouteDecision):
        route = RouteDecision.from_dict(route)
    try:
        split = DataSplit(str(split))
    except ValueError as exc:
        raise ContractError("teacher trace split is invalid") from exc

    normalized_costs: dict[str, float] = {}
    for action in RouteAction:
        raw = route_action_costs.get(action, route_action_costs.get(action.value))
        if raw is None:
            raise ContractError(
                "route_action_costs must explicitly contain answer, fallback, and abstain"
            )
        value = float(raw)
        if not math.isfinite(value) or value < 0:
            raise ContractError("route_action_costs must be finite and non-negative")
        normalized_costs[action.value] = value
    extra_costs = {
        str(key.value if isinstance(key, RouteAction) else key)
        for key in route_action_costs
    } - {action.value for action in RouteAction}
    if extra_costs:
        raise ContractError("route_action_costs contains unknown actions")

    missing = sorted(set(candidate_trace.candidate_ids) - set(records_by_id))
    if missing:
        raise ContractError(
            "candidate trace references unresolved evidence: " + ", ".join(missing)
        )
    candidate_records = tuple(
        records_by_id[evidence_id] for evidence_id in candidate_trace.candidate_ids
    )
    selected_ids = {
        decision.evidence_id
        for decision in candidate_trace.decisions
        if decision.selected
    }
    for evidence_id in selected_ids:
        record = records_by_id[evidence_id]
        if record.role != query.requested_role:
            raise ContractError(
                f"selected evidence {evidence_id} is outside the requested role"
            )
        if query.fault_id not in record.fault_class_ids:
            raise ContractError(
                f"selected evidence {evidence_id} is outside the requested fault scope"
            )

    render_decisions = tuple(
        RenderEvidenceDecision(
            evidence_id=decision.evidence_id,
            support=decision.support,
            selected=decision.selected,
            rank=decision.rank,
        )
        for decision in candidate_trace.decisions
    )
    selected_count = len(selected_ids)
    field_plan = tuple(
        RenderFieldPlan(
            role=role,
            state=(
                CardFieldState.SUPPORTED
                if role == query.requested_role and selected_count
                else CardFieldState.INSUFFICIENT
            ),
            cardinality=(selected_count if role == query.requested_role else 0),
        )
        for role in CARD_SLOT_ROLES
    )
    card = DeterministicDiagnosisCardRenderer().render(
        query=query,
        records_by_id=records_by_id,
        decisions=render_decisions,
        field_plan=field_plan,
    )
    if selected_count == 0 and route.action == RouteAction.ANSWER:
        raise ContractError("an empty teacher selection cannot use route=answer")
    if selected_count and route.action != RouteAction.ANSWER:
        # Fallback/abstain supervision must expose a fact-free local card.  The
        # teacher's selected pointers remain in evidence_decisions for ranking
        # and support losses, but are not presented as an accepted local answer.
        card = DeterministicDiagnosisCardRenderer().render(
            query=query,
            records_by_id={},
            decisions=(),
            field_plan=tuple(
                RenderFieldPlan(
                    role=role,
                    state=CardFieldState.INSUFFICIENT,
                    cardinality=0,
                )
                for role in CARD_SLOT_ROLES
            ),
        )
    if route.action == RouteAction.ANSWER and card.status not in {
        CardStatus.ANSWERED,
        CardStatus.PARTIAL,
    }:
        raise ContractError("route=answer requires a supported teacher card")

    trace_metadata = dict(metadata or {})
    trace_metadata.update(
        {
            "candidate_trace_schema": TRACE_EXPORT_SCHEMA,
            "source_teacher_method": candidate_trace.source_teacher_method,
            "supervision_granularity": "known_fault_single_diagnostic_role",
            "route_action_costs": normalized_costs,
            "candidate_claim_ids": sorted(
                {record.claim_id for record in candidate_records}
            ),
            "candidate_document_ids": sorted(
                {record.provenance.doc_id for record in candidate_records}
            ),
            "candidate_source_family_ids": sorted(
                {record.provenance.source_family_id for record in candidate_records}
            ),
            "validation_semantics": "fixed_memory_query_generalization",
        }
    )
    return TeacherTrace(
        trace_id=trace_id,
        query=query,
        candidate_evidence_ids=candidate_trace.candidate_ids,
        availability_mask=candidate_trace.availability_mask,
        selection_budget=candidate_trace.selection_budget,
        underfill_reason_codes=candidate_trace.underfill_reason_codes,
        evidence_decisions=candidate_trace.decisions,
        diagnosis_card=card,
        route=route,
        split=split,
        claim_group_ids=tuple(
            sorted(
                {
                    records_by_id[evidence_id].claim_id
                    for evidence_id in card.cited_evidence_ids
                }
            )
        ),
        document_group_ids=tuple(
            sorted(
                {
                    record.provenance.doc_id
                    for record in candidate_records
                }
            )
        ),
        source_family_group_ids=tuple(
            sorted(
                {
                    record.provenance.source_family_id
                    for record in candidate_records
                }
            )
        ),
        teacher_graph_id=teacher_graph_id,
        teacher_replay_id=teacher_replay_id,
        perturbation_id=perturbation_id,
        metadata=trace_metadata,
    )


__all__ = [
    "TRACE_EXPORT_SCHEMA",
    "TEACHER_TRACE_BUNDLE_SOURCE_SCHEMA",
    "CandidateTraceExport",
    "assemble_single_role_teacher_trace",
    "assert_top3_replay_not_used_for_rank_training",
    "export_candidate_decisions",
    "route_from_teacher_row",
]
