"""Synthetic contracts for RP3 tensorization, training manifests, and ONNX prep."""

from __future__ import annotations

from dataclasses import replace

import pytest

torch = pytest.importorskip("torch", reason="RP3 training contracts require PyTorch")

from src.research_point_3.artifacts import stable_sha256
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
from src.research_point_3.dataset import (
    FEATURE_BUNDLE_SCHEMA,
    ExplicitFeatureStore,
    TensorizationConfig,
    TensorizedTeacherDataset,
    assert_group_disjoint_splits,
    collate_teacher_batch,
    validate_development_sources,
    validate_training_sources,
)
from src.research_point_3.model import EvidenceControllerConfig
from src.research_point_3.onnx_export import (
    INT8_CALIBRATION_SCHEMA,
    NumpyInt8CalibrationDataReader,
    build_int8_calibration_input_bundle,
)
from src.research_point_3.teacher_freeze import TEACHER_FREEZE_ID, TEACHER_FREEZE_SCHEMA
from src.research_point_3.training import TrainingConfig, set_deterministic_seed


REPLAY_HASH = "b" * 64


def _card(evidence_id: str) -> DiagnosisCard:
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
                            text_zh="泵体出现异常振动。",
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
        card_id="C1",
        status=CardStatus.PARTIAL,
        fault_ids=("F01",),
        applicability_conditions=("运行状态",),
        slots=tuple(slots),
    )


def _trace(
    trace_id: str,
    split: DataSplit,
    *,
    scenario_id: str,
    evidence_id: str,
    doc_id: str,
) -> TeacherTrace:
    return TeacherTrace(
        trace_id=trace_id,
        query=QueryContext(
            query_id=f"Q-{trace_id}",
            question_zh="异常振动有哪些表现？",
            fault_id="F01",
            fault_name_zh="异常振动",
            requested_role=DiagnosticRole.FULL_CARD,
            scenario_id=scenario_id,
        ),
        candidate_evidence_ids=(evidence_id,),
        availability_mask=(True,),
        selection_budget=1,
        underfill_reason_codes=(),
        evidence_decisions=(
            TeacherEvidenceDecision(
                evidence_id=evidence_id,
                rank=1,
                teacher_score=0.9,
                support=SupportVerdict.DIRECT,
                selected=True,
            ),
        ),
        diagnosis_card=_card(evidence_id),
        route=RouteDecision(
            action=RouteAction.ANSWER,
            reason_codes=("supported",),
            estimated_student_cost=1.0,
            estimated_teacher_cost=8.0,
            estimated_error_cost=2.0,
            confidence=0.9,
        ),
        split=split,
        claim_group_ids=(f"claim-{evidence_id}",),
        document_group_ids=(doc_id,),
        source_family_group_ids=(f"family-{evidence_id}",),
        teacher_graph_id="TeacherGraph_RP3_v1",
        teacher_replay_id="replay-v1",
        metadata={
            "route_action_costs": {
                "answer": 1.0,
                "fallback": 8.0,
                "abstain": 2.0,
            }
        },
    )


def _record(evidence_id: str, split: DataSplit, doc_id: str) -> CompactEvidenceRecord:
    return CompactEvidenceRecord(
        evidence_id=evidence_id,
        claim_id=f"claim-{evidence_id}",
        head_label_zh="异常振动",
        relation="表现为",
        tail_label_zh="泵体振动",
        role=DiagnosticRole.SYMPTOM,
        fault_class_ids=("F01",),
        evidence_text="泵体出现异常振动。",
        provenance=EvidenceProvenance(
            doc_id=doc_id,
            physical_pdf_page=1,
            source_family_id=f"family-{evidence_id}",
        ),
        partition=split,
        memory_index=0,
        feature_vector=(0.1, 0.2, 0.3),
    )


def _features(trace_ids: tuple[str, ...], evidence_ids: tuple[str, ...]) -> ExplicitFeatureStore:
    payload = ExplicitFeatureStore.build_payload(
        query_features={trace_id: (1.0, 2.0) for trace_id in trace_ids},
        evidence_features={evidence_id: (0.1, 0.2, 0.3) for evidence_id in evidence_ids},
        query_dimension=2,
        evidence_dimension=3,
        encoder_manifest={"encoder_id": "external-test-encoder", "frozen": True},
    )
    return ExplicitFeatureStore.from_dict(payload)


