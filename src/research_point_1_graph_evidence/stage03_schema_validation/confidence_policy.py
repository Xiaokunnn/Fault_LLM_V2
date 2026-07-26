"""Strict candidate confidence and automatic-Silver decision policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SOURCE_COMPONENTS = {"A": 1.0, "B": 0.95, "C": 0.85, "D": 0.70}
EVIDENCE_COMPONENTS = {"E1": 1.0, "E2": 0.95, "E3": 0.75}


@dataclass(frozen=True)
class ConfidenceDecision:
    decision: str
    final_confidence: float
    model_confidence: float
    evidence_confidence_component: float
    source_confidence_component: float
    entailment_confidence_component: float
    silver_eligible: bool
    hard_veto_reasons: tuple[str, ...] = ()
    review_reasons: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _bounded(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, number))


def decide_confidence(
    *,
    model_confidence: float,
    evidence_validation: object,
    relation_type_validation: object,
    relation_entailment_validation: object,
    schema_valid: bool = True,
    source_tier: str = "A",
    inferred_edge: bool = False,
    document_split: str = "build_train",
    minimum_candidate_confidence: float = 0.6,
    minimum_silver_confidence: float = 0.8,
) -> ConfidenceDecision:
    """Combine auditable components but apply semantic hard gates first."""

    model_component = _bounded(model_confidence)
    evidence_level = str(_field(evidence_validation, "evidence_level", "") or "")
    evidence_component = EVIDENCE_COMPONENTS.get(evidence_level, 0.0)
    source_component = SOURCE_COMPONENTS.get(str(source_tier), 0.0)
    entailment_status = str(
        _field(relation_entailment_validation, "status", "undetermined")
    )
    entailment_component = {
        "entailed": 1.0,
        "undetermined": 0.75,
        "not_entailed": 0.0,
    }.get(entailment_status, 0.0)
    # Source authority is recorded and gated separately. It must not inflate or
    # deflate whether the quoted text semantically supports the Claim.
    structural_confidence = round(model_component * evidence_component, 3)
    final = round(structural_confidence * entailment_component, 3)

    fatal: list[str] = []
    vetoes: list[str] = []
    if not schema_valid:
        fatal.append("schema_invalid")
    if not bool(_field(relation_type_validation, "valid", False)):
        fatal.append("relation_type_invalid")
    if not bool(_field(evidence_validation, "valid", False)):
        fatal.append("evidence_invalid")
    if entailment_status == "not_entailed":
        fatal.append("relation_not_entailed")
    elif entailment_status != "entailed":
        vetoes.append("relation_entailment_undetermined")
    if evidence_level == "E3" or not bool(
        _field(evidence_validation, "silver_eligible", False)
    ):
        vetoes.append("evidence_not_automatic_silver")
    if not bool(_field(relation_entailment_validation, "silver_eligible", False)):
        vetoes.append("entailment_not_automatic_silver")
    if inferred_edge:
        vetoes.append("inferred_edge_not_automatic_silver")
    if document_split in {"held_out_test", "heldout_test"}:
        vetoes.append("held_out_test_not_primary_graph_eligible")
    if source_component <= 0:
        fatal.append("unknown_source_tier")

    fatal = list(dict.fromkeys(fatal))
    vetoes = list(dict.fromkeys(vetoes))
    rejection_reasons = list(fatal)
    if fatal:
        decision = "rejected"
    elif final >= minimum_silver_confidence and not vetoes:
        decision = "silver_candidate"
    elif final >= minimum_candidate_confidence or (
        vetoes and structural_confidence >= minimum_candidate_confidence
    ):
        decision = "candidate_needs_review"
    else:
        decision = "rejected"
        rejection_reasons.append("below_candidate_confidence")

    return ConfidenceDecision(
        decision=decision,
        final_confidence=final,
        model_confidence=model_component,
        evidence_confidence_component=evidence_component,
        source_confidence_component=source_component,
        entailment_confidence_component=entailment_component,
        silver_eligible=decision == "silver_candidate",
        hard_veto_reasons=tuple(fatal),
        review_reasons=tuple(vetoes),
        rejection_reasons=tuple(dict.fromkeys(rejection_reasons)),
    )
