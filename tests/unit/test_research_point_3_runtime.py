from __future__ import annotations

from dataclasses import replace

from src.research_point_3.artifacts import stable_sha256
from src.research_point_3.contracts import (
    CARD_SLOT_ROLES,
    CONTRACT_VERSION,
    CardFieldState,
    CompactEvidenceRecord,
    DataSplit,
    DiagnosticRole,
    EvidenceProvenance,
    QueryContext,
    RouteAction,
    SupportVerdict,
)
from src.research_point_3.renderer import (
    DeterministicDiagnosisCardRenderer,
    RenderFieldPlan,
)
from src.research_point_3.routing import (
    CostSensitiveRouter,
    RoutingCostProfile,
    RoutingSignals,
)
from src.research_point_3.tool_api import (
    ControllerEvidenceDecision,
    ControllerFieldPrediction,
    ControllerPrediction,
    EvidenceMemoryResolver,
    FrozenCandidateBucket,
    FrozenCandidateBucketRegistry,
    SelectPumpEvidenceRequest,
    SelectPumpEvidenceFacade,
    SelectPumpEvidenceTool,
    TOOL_API_VERSION,
    candidate_signature_sha256,
    select_pump_evidence_audit_schema,
    select_pump_evidence_tool_schema,
)


GRAPH_SHA = "a" * 64


def _query(role: DiagnosticRole = DiagnosticRole.FULL_CARD) -> QueryContext:
    return QueryContext(
        query_id="Q1",
        question_zh="泵异常振动时应如何辅助排查？",
        fault_id="F01",
        fault_name_zh="异常振动",
        requested_role=role,
        scenario_id="S1",
        operating_context=("泵运行期间",),
    )


def _record(
    evidence_id: str = "E1",
    *,
    role: DiagnosticRole = DiagnosticRole.SYMPTOM,
    memory_index: int = 0,
    text: str = "泵运行时振幅升高。",
) -> CompactEvidenceRecord:
    return CompactEvidenceRecord(
        evidence_id=evidence_id,
        claim_id=f"C-{evidence_id}",
        head_label_zh="异常振动",
        relation="manifests_as",
        tail_label_zh="振幅升高",
        role=role,
        fault_class_ids=("F01",),
        evidence_text=text,
        provenance=EvidenceProvenance(
            doc_id="MP001",
            physical_pdf_page=3,
            source_family_id="SF1",
        ),
        partition=DataSplit.TRAIN,
        memory_index=memory_index,
        feature_vector=(0.1, 0.2),
        evidence_contract_confidence=0.9,
    )


def _manifest(records: tuple[CompactEvidenceRecord, ...]) -> dict[str, object]:
    return {
        "artifact_type": "rp3_compact_evidence_memory",
        "contract_version": CONTRACT_VERSION,
        "memory_id": "M1",
        "record_count": len(records),
        "logical_sha256": stable_sha256([record.to_dict() for record in records]),
        "teacher_graph": {
            "id": "TeacherGraph_RP3_v1",
            "sha256": GRAPH_SHA,
        },
    }


def _request(
    records: tuple[CompactEvidenceRecord, ...],
    *,
    ids: tuple[str, ...] | None = None,
    mask: tuple[bool, ...] | None = None,
) -> SelectPumpEvidenceRequest:
    evidence_ids = ids or tuple(record.evidence_id for record in records)
    availability = mask or tuple(True for _ in evidence_ids)
    manifest = _manifest(records)
    return SelectPumpEvidenceRequest.create(
        query=_query(),
        candidate_evidence_ids=evidence_ids,
        availability_mask=availability,
        selection_budget=1,
        memory_id="M1",
        memory_logical_sha256=str(manifest["logical_sha256"]),
        teacher_graph_id="TeacherGraph_RP3_v1",
        teacher_graph_sha256=GRAPH_SHA,
    )


