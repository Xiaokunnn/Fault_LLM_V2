from __future__ import annotations

from dataclasses import replace

import pytest

from src.research_point_3.contracts import (
    CARD_SLOT_ROLES,
    CardFieldState,
    CompactEvidenceRecord,
    ContractError,
    DataSplit,
    DiagnosticRole,
    EvidenceProvenance,
    QueryContext,
    RouteAction,
    RouteDecision,
    SupportVerdict,
)
from src.research_point_3.renderer import merge_single_role_teacher_traces
from src.research_point_3.trace_export import (
    assemble_single_role_teacher_trace,
    assert_top3_replay_not_used_for_rank_training,
    export_candidate_decisions,
    route_from_teacher_row,
)


def _row(count: int = 4) -> dict:
    ids = [f"E{index}" for index in range(count)]
    return {
        "query_id": "Q1",
        "method": "Ours_v6_k3_equal",
        "candidates": [
            {"evidence_id": evidence_id, "score": 1.0 - index / 10, "available": True}
            for index, evidence_id in enumerate(ids)
        ],
        "final_support_by_evidence_id": {ids[0]: 1, ids[1]: 0},
        "selected_evidence_ids": [ids[0]],
        "underfill_reason_codes": ["only_one_direct_support"],
    }


def test_full_candidate_export_keeps_rank_and_support() -> None:
    result = export_candidate_decisions(_row(), require_complete_top_n=4)
    assert result.candidate_ids == ("E0", "E1", "E2", "E3")
    assert result.decisions[0].support == SupportVerdict.DIRECT
    assert result.decisions[2].support == SupportVerdict.NOT_ASSESSED


def test_archived_top3_replay_is_rejected_as_rank_training_data() -> None:
    with pytest.raises(ContractError, match="not a complete"):
        assert_top3_replay_not_used_for_rank_training([{"ranked": [{}, {}, {}]}])


def test_export_requires_underfill_reason() -> None:
    row = _row()
    row["underfill_reason_codes"] = []
    with pytest.raises(ContractError, match="underfilled"):
        export_candidate_decisions(row, require_complete_top_n=4)


def test_export_requires_frozen_teacher_method_and_id_closure() -> None:
    row = _row()
    row["method"] = "Dense_k3_equal"
    with pytest.raises(ContractError, match="required"):
        export_candidate_decisions(row, require_complete_top_n=4)
    row = _row()
    with pytest.raises(ContractError, match="strict-208"):
        export_candidate_decisions(
            row,
            require_complete_top_n=4,
            allowed_evidence_ids={"E0", "E1", "E2"},
        )


def _record(evidence_id: str, role: DiagnosticRole, index: int) -> CompactEvidenceRecord:
    return CompactEvidenceRecord(
        evidence_id=evidence_id,
        claim_id=f"C-{evidence_id}",
        head_label_zh="汽蚀",
        relation="manifests_as" if role == DiagnosticRole.SYMPTOM else "mitigated_by",
        tail_label_zh="证据结论",
        role=role,
        fault_class_ids=("cavitation",),
        evidence_text=f"{role.value} evidence {evidence_id}",
        provenance=EvidenceProvenance(
            doc_id=f"MP{index + 1:03d}",
            physical_pdf_page=1,
            source_family_id=f"SF-{index}",
        ),
        partition=DataSplit.TRAIN,
        memory_index=index,
    )


def _route() -> RouteDecision:
    return RouteDecision(
        action=RouteAction.ANSWER,
        reason_codes=("teacher_supported",),
        estimated_student_cost=1.0,
        estimated_teacher_cost=8.0,
        estimated_error_cost=0.0,
        confidence=1.0,
    )


