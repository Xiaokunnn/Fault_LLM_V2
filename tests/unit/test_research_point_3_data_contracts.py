from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from src.research_point_3.artifacts import (
    read_compact_evidence_memory_bundle,
    read_teacher_trace_bundle,
    stable_sha256,
    validate_trace_memory_references,
    write_compact_evidence_memory_bundle,
    write_teacher_trace_bundle,
)
from src.research_point_3.contracts import (
    CARD_SLOT_ROLES,
    CardFieldState,
    CardItem,
    CardStatus,
    CompactEvidenceRecord,
    ContractError,
    DataSplit,
    DiagnosisCard,
    DiagnosisCardSlot,
    DiagnosticRole,
    EvidenceProvenance,
    QueryContext,
    RouteAction,
    RouteDecision,
    SupportVerdict,
    TeacherEvidenceDecision,
    TeacherTrace,
)
from src.research_point_3.splits import (
    assign_fixed_memory_query_splits,
    assign_grouped_splits,
    assert_training_trace_boundary,
)


def _card(evidence_id: str = "E1") -> DiagnosisCard:
    slots = []
    for role in CARD_SLOT_ROLES:
        if role == DiagnosticRole.SYMPTOM:
            slots.append(
                DiagnosisCardSlot(
                    role=role,
                    state=CardFieldState.SUPPORTED,
                    items=(
                        CardItem(
                            item_id="symptom-1",
                            text_zh="泵可能出现异常振动。",
                            evidence_ids=(evidence_id,),
                        ),
                    ),
                )
            )
        else:
            slots.append(
                DiagnosisCardSlot(role=role, state=CardFieldState.INSUFFICIENT)
            )
    return DiagnosisCard(
        card_id="CARD-Q1",
        status=CardStatus.PARTIAL,
        fault_ids=("F01",),
        applicability_conditions=("运行中",),
        slots=tuple(slots),
    )


def _trace(
    trace_id: str = "T1",
    *,
    doc_id: str = "MP001",
    split: DataSplit = DataSplit.UNASSIGNED,
    claim_id: str = "C1",
    source_family_id: str = "SF1",
) -> TeacherTrace:
    return TeacherTrace(
        trace_id=trace_id,
        query=QueryContext(
            query_id=f"Q-{trace_id}",
            question_zh="异常振动有哪些表现？",
            fault_id="F01",
            fault_name_zh="异常振动",
            requested_role=DiagnosticRole.FULL_CARD,
            scenario_id=f"S-{trace_id}",
        ),
        candidate_evidence_ids=("E1", "E2"),
        availability_mask=(True, True),
        selection_budget=2,
        underfill_reason_codes=("only_one_direct_support",),
        evidence_decisions=(
            TeacherEvidenceDecision(
                evidence_id="E1",
                rank=1,
                teacher_score=0.9,
                support=SupportVerdict.DIRECT,
                selected=True,
            ),
            TeacherEvidenceDecision(
                evidence_id="E2",
                rank=2,
                teacher_score=0.2,
                support=SupportVerdict.IRRELEVANT,
                selected=False,
            ),
        ),
        diagnosis_card=_card(),
        route=RouteDecision(
            action=RouteAction.ANSWER,
            reason_codes=("teacher_supported",),
            estimated_student_cost=1.0,
            estimated_teacher_cost=8.0,
            estimated_error_cost=2.0,
            confidence=0.9,
        ),
        split=split,
        claim_group_ids=(claim_id,),
        document_group_ids=(doc_id,),
        source_family_group_ids=(source_family_id,),
        teacher_graph_id="TeacherGraph_RP3_v1",
        teacher_replay_id="RP2_v6_replay_on_TeacherGraph_RP3_v1",
    )


