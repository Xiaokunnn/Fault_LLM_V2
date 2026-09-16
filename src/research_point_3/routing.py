"""Cost-sensitive three-action routing for the RP3 edge runtime.

Routing is an expected-risk decision, not an entropy threshold.  The router
compares the expected cost of accepting the student answer, invoking the full
RP2 teacher, and abstaining for human review.  Hard evidence-contract failures
make a local answer ineligible, while an independently trusted teacher may
remain an admissible fallback.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable

from .contracts import ContractError, RouteAction, RouteDecision


def _probability(value: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ContractError(f"{name} must be finite and in [0, 1]")
    return number


def _cost(value: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ContractError(f"{name} must be finite and >= 0")
    return number


def _codes(values: Iterable[str], name: str) -> tuple[str, ...]:
    result = tuple(str(value).strip() for value in values)
    if any(not value for value in result):
        raise ContractError(f"{name} must not contain empty values")
    if len(set(result)) != len(result):
        raise ContractError(f"{name} must not contain duplicate values")
    return result


@dataclass(frozen=True)
class RoutingCostProfile:
    """Costs and admissibility floors expressed in one deployment cost unit."""

    student_compute_cost: float = 1.0
    teacher_compute_cost: float = 8.0
    unsafe_or_wrong_answer_cost: float = 50.0
    abstain_and_review_cost: float = 12.0
    minimum_student_success_probability: float = 0.70
    minimum_teacher_success_probability: float = 0.80

    def __post_init__(self) -> None:
        for name in (
            "student_compute_cost",
            "teacher_compute_cost",
            "unsafe_or_wrong_answer_cost",
            "abstain_and_review_cost",
        ):
            object.__setattr__(self, name, _cost(getattr(self, name), name))
        for name in (
            "minimum_student_success_probability",
            "minimum_teacher_success_probability",
        ):
            object.__setattr__(self, name, _probability(getattr(self, name), name))


@dataclass(frozen=True)
class RoutingSignals:
    """Calibrated benefit estimates and hard runtime constraints.

    ``student_success_probability`` and ``teacher_success_probability`` are
    calibrated estimates of producing an acceptable evidence-grounded output.
    They may be learned, but they are not an entropy proxy.  The direct-support
    count and hard-failure codes are independently checked runtime facts.
    """

    student_success_probability: float
    teacher_success_probability: float
    direct_support_count: int
    teacher_available: bool = True
    hard_failure_codes: tuple[str, ...] = ()
    teacher_failure_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "student_success_probability",
            _probability(
                self.student_success_probability, "student_success_probability"
            ),
        )
        object.__setattr__(
            self,
            "teacher_success_probability",
            _probability(
                self.teacher_success_probability, "teacher_success_probability"
            ),
        )
        count = int(self.direct_support_count)
        if count < 0:
            raise ContractError("direct_support_count must be >= 0")
        object.__setattr__(self, "direct_support_count", count)
        if type(self.teacher_available) is not bool:
            raise ContractError("teacher_available must be a JSON boolean")
        object.__setattr__(
            self, "hard_failure_codes", _codes(self.hard_failure_codes, "hard_failure_codes")
        )
        object.__setattr__(
            self,
            "teacher_failure_codes",
            _codes(self.teacher_failure_codes, "teacher_failure_codes"),
        )


@dataclass(frozen=True)
class RoutingEvaluation:
    decision: RouteDecision
    expected_answer_loss: float
    expected_fallback_loss: float
    expected_abstain_loss: float
    answer_eligible: bool
    fallback_eligible: bool


class CostSensitiveRouter:
    """Choose answer, full-teacher fallback, or abstention by expected cost."""

    def __init__(self, profile: RoutingCostProfile | None = None) -> None:
        self.profile = profile or RoutingCostProfile()

    def evaluate(self, signals: RoutingSignals) -> RoutingEvaluation:
        profile = self.profile
        answer_loss = profile.student_compute_cost + (
            1.0 - signals.student_success_probability
        ) * profile.unsafe_or_wrong_answer_cost
        fallback_loss = profile.teacher_compute_cost + (
            1.0 - signals.teacher_success_probability
        ) * profile.unsafe_or_wrong_answer_cost
        abstain_loss = profile.abstain_and_review_cost

        answer_eligible = (
            signals.direct_support_count > 0
            and not signals.hard_failure_codes
            and signals.student_success_probability
            >= profile.minimum_student_success_probability
        )
        fallback_eligible = (
            signals.teacher_available
            and not signals.teacher_failure_codes
            and signals.teacher_success_probability
            >= profile.minimum_teacher_success_probability
        )

        # On an exact cost tie, prefer the safer action: abstain, then the full
        # teacher, then the student answer.
        candidates: list[tuple[float, int, RouteAction]] = [
            (abstain_loss, 0, RouteAction.ABSTAIN)
        ]
        if fallback_eligible:
            candidates.append((fallback_loss, 1, RouteAction.FALLBACK))
        if answer_eligible:
            candidates.append((answer_loss, 2, RouteAction.ANSWER))
        ordered = sorted(candidates, key=lambda item: (item[0], item[1]))
        chosen_loss, _, action = ordered[0]

        reasons: list[str] = ["cost_sensitive_minimum_expected_loss"]
        if not answer_eligible:
            if signals.direct_support_count == 0:
                reasons.append("no_direct_support")
            if signals.student_success_probability < profile.minimum_student_success_probability:
                reasons.append("student_success_below_floor")
            reasons.extend(signals.hard_failure_codes)
        if not fallback_eligible:
            if not signals.teacher_available:
                reasons.append("teacher_unavailable")
            elif signals.teacher_success_probability < profile.minimum_teacher_success_probability:
                reasons.append("teacher_success_below_floor")
            reasons.extend(signals.teacher_failure_codes)
        reasons.append(f"selected_{action.value}")
        reasons = list(dict.fromkeys(reasons))

        if len(ordered) == 1:
            route_confidence = 1.0
        else:
            second_loss = ordered[1][0]
            scale = abs(chosen_loss) + abs(second_loss) + 1.0
            route_confidence = max(0.0, min(1.0, (second_loss - chosen_loss) / scale))

        error_cost = {
            RouteAction.ANSWER: (
                1.0 - signals.student_success_probability
            )
            * profile.unsafe_or_wrong_answer_cost,
            RouteAction.FALLBACK: (
                1.0 - signals.teacher_success_probability
            )
            * profile.unsafe_or_wrong_answer_cost,
            RouteAction.ABSTAIN: 0.0,
        }[action]
        decision = RouteDecision(
            action=action,
            reason_codes=tuple(reasons),
            estimated_student_cost=profile.student_compute_cost,
            estimated_teacher_cost=profile.teacher_compute_cost,
            estimated_error_cost=error_cost,
            confidence=route_confidence,
        )
        return RoutingEvaluation(
            decision=decision,
            expected_answer_loss=answer_loss,
            expected_fallback_loss=fallback_loss,
            expected_abstain_loss=abstain_loss,
            answer_eligible=answer_eligible,
            fallback_eligible=fallback_eligible,
        )

    def decide(self, signals: RoutingSignals) -> RouteDecision:
        return self.evaluate(signals).decision

    def label_from_oracle(
        self,
        *,
        student_output_acceptable: bool,
        teacher_output_acceptable: bool,
        direct_support_count: int,
        teacher_available: bool = True,
        hard_failure_codes: tuple[str, ...] = (),
        teacher_failure_codes: tuple[str, ...] = (),
    ) -> RouteDecision:
        """Generate a cost-sensitive training label from observed outcomes.

        The oracle supplies binary counterfactual outcomes for the student and
        teacher.  Costs still decide whether fallback or review is preferable;
        consequently this is not a rule that merely maps error to fallback.
        """

        if type(student_output_acceptable) is not bool:
            raise ContractError("student_output_acceptable must be a JSON boolean")
        if type(teacher_output_acceptable) is not bool:
            raise ContractError("teacher_output_acceptable must be a JSON boolean")
        decision = self.decide(
            RoutingSignals(
                student_success_probability=float(student_output_acceptable),
                teacher_success_probability=float(teacher_output_acceptable),
                direct_support_count=direct_support_count,
                teacher_available=teacher_available,
                hard_failure_codes=hard_failure_codes,
                teacher_failure_codes=teacher_failure_codes,
            )
        )
        return replace(
            decision,
            reason_codes=("oracle_cost_sensitive_label",) + decision.reason_codes,
        )


__all__ = [
    "CostSensitiveRouter",
    "RoutingCostProfile",
    "RoutingEvaluation",
    "RoutingSignals",
]
