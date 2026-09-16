from __future__ import annotations

from src.research_point_3.evaluation import (
    aurc,
    intervention_direction_consistency,
    pointer_metrics,
    route_regret,
    selective_risk_curve,
)


def test_pointer_metrics_penalize_wrong_and_missing_ids() -> None:
    metrics = pointer_metrics(["E1", "X"], ["E1", "E2"])
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert 0.0 < metrics["ndcg"] < 1.0


def test_intervention_consistency_compares_direction() -> None:
    assert intervention_direction_consistency([-1, 1, 0], [-0.2, 0.4, 0]) == 1.0


def test_route_regret_uses_observed_action_cost_not_entropy() -> None:
    result = route_regret(
        ["answer", "fallback"],
        [
            {"answer": 3.0, "fallback": 1.0, "abstain": 5.0},
            {"answer": 4.0, "fallback": 2.0, "abstain": 1.0},
        ],
    )
    assert result["mean_regret"] == 1.5


def test_selective_curve_and_aurc_are_bounded() -> None:
    curve = selective_risk_curve([0.9, 0.8, 0.2], [0.0, 1.0, 1.0])
    assert curve[0]["risk"] == 0.0
    assert 0.0 <= aurc(curve) <= 1.0