def _memory(
    *,
    evidence_id: str = "E1",
    claim_id: str = "C1",
    doc_id: str = "MP001",
    partition: DataSplit = DataSplit.TRAIN,
    memory_index: int = 0,
) -> CompactEvidenceRecord:
    return CompactEvidenceRecord(
        evidence_id=evidence_id,
        claim_id=claim_id,
        head_label_zh="异常振动",
        relation="manifests_as",
        tail_label_zh="振幅升高",
        role=DiagnosticRole.SYMPTOM,
        fault_class_ids=("F01",),
        evidence_text="运行时振幅升高。",
        provenance=EvidenceProvenance(
            doc_id=doc_id,
            physical_pdf_page=3,
            source_family_id="SF1",
            source_url="https://example.invalid/manual.pdf",
        ),
        partition=partition,
        memory_index=memory_index,
        feature_vector=(0.25, -0.5),
        evidence_contract_confidence=0.9,
    )


def _zero_candidate_trace(trace_id: str = "T-ZERO") -> TeacherTrace:
    trace = _trace(trace_id)
    empty_card = DiagnosisCard(
        card_id=f"CARD-{trace_id}",
        status=CardStatus.INSUFFICIENT_EVIDENCE,
        fault_ids=(trace.query.fault_id,),
        applicability_conditions=(),
        slots=tuple(
            DiagnosisCardSlot(role=role, state=CardFieldState.INSUFFICIENT)
            for role in CARD_SLOT_ROLES
        ),
    )
    return replace(
        trace,
        candidate_evidence_ids=(),
        availability_mask=(),
        selection_budget=3,
        underfill_reason_codes=("no_role_candidates",),
        evidence_decisions=(),
        diagnosis_card=empty_card,
        route=RouteDecision(
            action=RouteAction.ABSTAIN,
            reason_codes=("no_candidate_evidence",),
            estimated_student_cost=1.0,
            estimated_teacher_cost=8.0,
            estimated_error_cost=2.0,
            confidence=1.0,
        ),
        claim_group_ids=(),
        document_group_ids=(),
        source_family_group_ids=(),
    )


def test_complete_card_rejects_missing_slot() -> None:
    card = _card()
    with pytest.raises(ContractError, match="complete diagnosis card"):
        replace(card, slots=card.slots[:-1])


def test_trace_requires_mask_and_selected_pointer_consistency() -> None:
    trace = _trace()
    with pytest.raises(ContractError, match="availability_mask"):
        replace(trace, availability_mask=(True,))
    with pytest.raises(ContractError, match="unavailable evidence"):
        replace(trace, availability_mask=(False, True))
    with pytest.raises(ContractError, match="JSON booleans"):
        replace(trace, availability_mask=(1, 1))


def test_group_split_keeps_shared_claim_together_and_forces_corpus_partitions() -> None:
    build_a = _trace("T1", claim_id="SHARED")
    build_b = replace(
        _trace("T2", doc_id="MP002", claim_id="SHARED", source_family_id="SF2"),
        query=replace(_trace().query, query_id="Q2", scenario_id="S2"),
    )
    development = _trace("T3", doc_id="MP008", claim_id="DEV", source_family_id="SFD")
    external = _trace("T4", doc_id="MP009", claim_id="EXT", source_family_id="SFE")

    rows, report = assign_grouped_splits(
        (build_a, build_b, development, external), seed="fixed", validation_fraction=0.5
    )
    by_id = {row.trace_id: row for row in rows}
    assert by_id["T1"].split == by_id["T2"].split
    assert by_id["T3"].split == DataSplit.DEVELOPMENT
    assert by_id["T4"].split == DataSplit.EXTERNAL_EVALUATION
    assert report.component_count == 3


def test_group_split_is_reproducible() -> None:
    rows = (_trace("T1"),)
    first, first_report = assign_grouped_splits(rows, seed="fixed")
    second, second_report = assign_grouped_splits(rows, seed="fixed")
    assert first == second
    assert first_report == second_report