def _manifests() -> tuple[dict, dict, dict]:
    freeze = {
        "schema": TEACHER_FREEZE_SCHEMA,
        "freeze_id": TEACHER_FREEZE_ID,
        "teacher_graph_id": "TeacherGraph_RP3_v1",
        "status": "frozen",
        "checks": [{"name": "all", "ok": True, "detail": "ready"}],
        "replay_artifacts": [
            {"path": "retrieval_replay.jsonl", "sha256": REPLAY_HASH}
        ],
        "immutable_graph_logical_sha256": "a" * 64,
        "teacher_system_identity_sha256": "c" * 64,
    }
    freeze["freeze_manifest_logical_sha256"] = stable_sha256(freeze)
    trace_manifest = {
        "teacher_graph": {
            "id": "TeacherGraph_RP3_v1",
            "sha256": freeze["immutable_graph_logical_sha256"],
        },
        "teacher_replay_sha256": REPLAY_HASH,
        "teacher_system_identity_sha256": freeze["teacher_system_identity_sha256"],
        "split_protocol": {"mode": "fixed_memory_query_generalization"},
    }
    memory_manifest = {
        "teacher_graph": {
            "id": "TeacherGraph_RP3_v1",
            "sha256": freeze["immutable_graph_logical_sha256"],
        },
        "teacher_system_identity_sha256": freeze["teacher_system_identity_sha256"],
    }
    return trace_manifest, memory_manifest, freeze


def test_explicit_feature_store_rejects_hash_and_dimension_mismatch() -> None:
    payload = ExplicitFeatureStore.build_payload(
        query_features={"T1": (1.0, 2.0)},
        evidence_features={"E1": (1.0, 2.0, 3.0)},
        query_dimension=2,
        evidence_dimension=3,
        encoder_manifest={"encoder_id": "external"},
    )
    assert payload["schema"] == FEATURE_BUNDLE_SCHEMA
    assert ExplicitFeatureStore.from_dict(payload).query_dimension == 2

    tampered = dict(payload)
    tampered["query_dimension"] = 3
    with pytest.raises(ContractError, match="SHA-256"):
        ExplicitFeatureStore.from_dict(tampered)


def test_group_level_split_blocks_shared_scenario_across_train_validation() -> None:
    train = _trace(
        "T1", DataSplit.TRAIN, scenario_id="S-SHARED", evidence_id="E1", doc_id="MP001"
    )
    validation = _trace(
        "T2",
        DataSplit.VALIDATION,
        scenario_id="S-SHARED",
        evidence_id="E2",
        doc_id="MP002",
    )
    with pytest.raises(ContractError, match="group leakage"):
        assert_group_disjoint_splits((train, validation))


def test_training_source_validation_requires_matching_frozen_teacher_and_replay() -> None:
    trace = _trace(
        "T1", DataSplit.TRAIN, scenario_id="S1", evidence_id="E1", doc_id="MP001"
    )
    record = _record("E1", DataSplit.TRAIN, "MP001")
    trace_manifest, memory_manifest, freeze = _manifests()

    assert len(
        validate_training_sources(
            (trace,), (record,), trace_manifest, memory_manifest, freeze
        )
    ) == 64

    bad_memory = dict(memory_manifest)
    bad_memory["teacher_graph"] = {
        "id": "TeacherGraph_RP3_v1",
        "sha256": "c" * 64,
    }
    with pytest.raises(ContractError, match="different teacher graphs"):
        validate_training_sources(
            (trace,), (record,), trace_manifest, bad_memory, freeze
        )


def test_development_source_validation_is_mp008_only_and_same_teacher() -> None:
    trace = _trace(
        "TD1",
        DataSplit.DEVELOPMENT,
        scenario_id="SD1",
        evidence_id="ED1",
        doc_id="MP008",
    )
    record = _record("ED1", DataSplit.DEVELOPMENT, "MP008")
    trace_manifest, memory_manifest, freeze = _manifests()
    trace_manifest = {**trace_manifest, "teacher_replay_sha256": "d" * 64}
    frozen_binding = (
        trace_manifest["teacher_graph"]["id"],
        trace_manifest["teacher_graph"]["sha256"],
    )
    assert len(
        validate_development_sources(
            (trace,),
            (record,),
            trace_manifest,
            memory_manifest,
            freeze,
            expected_graph_binding=frozen_binding,
        )
    ) == 64

    build_replay_manifest = {**trace_manifest, "teacher_replay_sha256": REPLAY_HASH}
    with pytest.raises(ContractError, match="distinct development replay"):
        validate_development_sources(
            (trace,),
            (record,),
            build_replay_manifest,
            memory_manifest,
            freeze,
            expected_graph_binding=frozen_binding,
        )

    wrong_split = replace(trace, split=DataSplit.VALIDATION)
    with pytest.raises(ContractError, match="DataSplit.DEVELOPMENT"):
        validate_development_sources(
            (wrong_split,),
            (record,),
            trace_manifest,
            memory_manifest,
            freeze,
            expected_graph_binding=frozen_binding,
        )

    wrong_graph = dict(memory_manifest)
    wrong_graph["teacher_graph"] = {
        "id": "TeacherGraph_RP3_v1",
        "sha256": "c" * 64,
    }
    with pytest.raises(ContractError, match="same frozen"):
        validate_development_sources(
            (trace,),
            (record,),
            trace_manifest,
            wrong_graph,
            freeze,
            expected_graph_binding=frozen_binding,
        )