class _Controller:
    def __init__(
        self,
        *,
        selected_id: str | None = "E1",
        support: SupportVerdict = SupportVerdict.DIRECT,
        route_action: RouteAction = RouteAction.ANSWER,
        route_confidence: float = 0.99,
    ) -> None:
        self.selected_id = selected_id
        self.support = support
        self.route_action = route_action
        self.route_confidence = route_confidence
        # Test double for a controller whose threshold has been loaded from a
        # version-bound MP008 calibration artifact.
        self.minimum_route_confidence = 0.0

    def predict(self, *, query, candidates, selection_budget):
        decisions = []
        for rank, candidate in enumerate(candidates, start=1):
            selected = candidate.evidence_id == self.selected_id
            decisions.append(
                ControllerEvidenceDecision(
                    evidence_id=candidate.evidence_id,
                    rank=rank,
                    score=1.0 / rank,
                    support=self.support if selected else SupportVerdict.IRRELEVANT,
                    selected=selected,
                )
            )
        return ControllerPrediction(
            decisions=tuple(decisions),
            fields=tuple(
                ControllerFieldPrediction(
                    role=role,
                    state=(
                        CardFieldState.SUPPORTED
                        if role == DiagnosticRole.SYMPTOM and self.selected_id == "E1"
                        else CardFieldState.INSUFFICIENT
                    ),
                    cardinality=(
                        1
                        if role == DiagnosticRole.SYMPTOM and self.selected_id == "E1"
                        else 0
                    ),
                )
                for role in CARD_SLOT_ROLES
            ),
            route_action=self.route_action,
            route_confidence=self.route_confidence,
        )


def _tool(
    records: tuple[CompactEvidenceRecord, ...], controller: _Controller
) -> SelectPumpEvidenceTool:
    return SelectPumpEvidenceTool(
        controller=controller,
        resolver=EvidenceMemoryResolver(records, _manifest(records)),
    )


def test_cost_sensitive_router_uses_expected_loss_and_three_actions() -> None:
    router = CostSensitiveRouter()
    assert router.decide(
        RoutingSignals(0.99, 0.95, direct_support_count=1)
    ).action == RouteAction.ANSWER
    assert router.decide(
        RoutingSignals(0.20, 0.99, direct_support_count=1)
    ).action == RouteAction.FALLBACK
    assert router.decide(
        RoutingSignals(0.20, 0.20, direct_support_count=1)
    ).action == RouteAction.ABSTAIN

    # Even a confident teacher is not automatically invoked when its measured
    # cost exceeds review cost; this distinguishes routing from entropy-only.
    expensive_teacher = CostSensitiveRouter(
        RoutingCostProfile(teacher_compute_cost=100.0)
    )
    assert expensive_teacher.decide(
        RoutingSignals(0.20, 0.99, direct_support_count=1)
    ).action == RouteAction.ABSTAIN


def test_oracle_label_is_still_cost_sensitive() -> None:
    router = CostSensitiveRouter(
        RoutingCostProfile(teacher_compute_cost=100.0)
    )
    decision = router.label_from_oracle(
        student_output_acceptable=False,
        teacher_output_acceptable=True,
        direct_support_count=1,
    )
    assert decision.action == RouteAction.ABSTAIN
    assert decision.reason_codes[0] == "oracle_cost_sensitive_label"


def test_renderer_builds_exactly_four_rp2_slots_and_copies_only_direct_text() -> None:
    record = _record()
    renderer = DeterministicDiagnosisCardRenderer()
    card = renderer.render(
        query=_query(),
        records_by_id={record.evidence_id: record},
        decisions=(
            ControllerEvidenceDecision(
                evidence_id="E1",
                rank=1,
                score=0.9,
                support=SupportVerdict.DIRECT,
                selected=True,
            ),
        ),
        field_plan=tuple(
            RenderFieldPlan(
                role=role,
                state=(
                    CardFieldState.SUPPORTED
                    if role == DiagnosticRole.SYMPTOM
                    else CardFieldState.INSUFFICIENT
                ),
                cardinality=1 if role == DiagnosticRole.SYMPTOM else 0,
            )
            for role in CARD_SLOT_ROLES
        ),
    )
    assert tuple(slot.role for slot in card.slots) == CARD_SLOT_ROLES
    symptom = next(slot for slot in card.slots if slot.role == DiagnosticRole.SYMPTOM)
    assert symptom.items[0].text_zh == record.evidence_text
    assert len(card.slots) == 4
    shell = renderer.render_natural_language_shell(card)
    assert record.evidence_text in shell
    assert "请立即停机" not in shell
    assert "务必" not in shell