def test_fixed_memory_split_groups_by_scenario_without_candidate_giant_component() -> None:
    same_scenario = replace(
        _trace("T2", doc_id="MP002", claim_id="C2", source_family_id="SF2"),
        query=replace(_trace().query, query_id="Q2", scenario_id="S-T1"),
    )
    first = replace(_trace("T1"), query=replace(_trace().query, scenario_id="S-T1"))
    independent = _trace("T3", doc_id="MP003", claim_id="C3", source_family_id="SF3")
    rows, report = assign_fixed_memory_query_splits(
        (first, same_scenario, independent), seed="fixed", validation_fraction=0.5
    )
    by_id = {row.trace_id: row for row in rows}
    assert by_id["T1"].split == by_id["T2"].split
    assert report.component_count == 2


def test_fixed_memory_split_preserves_zero_candidate_route_supervision() -> None:
    trace = _zero_candidate_trace()
    rows, report = assign_fixed_memory_query_splits((trace,), seed="fixed")

    assert len(rows) == 1
    assert rows[0].split in {DataSplit.TRAIN, DataSplit.VALIDATION}
    assert rows[0].document_group_ids == ()
    assert report.component_count == 1
    assert_training_trace_boundary(
        rows, split_mode="fixed_memory_query_generalization"
    )


def test_empty_document_groups_remain_forbidden_outside_zero_candidate_fixed_memory() -> None:
    zero = replace(_zero_candidate_trace(), split=DataSplit.TRAIN)
    with pytest.raises(ContractError, match="document_group_ids"):
        assert_training_trace_boundary(zero for _ in range(1))

    malformed_nonempty = replace(
        _trace(),
        claim_group_ids=(),
        document_group_ids=(),
        source_family_group_ids=(),
    )
    with pytest.raises(ContractError, match="non-empty fixed-memory"):
        assign_fixed_memory_query_splits((malformed_nonempty,))


def test_training_bundle_hard_rejects_external_evaluation_documents(tmp_path: Path) -> None:
    trace = replace(_trace(doc_id="MP009"), split=DataSplit.TRAIN)
    with pytest.raises(ContractError, match="non-training document"):
        write_teacher_trace_bundle(
            tmp_path,
            (trace,),
            dataset_id="D1",
            teacher_graph_id=trace.teacher_graph_id,
            teacher_graph_sha256="a" * 64,
            teacher_replay_id=trace.teacher_replay_id,
            teacher_replay_sha256="b" * 64,
            candidate_trace_sha256="c" * 64,
            candidate_trace_manifest_sha256="d" * 64,
            teacher_system_identity_sha256="e" * 64,
            split_protocol={"mode": "fixed_memory_query_generalization"},
            validation_report={
                "exactly_40_original_base_queries": True,
                "complete_four_slot_cards": True,
                "cited_selected_pointer_closure": True,
                "exact_original_trace_count": True,
                "unique_original_query_ids": True,
                "candidate_width_exact_32": True,
                "four_slot_card_schema": True,
                "route_card_closure": True,
                "explicit_three_action_costs": True,
                "known_fault_single_role_supervision": True,
            },
            purpose="training",
        )


def test_teacher_trace_bundle_round_trip_and_immutable_hash(tmp_path: Path) -> None:
    trace = replace(_trace(), split=DataSplit.TRAIN)
    kwargs = dict(
        dataset_id="D1",
        teacher_graph_id=trace.teacher_graph_id,
        teacher_graph_sha256="a" * 64,
        teacher_replay_id=trace.teacher_replay_id,
        teacher_replay_sha256="b" * 64,
        candidate_trace_sha256="c" * 64,
        candidate_trace_manifest_sha256="d" * 64,
        teacher_system_identity_sha256="e" * 64,
        split_protocol={
            "mode": "fixed_memory_query_generalization",
            "shared_memory_across_train_validation": True,
            "inductive_holdout_claim_allowed": False,
        },
        validation_report={
            "exactly_40_original_base_queries": True,
            "complete_four_slot_cards": True,
            "cited_selected_pointer_closure": True,
            "exact_original_trace_count": True,
            "unique_original_query_ids": True,
            "candidate_width_bounded_32": True,
            "four_slot_card_schema": True,
            "route_card_closure": True,
            "explicit_three_action_costs": True,
            "known_fault_single_role_supervision": True,
        },
        purpose="training",
    )
    manifest = write_teacher_trace_bundle(tmp_path, (trace,), **kwargs)
    # The synthetic helper is one row rather than the formal 40-row bundle;
    # its manifest flags exercise structural parsing, while the exact count is
    # independently enforced by the final freeze gate.
    rows, loaded_manifest = read_teacher_trace_bundle(tmp_path, purpose="training")
    assert rows == (trace,)
    assert loaded_manifest == manifest
    assert manifest["human_expert_reviewed"] is False
    assert manifest["candidate_trace"]["data_sha256"] == "c" * 64
    assert manifest["teacher_system_identity_sha256"] == "e" * 64
    assert write_teacher_trace_bundle(tmp_path, (trace,), **kwargs) == manifest

    changed = replace(trace, perturbation_id="changed")
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        write_teacher_trace_bundle(tmp_path, (changed,), **kwargs)


