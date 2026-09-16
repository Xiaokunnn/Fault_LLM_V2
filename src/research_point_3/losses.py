"""Multi-objective distillation losses for the lightweight evidence controller."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .model import EvidenceControllerOutput, require_torch

try:  # See model.py for the optional-dependency policy.
    import torch
    import torch.nn.functional as F
    from torch import Tensor
except ImportError:  # pragma: no cover
    torch = None
    F = None
    Tensor = Any


IGNORE_INDEX = -100


@dataclass(frozen=True)
class EvidenceControllerTargets:
    """Aligned supervision exported from a validated :class:`TeacherTrace` batch."""

    teacher_rank_scores: Tensor
    support_labels: Tensor
    field_state_labels: Tensor
    cardinality_labels: Tensor
    route_labels: Tensor
    route_action_costs: Tensor | None = None


@dataclass(frozen=True)
class LossWeights:
    """Weights for the named objectives reported by the training loop."""

    ranking: float = 1.0
    support: float = 1.0
    field_state: float = 1.0
    cardinality: float = 1.0
    route: float = 1.0
    intervention: float = 0.5
    calibration: float = 0.1

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if float(value) < 0:
                raise ValueError(f"loss weight {name} must be >= 0")


@dataclass
class EvidenceControllerLoss:
    """Differentiable total plus detached-friendly named components."""

    total: Tensor
    ranking: Tensor
    support: Tensor
    field_state: Tensor
    cardinality: Tensor
    route: Tensor
    intervention: Tensor
    calibration: Tensor

    def as_dict(self, *, detach: bool = False) -> dict[str, Tensor]:
        result = {
            "total": self.total,
            "ranking": self.ranking,
            "support": self.support,
            "field_state": self.field_state,
            "cardinality": self.cardinality,
            "route": self.route,
            "intervention": self.intervention,
            "calibration": self.calibration,
        }
        if detach:
            return {name: value.detach() for name, value in result.items()}
        return result


def _zero(reference: Tensor) -> Tensor:
    # Masked logits can equal finfo.min; summing them first overflows to -inf.
    return (reference * 0.0).sum()


def _check_temperatures(temperatures: Sequence[float]) -> tuple[float, ...]:
    values = tuple(float(value) for value in temperatures)
    if not values or any(value <= 0 for value in values):
        raise ValueError("temperatures must contain one or more values > 0")
    return values


def multi_temperature_listwise_kd(
    student_logits: Tensor,
    teacher_scores: Tensor,
    availability_mask: Tensor,
    *,
    temperatures: Sequence[float] = (1.0, 2.0, 4.0),
) -> Tensor:
    """Average listwise KL at several temperatures over available candidates.

    Rows with no available candidates contribute zero rather than producing NaN.
    Multiplication by ``T^2`` follows the standard distillation gradient scaling.
    """

    require_torch()
    values = _check_temperatures(temperatures)
    if student_logits.shape != teacher_scores.shape:
        raise ValueError("student_logits and teacher_scores must have the same shape")
    if availability_mask.shape != student_logits.shape:
        raise ValueError("availability_mask must align with ranking tensors")
    mask = availability_mask.to(device=student_logits.device, dtype=torch.bool)
    valid_rows = mask.any(dim=-1)
    if not torch.any(valid_rows):
        return _zero(student_logits)
    floor = torch.finfo(student_logits.dtype).min
    student = torch.where(mask, student_logits, torch.full_like(student_logits, floor))
    teacher = teacher_scores.to(device=student_logits.device, dtype=student_logits.dtype)
    teacher = torch.where(mask, teacher, torch.full_like(teacher, floor))
    losses = []
    for temperature in values:
        student_log_prob = F.log_softmax(student[valid_rows] / temperature, dim=-1)
        teacher_prob = F.softmax(teacher[valid_rows] / temperature, dim=-1)
        losses.append(
            F.kl_div(student_log_prob, teacher_prob, reduction="batchmean")
            * (temperature**2)
        )
    return torch.stack(losses).mean()


def masked_support_bce(
    support_logits: Tensor,
    support_labels: Tensor,
    availability_mask: Tensor,
) -> Tensor:
    """Binary support loss, ignoring unavailable and ``IGNORE_INDEX`` positions."""

    require_torch()
    if support_logits.shape != support_labels.shape:
        raise ValueError("support_logits and support_labels must have the same shape")
    if availability_mask.shape != support_logits.shape:
        raise ValueError("availability_mask must align with support tensors")
    labels = support_labels.to(device=support_logits.device)
    active = availability_mask.to(device=support_logits.device, dtype=torch.bool)
    active = active & (labels != IGNORE_INDEX)
    if not torch.any(active):
        return _zero(support_logits)
    targets = labels[active].to(support_logits.dtype)
    if torch.any((targets < 0) | (targets > 1)):
        raise ValueError("active support labels must be binary 0/1")
    return F.binary_cross_entropy_with_logits(support_logits[active], targets)


def masked_cross_entropy(
    logits: Tensor,
    labels: Tensor,
    *,
    ignore_index: int = IGNORE_INDEX,
    class_weights: Tensor | None = None,
) -> Tensor:
    """Cross entropy that safely returns zero when every target is ignored."""

    require_torch()
    expected = logits.shape[:-1]
    if labels.shape != expected:
        raise ValueError(f"labels must have shape {expected}, got {tuple(labels.shape)}")
    flat_logits = logits.reshape(-1, logits.shape[-1])
    flat_labels = labels.to(device=logits.device, dtype=torch.long).reshape(-1)
    active = flat_labels != ignore_index
    if not torch.any(active):
        return _zero(logits)
    weights = None
    if class_weights is not None:
        if class_weights.numel() != logits.shape[-1]:
            raise ValueError("class_weights length must equal the number of classes")
        weights = class_weights.to(device=logits.device, dtype=logits.dtype)
    return F.cross_entropy(flat_logits[active], flat_labels[active], weight=weights)


def cost_sensitive_route_loss(
    route_logits: Tensor,
    route_labels: Tensor,
    *,
    route_action_costs: Tensor | None = None,
    class_weights: Tensor | None = None,
    expected_cost_weight: float = 1.0,
) -> Tensor:
    """Route classification plus differentiable expected deployment cost.

    ``route_action_costs[b, a]`` is the externally declared cost of taking action
    ``a`` for row ``b``.  It may combine latency/call cost and estimated error
    cost, but must be computed outside this function and remain auditable.
    """

    require_torch()
    if expected_cost_weight < 0:
        raise ValueError("expected_cost_weight must be >= 0")
    labels = route_labels.to(device=route_logits.device, dtype=torch.long)
    active = labels != IGNORE_INDEX
    classification = masked_cross_entropy(
        route_logits, labels, class_weights=class_weights
    )
    if route_action_costs is None or expected_cost_weight == 0:
        return classification
    if route_action_costs.shape != route_logits.shape:
        raise ValueError("route_action_costs must have the same shape as route_logits")
    costs = route_action_costs.to(device=route_logits.device, dtype=route_logits.dtype)
    if torch.any(~torch.isfinite(costs)) or torch.any(costs < 0):
        raise ValueError("route_action_costs must be finite and non-negative")
    if not torch.any(active):
        return _zero(route_logits)
    expected_cost = (
        torch.softmax(route_logits[active], dim=-1) * costs[active]
    ).sum(dim=-1).mean()
    return classification + float(expected_cost_weight) * expected_cost


def calibration_brier_loss(
    output: EvidenceControllerOutput,
    targets: EvidenceControllerTargets,
) -> Tensor:
    """Mean support/field/cardinality/route Brier score on labelled decisions."""

    require_torch()
    terms: list[Tensor] = []
    support_labels = targets.support_labels.to(device=output.support_logits.device)
    active_support = output.availability_mask & (support_labels != IGNORE_INDEX)
    if torch.any(active_support):
        support_target = support_labels[active_support].to(output.support_logits.dtype)
        terms.append(
            torch.mean(
                (torch.sigmoid(output.support_logits[active_support]) - support_target) ** 2
            )
        )

    multiclass_pairs = (
        (output.field_state_logits, targets.field_state_labels),
        (output.cardinality_logits, targets.cardinality_labels),
        (output.route_logits, targets.route_labels),
    )
    for logits, labels in multiclass_pairs:
        labels = labels.to(device=logits.device, dtype=torch.long)
        flat_labels = labels.reshape(-1)
        flat_logits = logits.reshape(-1, logits.shape[-1])
        active = flat_labels != IGNORE_INDEX
        if torch.any(active):
            active_logits = flat_logits[active]
            # A structurally masked class uses the minimum finite logit.  If a
            # malformed teacher label points to that class, omit it from the
            # calibration term just as CE would have to do at data validation.
            selected_logits = active_logits.gather(
                1, flat_labels[active].unsqueeze(-1)
            ).squeeze(-1)
            structurally_valid = selected_logits > torch.finfo(logits.dtype).min
            active_logits = active_logits[structurally_valid]
            active_labels = flat_labels[active][structurally_valid]
            if active_labels.numel() == 0:
                continue
            one_hot = F.one_hot(
                active_labels, num_classes=flat_logits.shape[-1]
            ).to(flat_logits.dtype)
            terms.append(
                ((torch.softmax(active_logits, dim=-1) - one_hot) ** 2)
                .sum(dim=-1)
                .mean()
            )
    if not terms:
        return _zero(output.route_logits)
    return torch.stack(terms).mean()


def _supervised_components(
    output: EvidenceControllerOutput,
    targets: EvidenceControllerTargets,
    *,
    temperatures: Sequence[float],
    route_class_weights: Tensor | None,
    expected_route_cost_weight: float,
) -> Mapping[str, Tensor]:
    ranking = multi_temperature_listwise_kd(
        output.rank_logits,
        targets.teacher_rank_scores,
        output.availability_mask,
        temperatures=temperatures,
    )
    support = masked_support_bce(
        output.support_logits, targets.support_labels, output.availability_mask
    )
    field_state = masked_cross_entropy(
        output.field_state_logits, targets.field_state_labels
    )
    cardinality = masked_cross_entropy(
        output.cardinality_logits, targets.cardinality_labels
    )
    route = cost_sensitive_route_loss(
        output.route_logits,
        targets.route_labels,
        route_action_costs=targets.route_action_costs,
        class_weights=route_class_weights,
        expected_cost_weight=expected_route_cost_weight,
    )
    return {
        "ranking": ranking,
        "support": support,
        "field_state": field_state,
        "cardinality": cardinality,
        "route": route,
    }


def evidence_intervention_loss(
    intervened_output: EvidenceControllerOutput,
    intervened_targets: EvidenceControllerTargets,
    *,
    temperatures: Sequence[float] = (1.0, 2.0, 4.0),
    route_class_weights: Tensor | None = None,
    expected_route_cost_weight: float = 1.0,
) -> Tensor:
    """Supervise changed decisions after candidate removal/interference.

    This deliberately uses intervention-specific teacher targets.  Enforcing
    invariance to evidence removal would teach the opposite of the desired safety
    behaviour.  The caller is responsible for pairing an original trace with its
    teacher-replayed perturbation trace.
    """

    require_torch()
    components = _supervised_components(
        intervened_output,
        intervened_targets,
        temperatures=temperatures,
        route_class_weights=route_class_weights,
        expected_route_cost_weight=expected_route_cost_weight,
    )
    return torch.stack(tuple(components.values())).mean()


def compute_evidence_controller_loss(
    output: EvidenceControllerOutput,
    targets: EvidenceControllerTargets,
    *,
    weights: LossWeights = LossWeights(),
    temperatures: Sequence[float] = (1.0, 2.0, 4.0),
    route_class_weights: Tensor | None = None,
    expected_route_cost_weight: float = 1.0,
    intervention_pair: tuple[
        EvidenceControllerOutput, EvidenceControllerTargets
    ]
    | None = None,
) -> EvidenceControllerLoss:
    """Compose KD, support, card, route, intervention, and calibration losses."""

    require_torch()
    components = _supervised_components(
        output,
        targets,
        temperatures=temperatures,
        route_class_weights=route_class_weights,
        expected_route_cost_weight=expected_route_cost_weight,
    )
    if intervention_pair is None:
        intervention = _zero(output.route_logits)
    else:
        intervention = evidence_intervention_loss(
            intervention_pair[0],
            intervention_pair[1],
            temperatures=temperatures,
            route_class_weights=route_class_weights,
            expected_route_cost_weight=expected_route_cost_weight,
        )
    calibration = calibration_brier_loss(output, targets)
    total = (
        weights.ranking * components["ranking"]
        + weights.support * components["support"]
        + weights.field_state * components["field_state"]
        + weights.cardinality * components["cardinality"]
        + weights.route * components["route"]
        + weights.intervention * intervention
        + weights.calibration * calibration
    )
    return EvidenceControllerLoss(
        total=total,
        ranking=components["ranking"],
        support=components["support"],
        field_state=components["field_state"],
        cardinality=components["cardinality"],
        route=components["route"],
        intervention=intervention,
        calibration=calibration,
    )


__all__ = [
    "IGNORE_INDEX",
    "EvidenceControllerLoss",
    "EvidenceControllerTargets",
    "LossWeights",
    "calibration_brier_loss",
    "compute_evidence_controller_loss",
    "cost_sensitive_route_loss",
    "evidence_intervention_loss",
    "masked_cross_entropy",
    "masked_support_bce",
    "multi_temperature_listwise_kd",
]
