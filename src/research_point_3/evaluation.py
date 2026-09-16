"""Model-agnostic evaluation for RP3 controller outputs and selective routing."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .contracts import ContractError, RouteAction


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def pointer_metrics(
    predicted_ids: Iterable[str],
    teacher_ids: Iterable[str],
) -> dict[str, float]:
    predicted = tuple(dict.fromkeys(str(value) for value in predicted_ids))
    teacher = tuple(dict.fromkeys(str(value) for value in teacher_ids))
    predicted_set, teacher_set = set(predicted), set(teacher)
    matched = len(predicted_set & teacher_set)
    precision = _safe_div(matched, len(predicted_set))
    recall = _safe_div(matched, len(teacher_set))
    f1 = _safe_div(2 * precision * recall, precision + recall)
    dcg = sum(
        (1.0 if evidence_id in teacher_set else 0.0) / math.log2(rank + 2)
        for rank, evidence_id in enumerate(predicted)
    )
    ideal = sum(1.0 / math.log2(rank + 2) for rank in range(min(len(teacher), len(predicted))))
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "ndcg": _safe_div(dcg, ideal),
    }


def binary_classification_metrics(
    probabilities: Sequence[float],
    labels: Sequence[int | bool],
    *,
    threshold: float = 0.5,
) -> dict[str, float]:
    if len(probabilities) != len(labels) or not probabilities:
        raise ContractError("probabilities and labels must have equal non-zero length")
    normalized_labels = [int(value) for value in labels]
    if any(value not in (0, 1) for value in normalized_labels):
        raise ContractError("binary labels must contain only 0/1")
    if any(not 0.0 <= float(value) <= 1.0 for value in probabilities):
        raise ContractError("probabilities must be in [0, 1]")
    predictions = [float(value) >= threshold for value in probabilities]
    tp = sum(prediction and label for prediction, label in zip(predictions, normalized_labels))
    fp = sum(prediction and not label for prediction, label in zip(predictions, normalized_labels))
    fn = sum(not prediction and label for prediction, label in zip(predictions, normalized_labels))
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    return {
        "precision": precision,
        "recall": recall,
        "f1": _safe_div(2 * precision * recall, precision + recall),
        "brier": sum(
            (float(probability) - label) ** 2
            for probability, label in zip(probabilities, normalized_labels)
        )
        / len(labels),
    }


def intervention_direction_consistency(
    teacher_deltas: Sequence[float], student_deltas: Sequence[float]
) -> float:
    if len(teacher_deltas) != len(student_deltas) or not teacher_deltas:
        raise ContractError("intervention deltas must have equal non-zero length")

    def sign(value: float) -> int:
        return 1 if value > 0 else -1 if value < 0 else 0

    return sum(
        sign(float(teacher)) == sign(float(student))
        for teacher, student in zip(teacher_deltas, student_deltas)
    ) / len(teacher_deltas)


def route_regret(
    predicted_actions: Sequence[RouteAction | str],
    costs: Sequence[Mapping[RouteAction | str, float]],
) -> dict[str, float]:
    if len(predicted_actions) != len(costs) or not costs:
        raise ContractError("route actions and costs must have equal non-zero length")
    regrets = []
    for action, row in zip(predicted_actions, costs):
        normalized = {RouteAction(str(key)): float(value) for key, value in row.items()}
        if set(normalized) != set(RouteAction):
            raise ContractError("each route-cost row must define all three actions")
        selected = RouteAction(str(action))
        regrets.append(normalized[selected] - min(normalized.values()))
    return {
        "mean_regret": sum(regrets) / len(regrets),
        "maximum_regret": max(regrets),
        "zero_regret_rate": sum(abs(value) < 1e-12 for value in regrets) / len(regrets),
    }


def selective_risk_curve(
    confidences: Sequence[float],
    losses: Sequence[float],
) -> list[dict[str, float]]:
    if len(confidences) != len(losses) or not losses:
        raise ContractError("selective-risk inputs must have equal non-zero length")
    rows = sorted(
        ((float(confidence), float(loss)) for confidence, loss in zip(confidences, losses)),
        reverse=True,
    )
    if any(not 0.0 <= confidence <= 1.0 for confidence, _ in rows):
        raise ContractError("confidence must be in [0, 1]")
    if any(not 0.0 <= loss <= 1.0 for _, loss in rows):
        raise ContractError("contract loss must be in [0, 1]")
    total = len(rows)
    cumulative = 0.0
    curve = []
    for index, (confidence, loss) in enumerate(rows, start=1):
        cumulative += loss
        curve.append(
            {
                "coverage": index / total,
                "risk": cumulative / index,
                "threshold": confidence,
            }
        )
    return curve


def aurc(curve: Sequence[Mapping[str, float]]) -> float:
    if not curve:
        raise ContractError("AURC requires a non-empty risk-coverage curve")
    area = 0.0
    previous_coverage = 0.0
    for point in curve:
        coverage = float(point["coverage"])
        risk = float(point["risk"])
        if coverage < previous_coverage:
            raise ContractError("risk-coverage curve must be sorted by coverage")
        area += (coverage - previous_coverage) * risk
        previous_coverage = coverage
    return area