def test_tensorizer_requires_explicit_three_action_counterfactual_costs() -> None:
    trace = _trace(
        "T1", DataSplit.TRAIN, scenario_id="S1", evidence_id="E1", doc_id="MP001"
    )
    missing_costs = replace(trace, metadata={})
    with pytest.raises(ContractError, match="explicitly declare"):
        TensorizedTeacherDataset(
            (missing_costs,),
            (_record("E1", DataSplit.TRAIN, "MP001"),),
            _features(("T1",), ("E1",)),
            TensorizationConfig(max_candidates=4),
        )


def test_fixed_width_tensorization_and_four_head_targets() -> None:
    trace = _trace(
        "T1", DataSplit.TRAIN, scenario_id="S1", evidence_id="E1", doc_id="MP001"
    )
    dataset = TensorizedTeacherDataset(
        (trace,),
        (_record("E1", DataSplit.TRAIN, "MP001"),),
        _features(("T1",), ("E1",)),
        TensorizationConfig(max_candidates=4, max_cardinality=3),
    )
    row = dataset[0]
    assert row["query_features"].shape == (2,)
    assert row["candidate_features"].shape == (4, 3)
    assert row["availability_mask"].tolist() == [True, False, False, False]
    assert row["support_labels"].tolist() == [1, -100, -100, -100]

    batch = collate_teacher_batch((row,))
    targets = batch["targets"]
    assert targets.teacher_rank_scores.shape == (1, 4)
    assert targets.field_state_labels.shape == (1, len(CARD_SLOT_ROLES))
    assert targets.cardinality_labels.shape == (1, len(CARD_SLOT_ROLES))
    assert targets.route_labels.shape == (1,)
    assert targets.route_action_costs.shape == (1, 3)


def test_tensorizer_never_generates_missing_features() -> None:
    trace = _trace(
        "T1", DataSplit.TRAIN, scenario_id="S1", evidence_id="E1", doc_id="MP001"
    )
    record = replace(
        _record("E1", DataSplit.TRAIN, "MP001"), feature_vector=()
    )
    feature_payload = ExplicitFeatureStore.build_payload(
        query_features={"T1": (1.0, 2.0)},
        evidence_features={},
        query_dimension=2,
        evidence_dimension=3,
        encoder_manifest={"encoder_id": "external"},
    )
    with pytest.raises(ContractError, match="no explicit feature"):
        TensorizedTeacherDataset(
            (trace,),
            (record,),
            ExplicitFeatureStore.from_dict(feature_payload),
            TensorizationConfig(max_candidates=4),
        )


def test_seed_contract_and_config_are_deterministic() -> None:
    set_deterministic_seed(17)
    first = torch.rand(4)
    set_deterministic_seed(17)
    second = torch.rand(4)
    assert torch.equal(first, second)
    assert EvidenceControllerConfig(query_dim=2, evidence_dim=3).query_dim == 2
    assert TrainingConfig(seed=17).num_workers == 0
    with pytest.raises(ValueError, match="num_workers=0"):
        TrainingConfig(num_workers=1)


def test_calibration_bundle_is_manifested_but_never_claims_quantization(tmp_path) -> None:
    pytest.importorskip("numpy")
    trace = _trace(
        "T1", DataSplit.VALIDATION, scenario_id="S1", evidence_id="E1", doc_id="MP001"
    )
    dataset = TensorizedTeacherDataset(
        (trace,),
        (_record("E1", DataSplit.VALIDATION, "MP001"),),
        _features(("T1",), ("E1",)),
        TensorizationConfig(max_candidates=4),
    )
    manifest = build_int8_calibration_input_bundle(
        dataset,
        output_dir=tmp_path,
        source_input_fingerprint="input-hash",
        max_samples=1,
    )
    assert manifest["schema"] == INT8_CALIBRATION_SCHEMA
    assert manifest["quantization_completed"] is False
    assert "quantization_not_run" in manifest["status"]

    reader = NumpyInt8CalibrationDataReader(
        tmp_path / "int8_calibration_manifest.json"
    )
    assert reader.get_next()["candidate_features"].shape == (1, 4, 3)
    assert reader.get_next() is None
    reader.rewind()
    assert reader.get_next() is not None
