"""Deterministic, pointer-grounded diagnosis-card rendering.

The renderer never asks a language model to paraphrase or complete a card.  It
copies the evidence text of records that the controller marked as *directly*
supporting the query into the matching slot.  Fixed labels and insufficiency
markers are presentation metadata; they do not introduce pump-system facts.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .contracts import (
    CARD_SLOT_ROLES,
    CardFieldState,
    CardItem,
    CardStatus,
    CompactEvidenceRecord,
    ContractError,
    DiagnosisCard,
    DiagnosisCardSlot,
    DiagnosticRole,
    EvidenceConflict,
    QueryContext,
    RouteAction,
    SupportVerdict,
)


SLOT_LABELS_ZH: Mapping[DiagnosticRole, str] = {
    DiagnosticRole.SYMPTOM: "症状表现",
    DiagnosticRole.CAUSE_OR_MECHANISM: "可能原因或机理",
    DiagnosticRole.INSPECTION: "检查建议",
    DiagnosticRole.MAINTENANCE: "维护建议",
}


@dataclass(frozen=True)
class RenderEvidenceDecision:
    """Minimal renderer input kept independent of a concrete model class."""

    evidence_id: str
    support: SupportVerdict
    selected: bool
    rank: int

    def __post_init__(self) -> None:
        evidence_id = str(self.evidence_id).strip()
        if not evidence_id:
            raise ContractError("render evidence_id must be non-empty")
        object.__setattr__(self, "evidence_id", evidence_id)
        try:
            support = SupportVerdict(str(self.support))
        except ValueError as exc:
            raise ContractError("invalid render support verdict") from exc
        object.__setattr__(self, "support", support)
        if type(self.selected) is not bool:
            raise ContractError("render selected must be a JSON boolean")
        rank = int(self.rank)
        if rank < 1:
            raise ContractError("render rank must be >= 1")
        object.__setattr__(self, "rank", rank)


@dataclass(frozen=True)
class RenderFieldPlan:
    """Decoded field-head output consumed without reinterpretation.

    ``cardinality`` is the number of selected evidence pointers that survive
    the field head's STOP decision for this role.  The renderer checks the
    number; it never fills a field merely because matching evidence exists.
    """

    role: DiagnosticRole
    state: CardFieldState
    cardinality: int

    def __post_init__(self) -> None:
        try:
            role = DiagnosticRole(str(self.role))
        except ValueError as exc:
            raise ContractError("invalid render field role") from exc
        if role not in CARD_SLOT_ROLES:
            raise ContractError("render field role must be a diagnosis-card slot")
        object.__setattr__(self, "role", role)
        try:
            state = CardFieldState(str(self.state))
        except ValueError as exc:
            raise ContractError("invalid render field state") from exc
        object.__setattr__(self, "state", state)
        cardinality = int(self.cardinality)
        if cardinality < 0:
            raise ContractError("render field cardinality must be >= 0")
        if state in {
            CardFieldState.INSUFFICIENT,
            CardFieldState.NOT_APPLICABLE,
        } and cardinality != 0:
            raise ContractError(
                f"field state={state.value} requires cardinality=0"
            )
        if state == CardFieldState.SUPPORTED and cardinality < 1:
            raise ContractError("field state=supported requires cardinality >= 1")
        if state == CardFieldState.CONFLICT and cardinality < 2:
            raise ContractError("field state=conflict requires cardinality >= 2")
        object.__setattr__(self, "cardinality", cardinality)


def _stable_card_id(query: QueryContext, evidence_ids: tuple[str, ...]) -> str:
    payload = json.dumps(
        {
            "query_id": query.query_id,
            "fault_id": query.fault_id,
            "scenario_id": query.scenario_id,
            "evidence_ids": list(evidence_ids),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "RP3-CARD-" + hashlib.sha256(payload).hexdigest()[:16]


class DeterministicDiagnosisCardRenderer:
    """Build the frozen RP2-aligned four-slot card from legal direct pointers."""

    def render(
        self,
        *,
        query: QueryContext,
        records_by_id: Mapping[str, CompactEvidenceRecord],
        decisions: Iterable[RenderEvidenceDecision],
        field_plan: Iterable[RenderFieldPlan],
        scope_authorized_evidence_ids: Iterable[str] = (),
    ) -> DiagnosisCard:
        if not isinstance(query, QueryContext):
            query = QueryContext.from_dict(query)
        normalized = tuple(
            decision
            if isinstance(decision, RenderEvidenceDecision)
            else RenderEvidenceDecision(
                evidence_id=getattr(decision, "evidence_id", ""),
                support=getattr(decision, "support", SupportVerdict.NOT_ASSESSED),
                selected=getattr(decision, "selected", False),
                rank=getattr(decision, "rank", 0),
            )
            for decision in decisions
        )
        ids = [decision.evidence_id for decision in normalized]
        if len(set(ids)) != len(ids):
            raise ContractError("renderer decisions must not contain duplicate evidence IDs")

        planned = tuple(
            field
            if isinstance(field, RenderFieldPlan)
            else RenderFieldPlan(
                role=getattr(field, "role", ""),
                state=getattr(field, "state", ""),
                cardinality=getattr(field, "cardinality", -1),
            )
            for field in field_plan
        )
        planned_roles = tuple(field.role for field in planned)
        if len(planned) != len(CARD_SLOT_ROLES) or set(planned_roles) != set(
            CARD_SLOT_ROLES
        ):
            raise ContractError(
                "renderer field plan must contain each frozen card slot exactly once"
            )
        planned_by_role = {field.role: field for field in planned}

        direct = tuple(
            sorted(
                (
                    decision
                    for decision in normalized
                    if decision.selected and decision.support == SupportVerdict.DIRECT
                ),
                key=lambda decision: decision.rank,
            )
        )
        # A selected pointer with anything other than direct support is a model
        # contract failure, not a fact to be silently rendered.
        invalid_selected = [
            decision.evidence_id
            for decision in normalized
            if decision.selected and decision.support != SupportVerdict.DIRECT
        ]
        if invalid_selected:
            raise ContractError(
                "selected card evidence must have direct support: "
                + ", ".join(invalid_selected)
            )

        scope_authorized = {str(value) for value in scope_authorized_evidence_ids}
        selected_records: list[tuple[RenderEvidenceDecision, CompactEvidenceRecord]] = []
        for decision in direct:
            record = records_by_id.get(decision.evidence_id)
            if record is None:
                raise ContractError(
                    f"renderer cannot resolve evidence_id={decision.evidence_id}"
                )
            if record.evidence_id != decision.evidence_id:
                raise ContractError("renderer evidence mapping contains an ID mismatch")
            if record.role not in CARD_SLOT_ROLES:
                raise ContractError(
                    f"evidence {record.evidence_id} has an illegal diagnosis-card role"
                )
            if (
                query.fault_id not in record.fault_class_ids
                and record.evidence_id not in scope_authorized
            ):
                raise ContractError(
                    f"evidence {record.evidence_id} is outside query fault scope"
                )
            if (
                query.requested_role != DiagnosticRole.FULL_CARD
                and record.role != query.requested_role
            ):
                raise ContractError(
                    f"evidence {record.evidence_id} is outside requested diagnostic role"
                )
            selected_records.append((decision, record))

        slots: list[DiagnosisCardSlot] = []
        conflicts: list[EvidenceConflict] = []
        for role in CARD_SLOT_ROLES:
            role_records = [item for item in selected_records if item[1].role == role]
            plan = planned_by_role[role]
            if len(role_records) != plan.cardinality:
                raise ContractError(
                    f"field cardinality mismatch for role={role.value}: "
                    f"planned={plan.cardinality}, selected={len(role_records)}"
                )
            if plan.state in {
                CardFieldState.INSUFFICIENT,
                CardFieldState.NOT_APPLICABLE,
            }:
                slots.append(
                    DiagnosisCardSlot(
                        role=role,
                        state=plan.state,
                        items=(),
                    )
                )
                continue
            items = tuple(
                CardItem(
                    item_id=f"{role.value}-{order}",
                    # Verbatim evidence is the only factual text in the shell.
                    text_zh=record.evidence_text,
                    evidence_ids=(record.evidence_id,),
                    order=order,
                )
                for order, (_, record) in enumerate(role_records, start=1)
            )
            slots.append(
                DiagnosisCardSlot(
                    role=role,
                    state=plan.state,
                    items=items,
                )
            )
            if plan.state == CardFieldState.CONFLICT:
                conflicts.append(
                    EvidenceConflict(
                        conflict_id=f"controller-conflict-{role.value}",
                        evidence_ids=tuple(
                            record.evidence_id for _, record in role_records
                        ),
                        # This reports the controller state; it does not infer
                        # which factual proposition is correct.
                        description_zh="控制器将该字段标记为证据冲突，需人工复核。",
                    )
                )

        supported_count = sum(
            slot.state == CardFieldState.SUPPORTED for slot in slots
        )
        if conflicts:
            status = CardStatus.CONFLICTING_EVIDENCE
        elif supported_count == 0:
            status = CardStatus.INSUFFICIENT_EVIDENCE
        elif supported_count == len(CARD_SLOT_ROLES):
            status = CardStatus.ANSWERED
        else:
            status = CardStatus.PARTIAL
        selected_ids = tuple(record.evidence_id for _, record in selected_records)
        return DiagnosisCard(
            card_id=_stable_card_id(query, selected_ids),
            status=status,
            fault_ids=(query.fault_id,),
            applicability_conditions=query.operating_context,
            slots=tuple(slots),
            conflicts=tuple(conflicts),
        )

    def render_natural_language_shell(self, card: DiagnosisCard) -> str:
        """Render labels, states, verbatim card items, and pointers only.

        The function intentionally omits fluent transitions, diagnoses, and
        generic safety advice: each of those can create an unsupported atomic
        proposition.  A downstream LLM may present this string unchanged, but
        it must not rewrite the evidence text.
        """

        if not isinstance(card, DiagnosisCard):
            card = DiagnosisCard.from_dict(card)
        lines = [f"诊断卡状态：{card.status.value}"]
        for slot in card.slots:
            lines.append(f"{SLOT_LABELS_ZH[slot.role]}：")
            if not slot.items:
                lines.append("- 证据不足")
                continue
            for item in slot.items:
                pointers = ",".join(item.evidence_ids)
                lines.append(f"- [{pointers}] {item.text_zh}")
        return "\n".join(lines)


def merge_single_role_teacher_traces(
    traces_by_role: Mapping[DiagnosticRole | str, object],
) -> DiagnosisCard:
    """Merge governed RP2 role traces with one frozen teacher identity.

    RP2 v6 has one query per known fault and diagnostic role.  This adapter is
    the explicit bridge to the RP3 complete-card presentation: it copies only
    the slot owned by each role call, marks missing roles insufficient, and
    carries only conflicts whose evidence is cited by that owned slot.  Requiring
    full traces prevents cards from different scenarios/teachers being mixed.
    """

    # Imported lazily to keep renderer/contracts dependency direction simple.
    from .contracts import TeacherTrace

    if not isinstance(traces_by_role, Mapping) or not traces_by_role:
        raise ContractError("at least one single-role teacher trace is required")
    normalized: dict[DiagnosticRole, DiagnosisCard] = {}
    trace_identity: set[tuple[str, str, str, str]] = set()
    for raw_role, raw_trace in traces_by_role.items():
        try:
            role = DiagnosticRole(str(raw_role))
        except ValueError as exc:
            raise ContractError("single-role card mapping contains an invalid role") from exc
        if role not in CARD_SLOT_ROLES:
            raise ContractError("single-role card mapping requires concrete card roles")
        if role in normalized:
            raise ContractError(f"duplicate single-role card for {role.value}")
        trace = (
            raw_trace
            if isinstance(raw_trace, TeacherTrace)
            else TeacherTrace.from_dict(raw_trace)
        )
        if trace.query.requested_role != role:
            raise ContractError("trace role disagrees with the card mapping key")
        if trace.route.action != RouteAction.ANSWER:
            raise ContractError("only locally answered role traces can contribute card facts")
        trace_identity.add(
            (
                trace.query.fault_id,
                trace.query.scenario_id,
                trace.teacher_graph_id,
                trace.teacher_replay_id,
            )
        )
        card = trace.diagnosis_card
        owned_slot = next(slot for slot in card.slots if slot.role == role)
        leaked = [
            slot.role.value
            for slot in card.slots
            if slot.role != role and slot.items
        ]
        if leaked:
            raise ContractError(
                f"single-role card for {role.value} contains items in other slots: "
                + ", ".join(leaked)
            )
        owned_ids = {
            evidence_id
            for item in owned_slot.items
            for evidence_id in item.evidence_ids
        }
        if any(
            not set(conflict.evidence_ids).issubset(owned_ids)
            for conflict in card.conflicts
        ):
            raise ContractError(
                f"single-role card for {role.value} has a conflict outside its owned slot"
            )
        normalized[role] = card

    if len(trace_identity) != 1:
        raise ContractError(
            "single-role traces must share fault, scenario, teacher graph, and replay"
        )

    fault_sets = {card.fault_ids for card in normalized.values()}
    if len(fault_sets) != 1:
        raise ContractError("single-role cards must describe the same known fault scope")
    fault_ids = next(iter(fault_sets))
    slots = tuple(
        (
            next(slot for slot in normalized[role].slots if slot.role == role)
            if role in normalized
            else DiagnosisCardSlot(
                role=role,
                state=CardFieldState.INSUFFICIENT,
                items=(),
            )
        )
        for role in CARD_SLOT_ROLES
    )
    conflicts = tuple(
        conflict
        for role in CARD_SLOT_ROLES
        if role in normalized
        for conflict in normalized[role].conflicts
    )
    supported_count = sum(slot.state == CardFieldState.SUPPORTED for slot in slots)
    if conflicts:
        status = CardStatus.CONFLICTING_EVIDENCE
    elif supported_count == 0:
        status = CardStatus.INSUFFICIENT_EVIDENCE
    elif supported_count == len(CARD_SLOT_ROLES):
        status = CardStatus.ANSWERED
    else:
        status = CardStatus.PARTIAL
    applicability = tuple(
        dict.fromkeys(
            condition
            for role in CARD_SLOT_ROLES
            if role in normalized
            for condition in normalized[role].applicability_conditions
        )
    )
    identity = json.dumps(
        {
            role.value: normalized[role].card_id
            for role in CARD_SLOT_ROLES
            if role in normalized
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return DiagnosisCard(
        card_id="RP3-MERGED-" + hashlib.sha256(identity).hexdigest()[:16],
        status=status,
        fault_ids=fault_ids,
        applicability_conditions=applicability,
        slots=slots,
        conflicts=conflicts,
    )


__all__ = [
    "DeterministicDiagnosisCardRenderer",
    "RenderEvidenceDecision",
    "RenderFieldPlan",
    "SLOT_LABELS_ZH",
    "merge_single_role_teacher_traces",
]