def test_tool_returns_grounded_answer_and_tool_schema() -> None:
    records = (_record(),)
    response = _tool(records, _Controller()).select_pump_evidence(_request(records))
    assert response.ok is True
    assert response.action == RouteAction.ANSWER
    assert response.diagnosis_card.cited_evidence_ids == ("E1",)
    assert tuple(item["evidence_id"] for item in response.selected_evidence) == ("E1",)
    assert response.selected_evidence[0]["support_probability"] == 1.0
    assert response.selected_evidence[0]["support_verdict"] == "direct"
    assert response.selected_evidence[0]["controller_rank"] == 1
    assert response.selected_evidence[0]["evidence_text"] in response.natural_language_shell

    schema = select_pump_evidence_tool_schema()
    assert schema["name"] == "select_pump_evidence"
    assert "teacher_graph_sha256" not in schema["parameters"]["properties"]
    assert "candidate_signature_sha256" not in schema["parameters"]["properties"]
    audit_schema = select_pump_evidence_audit_schema()
    assert audit_schema["parameters"]["properties"]["tool_api_version"]["const"] == TOOL_API_VERSION


def test_public_facade_injects_frozen_candidates_and_hashes_server_side() -> None:
    records = (_record(),)
    resolver = EvidenceMemoryResolver(records, _manifest(records))
    bucket = FrozenCandidateBucket(
        fault_id="F01", role=DiagnosticRole.SYMPTOM, evidence_ids=("E1",)
    )
    registry = FrozenCandidateBucketRegistry(
        buckets=(bucket,),
        manifest={
            "artifact_type": "rp3_frozen_candidate_bucket_registry",
            "contract_version": CONTRACT_VERSION,
            "bucket_count": 1,
            "memory": {
                "id": resolver.manifest["memory_id"],
                "logical_sha256": resolver.manifest["logical_sha256"],
            },
            "teacher_graph": resolver.manifest["teacher_graph"],
            "logical_sha256": stable_sha256(
                [{"fault_id": "F01", "role": "symptom", "evidence_ids": ["E1"]}]
            ),
        },
        resolver=resolver,
    )
    facade = SelectPumpEvidenceFacade(
        tool=SelectPumpEvidenceTool(controller=_Controller(), resolver=resolver),
        registry=registry,
    )
    response = facade(
        question="泵异常振动时如何辅助排查？",
        fault_id="F01",
        fault_name="异常振动",
        role="symptom",
        scenario_id="S1",
    )
    assert response.action == RouteAction.ANSWER


def test_unknown_id_fails_closed_without_exposing_factual_text() -> None:
    records = (_record(),)
    response = _tool(records, _Controller(selected_id="E404")).select_pump_evidence(
        _request(records, ids=("E404",), mask=(True,))
    )
    assert response.ok is False
    assert response.action == RouteAction.ABSTAIN
    assert response.selected_evidence == ()
    assert response.natural_language_shell == ""
    assert response.error_codes == ("unknown_evidence_id",)


def test_unavailable_selected_id_fails_closed() -> None:
    records = (_record(),)
    response = _tool(records, _Controller()).select_pump_evidence(
        _request(records, mask=(False,))
    )
    assert response.ok is False
    assert response.action == RouteAction.ABSTAIN
    assert response.error_codes == ("unavailable_evidence_id",)


def test_hash_and_version_mismatch_fail_closed() -> None:
    records = (_record(),)
    tool = _tool(records, _Controller())
    request = _request(records)
    bad_hash = replace(request, memory_logical_sha256="b" * 64)
    response = tool.select_pump_evidence(bad_hash)
    assert response.ok is False
    assert response.action == RouteAction.ABSTAIN
    assert response.error_codes == ("artifact_binding_mismatch",)

    bad_version = replace(request, contract_version="old_contract")
    response = tool.select_pump_evidence(bad_version)
    assert response.ok is False
    assert response.action == RouteAction.ABSTAIN
    assert response.error_codes == ("version_mismatch",)