def test_single_role_trace_and_multi_role_card_bridge_are_deterministic() -> None:
    roles = (
        DiagnosticRole.SYMPTOM,
        DiagnosticRole.MAINTENANCE,
        DiagnosticRole.MAINTENANCE,
        DiagnosticRole.MAINTENANCE,
    )
    records = {
        f"E{index}": _record(f"E{index}", roles[index], index)
        for index in range(4)
    }
    costs = {"answer": 1.0, "fallback": 8.0, "abstain": 12.0}

    symptom_export = export_candidate_decisions(_row(), require_complete_top_n=4)
    symptom_trace = assemble_single_role_teacher_trace(
        trace_id="T-SYM",
        query=QueryContext(
            query_id="Q1",
            question_zh="汽蚀有哪些症状？",
            fault_id="cavitation",
            fault_name_zh="汽蚀",
            requested_role=DiagnosticRole.SYMPTOM,
            scenario_id="cavitation-card",
        ),
        candidate_trace=symptom_export,
        records_by_id=records,
        route=_route(),
        route_action_costs=costs,
        split=DataSplit.TRAIN,
        teacher_graph_id="TeacherGraph_RP3_v1",
        teacher_replay_id="RP2-v6-replay",
    )
    assert symptom_trace.diagnosis_card.cited_evidence_ids == ("E0",)
    assert symptom_trace.metadata["route_action_costs"] == costs
    assert symptom_trace.metadata["candidate_document_ids"] == [
        "MP001",
        "MP002",
        "MP003",
        "MP004",
    ]

    maintenance_row = _row()
    maintenance_row["query_id"] = "Q2"
    maintenance_row["selected_evidence_ids"] = ["E1"]
    maintenance_row["final_support_by_evidence_id"] = {"E0": 0, "E1": 1}
    maintenance_trace = assemble_single_role_teacher_trace(
        trace_id="T-MAINT",
        query=QueryContext(
            query_id="Q2",
            question_zh="汽蚀有哪些维护措施？",
            fault_id="cavitation",
            fault_name_zh="汽蚀",
            requested_role=DiagnosticRole.MAINTENANCE,
            scenario_id="cavitation-card",
        ),
        candidate_trace=export_candidate_decisions(
            maintenance_row, require_complete_top_n=4
        ),
        records_by_id=records,
        route=_route(),
        route_action_costs=costs,
        split=DataSplit.TRAIN,
        teacher_graph_id="TeacherGraph_RP3_v1",
        teacher_replay_id="RP2-v6-replay",
    )
    merged = merge_single_role_teacher_traces(
        {
            DiagnosticRole.SYMPTOM: symptom_trace,
            DiagnosticRole.MAINTENANCE: maintenance_trace,
        }
    )
    state_by_role = {slot.role: slot.state for slot in merged.slots}
    assert tuple(state_by_role) == CARD_SLOT_ROLES
    assert state_by_role[DiagnosticRole.SYMPTOM] == CardFieldState.SUPPORTED
    assert state_by_role[DiagnosticRole.MAINTENANCE] == CardFieldState.SUPPORTED
    assert state_by_role[DiagnosticRole.INSPECTION] == CardFieldState.INSUFFICIENT
    assert merged.cited_evidence_ids == ("E0", "E1")


def test_visible_teacher_scope_mismatch_is_disclosed_without_relabelling_graph() -> None:
    records = {f"E{index}": _record(f"E{index}", DiagnosticRole.SYMPTOM, index)
        for index in range(4)}
    records["E0"] = replace(records["E0"], fault_class_ids=("neighbour_fault",))
    trace = assemble_single_role_teacher_trace(
        trace_id="T-CROSS-LABEL",
        query=QueryContext("Q1","堵塞有哪些症状？","hydraulic_blockage","堵塞",
            DiagnosticRole.SYMPTOM,"S1"),
        candidate_trace=export_candidate_decisions(_row(),require_complete_top_n=4),
        records_by_id=records,route=_route(),
        route_action_costs={"answer":1.0,"fallback":8.0,"abstain":12.0},
        split=DataSplit.TRAIN,teacher_graph_id="TeacherGraph_RP3_v1",
        teacher_replay_id="RP2-v6-replay")
    assert records["E0"].fault_class_ids == ("neighbour_fault",)
    assert trace.metadata["automatic_fault_label_mismatch_selected_evidence_ids"] == ["E0"]


def test_route_export_requires_explicit_three_action_costs() -> None:
    row = {
        "route": {
            "action": "fallback",
            "reason_codes": ["teacher_correction_gain"],
            "estimated_student_cost": 1.0,
            "estimated_teacher_cost": 8.0,
            "estimated_error_cost": 5.0,
            "confidence": 0.8,
        },
        "route_action_costs": {
            "answer": 5.0,
            "fallback": 8.0,
            "abstain": 2.0,
        },
    }
    route, costs = route_from_teacher_row(
        row,
        default_student_cost=1.0,
        default_teacher_cost=8.0,
        default_abstention_cost=2.0,
    )
    assert route.action == RouteAction.FALLBACK
    assert costs == row["route_action_costs"]
    del row["route_action_costs"]["abstain"]
    with pytest.raises(ContractError, match="exactly"):
        route_from_teacher_row(
            row,
            default_student_cost=1.0,
            default_teacher_cost=8.0,
            default_abstention_cost=2.0,
        )
