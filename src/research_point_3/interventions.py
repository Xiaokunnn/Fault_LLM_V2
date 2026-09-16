"""Governed evidence-set interventions for RP3 policy-distillation traces."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Iterable, Mapping

from .contracts import ContractError, TeacherTrace


INTERVENTION_VERSION = "rp3_evidence_intervention_v1"


def _id(trace_id: str, kind: str, targets: Iterable[str]) -> str:
    payload = "\n".join([INTERVENTION_VERSION, trace_id, kind, *sorted(targets)])
    return "RP3I-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def remove_evidence(
    trace: TeacherTrace,
    evidence_ids: Iterable[str],
) -> TeacherTrace:
    """Mask evidence without deleting its candidate position.

    A new teacher decision must later be attached by a model-capable replay.  To
    avoid inventing supervision, this function rejects removal of an already
    selected pointer; use ``mask_for_teacher_replay`` for that case.
    """

    targets = frozenset(str(value) for value in evidence_ids)
    unknown = sorted(targets - set(trace.candidate_evidence_ids))
    if unknown:
        raise ContractError("cannot remove unknown candidate IDs: " + ", ".join(unknown))
    selected = set(trace.selected_evidence_ids)
    if selected & targets:
        raise ContractError(
            "removing teacher-selected evidence changes the target; use "
            "mask_for_teacher_replay and rerun the frozen teacher"
        )
    if not targets or not any(
        available and evidence_id in targets
        for evidence_id, available in zip(trace.candidate_evidence_ids, trace.availability_mask)
    ):
        raise ContractError("intervention must change at least one availability value")
    mask = tuple(
        available and evidence_id not in targets
        for evidence_id, available in zip(
            trace.candidate_evidence_ids, trace.availability_mask
        )
    )
    return replace(
        trace,
        trace_id=_id(trace.trace_id, "remove_nonselected", targets),
        availability_mask=mask,
        perturbation_id=_id(trace.trace_id, "remove_nonselected", targets),
        metadata={
            **trace.metadata,
            "parent_trace_id": trace.trace_id,
            "intervention": {
                "version": INTERVENTION_VERSION,
                "kind": "remove_nonselected",
                "target_evidence_ids": sorted(targets),
                "teacher_replay_required": False,
            },
        },
    )


def mask_for_teacher_replay(
    trace: TeacherTrace,
    evidence_ids: Iterable[str],
) -> dict:
    """Create a replay request when an intervention invalidates teacher labels."""

    targets = frozenset(str(value) for value in evidence_ids)
    unknown = sorted(targets - set(trace.candidate_evidence_ids))
    if unknown:
        raise ContractError("cannot mask unknown candidate IDs: " + ", ".join(unknown))
    mask = [
        available and evidence_id not in targets
        for evidence_id, available in zip(
            trace.candidate_evidence_ids, trace.availability_mask
        )
    ]
    if mask == list(trace.availability_mask):
        raise ContractError("intervention must change at least one availability value")
    return {
        "schema": INTERVENTION_VERSION,
        "intervention_id": _id(trace.trace_id, "remove_for_replay", targets),
        "parent_trace_id": trace.trace_id,
        "kind": "evidence_availability_removal",
        "candidate_evidence_ids": list(trace.candidate_evidence_ids),
        "availability_mask": mask,
        "teacher_replay_required": True,
        "synthetic_label_allowed": False,
    }


def validate_intervention_lineage(rows: Iterable[Mapping[str, object]]) -> None:
    seen: set[str] = set()
    for row in rows:
        intervention_id = str(row.get("intervention_id") or "")
        parent = str(row.get("parent_trace_id") or "")
        if not intervention_id or not parent:
            raise ContractError("intervention records require IDs and parent trace lineage")
        if intervention_id in seen:
            raise ContractError(f"duplicate intervention ID: {intervention_id}")
        seen.add(intervention_id)
        if row.get("teacher_replay_required") is not True:
            raise ContractError("label-changing interventions require frozen teacher replay")
        if row.get("synthetic_label_allowed") is not False:
            raise ContractError("synthetic labels cannot replace teacher replay decisions")


def student_rollout_for_teacher_correction(
    trace: TeacherTrace,
    *,
    selected_evidence_ids: Iterable[str],
    support_by_evidence_id: Mapping[str, str],
    field_plan: Iterable[Mapping[str, object]],
    proposed_route: str,
    controller_version: str,
) -> dict[str, object]:
    """Build an auditable replay request for a student's on-policy mistake.

    This function records the student's symbolic decision only.  It never
    fabricates a corrected target: the frozen RP2 teacher must replay the same
    candidate signature and attach corrected ranking/support/field/route labels
    before the row may enter training.
    """

    selected = tuple(str(value).strip() for value in selected_evidence_ids)
    if any(not value for value in selected) or len(set(selected)) != len(selected):
        raise ContractError("student rollout pointers must be unique non-empty IDs")
    unknown = sorted(set(selected) - set(trace.candidate_evidence_ids))
    if unknown:
        raise ContractError(
            "student rollout contains unknown evidence IDs: " + ", ".join(unknown)
        )
    support = {str(key).strip(): str(value).strip() for key, value in support_by_evidence_id.items()}
    if any(not key or not value for key, value in support.items()):
        raise ContractError("student rollout support map must be non-empty strings")
    if set(support) - set(trace.candidate_evidence_ids):
        raise ContractError("student rollout support map contains unknown evidence IDs")
    fields = tuple(dict(value) for value in field_plan)
    if not fields:
        raise ContractError("student rollout must record the field plan")
    version = str(controller_version).strip()
    if not version:
        raise ContractError("student rollout controller_version must be non-empty")
    route = str(proposed_route).strip()
    if route not in {"answer", "fallback", "abstain"}:
        raise ContractError("student rollout proposed_route is invalid")
    from .artifacts import stable_sha256
    rollout_id = _id(trace.trace_id, "student_rollout", [stable_sha256({
        "selected": selected, "support": support, "fields": fields,
        "route": route, "controller_version": version,
    })])
    return {
        "schema": "rp3_student_rollout_teacher_correction_request_v1",
        "rollout_id": rollout_id,
        "parent_trace_id": trace.trace_id,
        "query": trace.query.to_dict(),
        "candidate_evidence_ids": list(trace.candidate_evidence_ids),
        "availability_mask": list(trace.availability_mask),
        "selection_budget": trace.selection_budget,
        "student_prediction": {
            "selected_evidence_ids": list(selected),
            "support_by_evidence_id": support,
            "field_plan": list(fields),
            "route": route,
            "controller_version": version,
        },
        "teacher_graph_id": trace.teacher_graph_id,
        "teacher_replay_id": trace.teacher_replay_id,
        "teacher_replay_required": True,
        "synthetic_label_allowed": False,
        "correction_status": "pending_teacher_replay",
    }