def test_memory_manifest_hash_and_contract_version_fail_before_use() -> None:
    records = (_record(),)
    bad_hash = _manifest(records)
    bad_hash["logical_sha256"] = "b" * 64
    try:
        EvidenceMemoryResolver(records, bad_hash)
    except Exception as exc:
        assert "logical hash mismatch" in str(exc)
    else:
        raise AssertionError("resolver accepted a memory hash mismatch")

    bad_version = _manifest(records)
    bad_version["contract_version"] = "old_contract"
    try:
        EvidenceMemoryResolver(records, bad_version)
    except Exception as exc:
        assert "contract version mismatch" in str(exc)
    else:
        raise AssertionError("resolver accepted a memory version mismatch")


def test_candidate_signature_binds_mask_and_ids() -> None:
    signature = candidate_signature_sha256(("E1",), (True,))
    assert signature != candidate_signature_sha256(("E1",), (False,))
    assert signature != candidate_signature_sha256(("E2",), (True,))


def test_fallback_response_contains_no_student_evidence_packet() -> None:
    records = (_record(),)
    controller = _Controller(route_action=RouteAction.FALLBACK)
    response = _tool(records, controller).select_pump_evidence(_request(records))
    assert response.action == RouteAction.FALLBACK
    assert response.selected_evidence == ()
    assert response.diagnosis_card.cited_evidence_ids == ()
    assert response.natural_language_shell == ""


def test_guard_never_upgrades_lec_fallback_or_abstain_to_answer() -> None:
    records = (_record(),)
    for action in (RouteAction.FALLBACK, RouteAction.ABSTAIN):
        response = _tool(records, _Controller(route_action=action)).select_pump_evidence(
            _request(records)
        )
        assert response.action == action
        assert response.selected_evidence == ()

    expensive_student = SelectPumpEvidenceTool(
        controller=_Controller(route_action=RouteAction.ANSWER),
        resolver=EvidenceMemoryResolver(records, _manifest(records)),
        router=CostSensitiveRouter(
            RoutingCostProfile(student_compute_cost=20.0, abstain_and_review_cost=12.0)
        ),
    )
    response = expensive_student.select_pump_evidence(_request(records))
    assert response.action == RouteAction.FALLBACK


def test_controller_prediction_requires_all_four_unique_field_outputs() -> None:
    try:
        ControllerPrediction(
            decisions=(),
            fields=(
                ControllerFieldPrediction(
                    role=DiagnosticRole.SYMPTOM,
                    state=CardFieldState.INSUFFICIENT,
                    cardinality=0,
                ),
            ),
            route_action=RouteAction.ABSTAIN,
            route_confidence=0.9,
        )
    except Exception as exc:
        assert "every frozen card slot" in str(exc)
    else:
        raise AssertionError("controller accepted an incomplete field-head output")


def test_field_cardinality_mismatch_and_context_selection_fail_closed() -> None:
    records = (_record(),)

    class _Mismatch(_Controller):
        def predict(self, *, query, candidates, selection_budget):
            prediction = super().predict(
                query=query, candidates=candidates, selection_budget=selection_budget
            )
            return replace(
                prediction,
                fields=tuple(
                    replace(field, cardinality=0, state=CardFieldState.INSUFFICIENT)
                    if field.role == DiagnosticRole.SYMPTOM
                    else field
                    for field in prediction.fields
                ),
            )

    response = _tool(records, _Mismatch()).select_pump_evidence(_request(records))
    assert response.action == RouteAction.ABSTAIN
    assert response.error_codes == ("invalid_controller_output",)

    context = (_record(role=DiagnosticRole.CONTEXT),)
    response = _tool(context, _Controller()).select_pump_evidence(_request(context))
    assert response.action == RouteAction.ABSTAIN
    assert response.error_codes == ("invalid_controller_output",)


def test_field_head_stop_prevents_renderer_from_filling_available_evidence() -> None:
    records = (_record(),)

    class _Stop(_Controller):
        def predict(self, *, query, candidates, selection_budget):
            prediction = super().predict(
                query=query, candidates=candidates, selection_budget=selection_budget
            )
            return replace(
                prediction,
                decisions=tuple(replace(row, selected=False) for row in prediction.decisions),
                fields=tuple(
                    replace(field, state=CardFieldState.INSUFFICIENT, cardinality=0)
                    for field in prediction.fields
                ),
            )

    response = _tool(records, _Stop()).select_pump_evidence(_request(records))
    assert response.action == RouteAction.FALLBACK
    assert response.diagnosis_card.cited_evidence_ids == ()
    assert response.selected_evidence == ()