def test_compact_memory_round_trip_and_external_guard(tmp_path: Path) -> None:
    record = _memory()
    manifest = write_compact_evidence_memory_bundle(
        tmp_path,
        (record,),
        memory_id="M1",
        teacher_graph_id="TeacherGraph_RP3_v1",
        teacher_graph_sha256="a" * 64,
        teacher_system_identity_sha256="c" * 64,
        purpose="training",
    )
    rows, loaded_manifest = read_compact_evidence_memory_bundle(tmp_path, purpose="training")
    assert rows == (record,)
    assert loaded_manifest == manifest
    assert manifest["retrieval_free_claim_allowed"] is False

    external = _memory(doc_id="MP009", partition=DataSplit.EXTERNAL_EVALUATION)
    with pytest.raises(ContractError, match="training evidence memory"):
        write_compact_evidence_memory_bundle(
            tmp_path / "bad",
            (external,),
            memory_id="bad",
            teacher_graph_id="TeacherGraph_RP3_v1",
            teacher_graph_sha256="a" * 64,
            teacher_system_identity_sha256="c" * 64,
            purpose="training",
        )


def test_stable_hash_is_mapping_order_independent() -> None:
    assert stable_sha256({"a": 1, "b": [2, 3]}) == stable_sha256(
        {"b": [2, 3], "a": 1}
    )


def test_trace_memory_cross_reference_requires_every_candidate() -> None:
    trace = replace(_trace(), split=DataSplit.TRAIN)
    with pytest.raises(ContractError, match="missing evidence"):
        validate_trace_memory_references((trace,), (_memory(),))


def test_trace_memory_validates_card_role_fault_and_claim_closure() -> None:
    trace = replace(_trace(), split=DataSplit.TRAIN)
    unused = _memory(
        evidence_id="E2", claim_id="C2", memory_index=1
    )
    unused = replace(unused, evidence_text="无关候选证据。")
    validate_trace_memory_references((trace,), (_memory(), unused))

    wrong_role = replace(_memory(), role=DiagnosticRole.MAINTENANCE)
    with pytest.raises(ContractError, match="role mismatch"):
        validate_trace_memory_references((trace,), (wrong_role, unused))

    wrong_fault = replace(_memory(), fault_class_ids=("OTHER",))
    with pytest.raises(ContractError, match="scope authorization"):
        validate_trace_memory_references((trace,), (wrong_fault, unused))
    authorized = replace(
        trace,
        metadata={
            "automatic_fault_label_mismatch_selected_evidence_ids": ["E1"]
        },
    )
    validate_trace_memory_references((authorized,), (wrong_fault, unused))

    wrong_claim = replace(_memory(), claim_id="OMITTED")
    with pytest.raises(ContractError, match="omits cited claim"):
        validate_trace_memory_references((trace,), (wrong_claim, unused))


def test_fallback_or_abstain_card_must_be_fact_free() -> None:
    trace = _trace()
    for action in (RouteAction.FALLBACK, RouteAction.ABSTAIN):
        with pytest.raises(ContractError, match="fact|insufficient"):
            replace(trace, route=replace(trace.route, action=action))
