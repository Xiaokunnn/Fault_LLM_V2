"""Executable safety contracts for the RP3 lightweight evidence controller.

These tests are intentionally synthetic: they validate tensor alignment,
availability interventions, safe pointer decoding, and loss composition without
loading or executing a language model.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch", reason="RP3 model tests require optional PyTorch")

from src.research_point_3.contracts import CardFieldState, DiagnosticRole, RouteAction
from src.research_point_3.decoding import decode_evidence_controller_output
from src.research_point_3.losses import (
    EvidenceControllerTargets,
    LossWeights,
    compute_evidence_controller_loss,
    multi_temperature_listwise_kd,
)
from src.research_point_3.model import (
    CARD_FIELD_ROLES,
    CARD_FIELD_STATES,
    ROUTE_ACTIONS,
    CardFieldStateIndex,
    EvidenceControllerConfig,
    EvidenceControllerOutput,
    LightweightEvidenceController,
    RouteActionIndex,
)


def _controller() -> LightweightEvidenceController:
    return LightweightEvidenceController(
        EvidenceControllerConfig(
            query_dim=4,
            evidence_dim=3,
            hidden_dim=8,
            max_cardinality=2,
            dropout=0.0,
        )
    )


def test_four_heads_align_and_mask_unavailable_candidates_fail_closed() -> None:
    controller = _controller()
    output = controller(
        query_features=torch.zeros(2, 4),
        candidate_features=torch.zeros(2, 3, 3),
        availability_mask=torch.tensor(
            [[True, False, True], [False, False, False]]
        ),
        selection_budget=torch.tensor([2, 2]),
    )

    assert output.rank_logits.shape == (2, 3)
    assert output.support_logits.shape == (2, 3)
    assert output.field_state_logits.shape == (
        2,
        len(CARD_FIELD_ROLES),
        len(CARD_FIELD_STATES),
    )
    assert output.cardinality_logits.shape == (2, len(CARD_FIELD_ROLES), 3)
    assert output.route_logits.shape == (2, len(ROUTE_ACTIONS))

    floor = torch.finfo(output.rank_logits.dtype).min
    assert output.rank_logits[0, 1].item() == floor
    assert output.support_logits[0, 1].item() == floor
    assert torch.equal(
        output.masked_rank_probabilities()[1], torch.zeros(3)
    )

    # Total evidence removal cannot result in an answer or a supported/conflict
    # diagnosis-card field, regardless of learned head biases.
    assert output.route_logits[1, RouteActionIndex.ANSWER].item() == floor
    assert (
        output.field_state_logits[1, :, CardFieldStateIndex.SUPPORTED] == floor
    ).all()
    assert (
        output.field_state_logits[1, :, CardFieldStateIndex.CONFLICT] == floor
    ).all()


def test_parameter_report_is_exact_and_exposes_storage_estimates() -> None:
    controller = _controller()
    exact = sum(parameter.numel() for parameter in controller.parameters())
    report = controller.parameter_report()

    assert exact > 0
    assert controller.parameter_count() == exact
    assert controller.parameter_count(trainable_only=True) == exact
    assert report == {
        "total_parameters": exact,
        "trainable_parameters": exact,
        "estimated_fp32_bytes": exact * 4,
        "estimated_fp16_bytes": exact * 2,
        "estimated_int8_bytes": exact,
    }


def _manual_output(
    *,
    candidate_mask: tuple[bool, ...] = (True, False, True, True),
) -> EvidenceControllerOutput:
    field_states = torch.full((1, len(CARD_FIELD_ROLES), len(CARD_FIELD_STATES)), -8.0)
    field_states[:, :, CardFieldStateIndex.SUPPORTED] = 8.0
    cardinalities = torch.full((1, len(CARD_FIELD_ROLES), 4), -8.0)
    cardinalities[:, :, 2] = 8.0
    route = torch.full((1, len(ROUTE_ACTIONS)), -8.0)
    route[:, RouteActionIndex.ANSWER] = 8.0
    return EvidenceControllerOutput(
        rank_logits=torch.tensor([[9.0, 100.0, 8.0, 7.0]]),
        support_logits=torch.tensor([[9.0, 9.0, -9.0, 9.0]]),
        field_state_logits=field_states,
        cardinality_logits=cardinalities,
        route_logits=route,
        availability_mask=torch.tensor([candidate_mask]),
    )


def test_decoder_rejects_unknown_unavailable_and_duplicate_ids() -> None:
    decision = decode_evidence_controller_output(
        _manual_output(),
        ["E1", "E2", "UNKNOWN", "E3"],
        [
            DiagnosticRole.SYMPTOM,
            DiagnosticRole.SYMPTOM,
            DiagnosticRole.CONTEXT,
            DiagnosticRole.SYMPTOM,
        ],
        {"E1", "E2", "E3"},
        selection_budget=3,
        support_threshold=0.5,
    )[0]

    assert decision.selected_evidence_ids == ("E1", "E3")
    assert "E2" not in decision.selected_evidence_ids  # known but unavailable
    assert "UNKNOWN" not in decision.selected_evidence_ids
    assert set(decision.rejected_evidence_ids) == {"E2", "UNKNOWN"}
    assert decision.route_action == RouteAction.ANSWER
    assert "active_underfill" in decision.reason_codes
    assert all(field.cardinality <= 2 for field in decision.card_fields)


def test_decoder_refuses_answer_when_no_id_resolves_in_frozen_memory() -> None:
    decision = decode_evidence_controller_output(
        _manual_output(candidate_mask=(True, True, True, True)),
        ["U1", "U2", "U3", "U4"],
        [DiagnosticRole.SYMPTOM] * 4,
        set(),
        selection_budget=2,
    )[0]

    assert decision.selected_evidence_ids == ()
    assert decision.route_action == RouteAction.ABSTAIN
    assert "no_known_available_evidence" in decision.reason_codes
    assert all(
        field.state not in {CardFieldState.SUPPORTED, CardFieldState.CONFLICT}
        for field in decision.card_fields
    )


def _targets(batch_size: int = 2) -> EvidenceControllerTargets:
    return EvidenceControllerTargets(
        teacher_rank_scores=torch.tensor(
            [[3.0, 2.0, 1.0], [1.0, 3.0, 2.0]][:batch_size]
        ),
        support_labels=torch.tensor(
            [[1, 0, 0], [0, 1, 0]][:batch_size]
        ),
        field_state_labels=torch.full(
            (batch_size, len(CARD_FIELD_ROLES)),
            CardFieldStateIndex.INSUFFICIENT,
            dtype=torch.long,
        ),
        cardinality_labels=torch.zeros(
            batch_size, len(CARD_FIELD_ROLES), dtype=torch.long
        ),
        route_labels=torch.tensor(
            [RouteActionIndex.ANSWER, RouteActionIndex.ABSTAIN][:batch_size]
        ),
        route_action_costs=torch.tensor(
            [[0.2, 1.0, 2.0], [5.0, 1.0, 0.2]][:batch_size]
        ),
    )


def test_composite_loss_covers_kd_support_card_route_intervention_calibration() -> None:
    controller = _controller()
    query = torch.randn(2, 4)
    candidates = torch.randn(2, 3, 3)
    original = controller(
        query,
        candidates,
        torch.tensor([[True, True, True], [True, True, True]]),
        selection_budget=torch.tensor([2, 2]),
    )
    intervened = controller(
        query,
        candidates,
        torch.tensor([[True, False, True], [False, False, False]]),
        selection_budget=torch.tensor([1, 0]),
    )

    losses = compute_evidence_controller_loss(
        original,
        _targets(),
        weights=LossWeights(),
        temperatures=(1.0, 2.0, 4.0),
        intervention_pair=(intervened, _targets()),
    )

    assert set(losses.as_dict()) == {
        "total",
        "ranking",
        "support",
        "field_state",
        "cardinality",
        "route",
        "intervention",
        "calibration",
    }
    assert all(torch.isfinite(value) for value in losses.as_dict().values())
    assert losses.intervention.item() >= 0
    assert losses.calibration.item() >= 0


def test_listwise_kd_is_zero_for_fully_removed_evidence_set() -> None:
    loss = multi_temperature_listwise_kd(
        torch.zeros(2, 3),
        torch.ones(2, 3),
        torch.zeros(2, 3, dtype=torch.bool),
        temperatures=(1.0, 3.0),
    )
    assert loss.item() == pytest.approx(0.0)


def test_enum_index_orders_are_derived_from_frozen_contracts() -> None:
    assert ROUTE_ACTIONS[RouteActionIndex.ANSWER] == RouteAction.ANSWER.value
    assert ROUTE_ACTIONS[RouteActionIndex.FALLBACK] == RouteAction.FALLBACK.value
    assert ROUTE_ACTIONS[RouteActionIndex.ABSTAIN] == RouteAction.ABSTAIN.value
    assert (
        CARD_FIELD_STATES[CardFieldStateIndex.INSUFFICIENT]
        == CardFieldState.INSUFFICIENT.value
    )
