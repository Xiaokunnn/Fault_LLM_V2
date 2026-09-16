"""Governed ``select_pump_evidence`` tool boundary for an LLM/orchestrator.

The tool exposes a bounded candidate signature and availability mask to the
student controller.  Every returned pointer is resolved against an immutable,
version-bound evidence memory before any factual text is rendered.  Contract,
hash, version, ID, mask, or controller-output violations return a fact-free
abstention response.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from .artifacts import stable_sha256
from .contracts import (
    CARD_SLOT_ROLES,
    CONTRACT_VERSION,
    CardFieldState,
    CompactEvidenceRecord,
    ContractError,
    DiagnosisCard,
    DiagnosticRole,
    QueryContext,
    RouteAction,
    RouteDecision,
    SupportVerdict,
    validate_compact_memory,
)
from .renderer import (
    DeterministicDiagnosisCardRenderer,
    RenderEvidenceDecision,
    RenderFieldPlan,
)
from .routing import CostSensitiveRouter


TOOL_NAME = "select_pump_evidence"
AUDIT_TOOL_NAME = "select_pump_evidence_audit"
TOOL_API_VERSION = "rp3_select_pump_evidence_v2"
BUCKET_REGISTRY_ARTIFACT_TYPE = "rp3_frozen_candidate_bucket_registry"


class RuntimeEvidenceError(ContractError):
    """A fail-closed runtime evidence binding or pointer error."""


def candidate_signature_sha256(
    evidence_ids: Sequence[str], availability_mask: Sequence[bool]
) -> str:
    return stable_sha256(
        {
            "candidate_evidence_ids": list(evidence_ids),
            "availability_mask": list(availability_mask),
        }
    )


def _digest(value: str, name: str) -> str:
    digest = str(value).strip().lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ContractError(f"{name} must be a 64-character hexadecimal SHA-256")
    return digest


@dataclass(frozen=True)
class SelectPumpEvidenceRequest:
    query: QueryContext
    candidate_evidence_ids: tuple[str, ...]
    availability_mask: tuple[bool, ...]
    selection_budget: int
    candidate_signature_sha256: str
    memory_id: str
    memory_logical_sha256: str
    teacher_graph_id: str
    teacher_graph_sha256: str
    contract_version: str = CONTRACT_VERSION
    tool_api_version: str = TOOL_API_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.query, QueryContext):
            object.__setattr__(self, "query", QueryContext.from_dict(self.query))
        ids = tuple(str(value).strip() for value in self.candidate_evidence_ids)
        if not ids or any(not value for value in ids):
            raise ContractError("candidate_evidence_ids must contain non-empty IDs")
        if len(ids) != len(set(ids)):
            raise ContractError("candidate_evidence_ids must not contain duplicates")
        object.__setattr__(self, "candidate_evidence_ids", ids)
        if any(type(value) is not bool for value in self.availability_mask):
            raise ContractError("availability_mask must contain JSON booleans")
        mask = tuple(self.availability_mask)
        if len(mask) != len(ids):
            raise ContractError("availability_mask length must equal candidate ID length")
        object.__setattr__(self, "availability_mask", mask)
        budget = int(self.selection_budget)
        if budget < 1:
            raise ContractError("selection_budget must be >= 1")
        object.__setattr__(self, "selection_budget", budget)
        object.__setattr__(
            self,
            "candidate_signature_sha256",
            _digest(self.candidate_signature_sha256, "candidate_signature_sha256"),
        )
        expected_signature = candidate_signature_sha256(ids, mask)
        if self.candidate_signature_sha256 != expected_signature:
            raise ContractError("candidate signature mismatch")
        for name in (
            "memory_id",
            "teacher_graph_id",
            "contract_version",
            "tool_api_version",
        ):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ContractError(f"{name} must be non-empty")
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "memory_logical_sha256",
            _digest(self.memory_logical_sha256, "memory_logical_sha256"),
        )
        object.__setattr__(
            self,
            "teacher_graph_sha256",
            _digest(self.teacher_graph_sha256, "teacher_graph_sha256"),
        )

    @classmethod
    def create(
        cls,
        *,
        query: QueryContext,
        candidate_evidence_ids: Sequence[str],
        availability_mask: Sequence[bool],
        selection_budget: int,
        memory_id: str,
        memory_logical_sha256: str,
        teacher_graph_id: str,
        teacher_graph_sha256: str,
        contract_version: str = CONTRACT_VERSION,
        tool_api_version: str = TOOL_API_VERSION,
    ) -> "SelectPumpEvidenceRequest":
        ids = tuple(candidate_evidence_ids)
        mask = tuple(availability_mask)
        return cls(
            query=query,
            candidate_evidence_ids=ids,
            availability_mask=mask,
            selection_budget=selection_budget,
            candidate_signature_sha256=candidate_signature_sha256(ids, mask),
            memory_id=memory_id,
            memory_logical_sha256=memory_logical_sha256,
            teacher_graph_id=teacher_graph_id,
            teacher_graph_sha256=teacher_graph_sha256,
            contract_version=contract_version,
            tool_api_version=tool_api_version,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SelectPumpEvidenceRequest":
        return cls(
            query=QueryContext.from_dict(data.get("query", {})),
            candidate_evidence_ids=tuple(data.get("candidate_evidence_ids", ())),
            availability_mask=tuple(data.get("availability_mask", ())),
            selection_budget=data.get("selection_budget", 0),
            candidate_signature_sha256=data.get("candidate_signature_sha256", ""),
            memory_id=data.get("memory_id", ""),
            memory_logical_sha256=data.get("memory_logical_sha256", ""),
            teacher_graph_id=data.get("teacher_graph_id", ""),
            teacher_graph_sha256=data.get("teacher_graph_sha256", ""),
            contract_version=data.get("contract_version", ""),
            tool_api_version=data.get("tool_api_version", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["query"] = self.query.to_dict()
        data["candidate_evidence_ids"] = list(self.candidate_evidence_ids)
        data["availability_mask"] = list(self.availability_mask)
        return data


@dataclass(frozen=True)
class ResolvedCandidate:
    evidence_id: str
    available: bool
    record: CompactEvidenceRecord | None


@dataclass(frozen=True)
class ControllerEvidenceDecision:
    evidence_id: str
    rank: int
    score: float
    support: SupportVerdict
    selected: bool
    support_probability: float | None = None

    def __post_init__(self) -> None:
        evidence_id = str(self.evidence_id).strip()
        if not evidence_id:
            raise ContractError("controller evidence_id must be non-empty")
        object.__setattr__(self, "evidence_id", evidence_id)
        rank = int(self.rank)
        if rank < 1:
            raise ContractError("controller rank must be >= 1")
        object.__setattr__(self, "rank", rank)
        score = float(self.score)
        if not math.isfinite(score):
            raise ContractError("controller score must be finite")
        object.__setattr__(self, "score", score)
        try:
            object.__setattr__(self, "support", SupportVerdict(str(self.support)))
        except ValueError as exc:
            raise ContractError("controller support verdict is invalid") from exc
        if type(self.selected) is not bool:
            raise ContractError("controller selected must be a JSON boolean")
        probability = self.support_probability
        if probability is None:
            probability = 1.0 if self.support == SupportVerdict.DIRECT else 0.0
        probability = float(probability)
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ContractError("controller support_probability must be in [0, 1]")
        object.__setattr__(self, "support_probability", probability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "rank": self.rank,
            "score": self.score,
            "support": self.support.value,
            "support_probability": self.support_probability,
            "selected": self.selected,
        }


@dataclass(frozen=True)
class ControllerFieldPrediction:
    """Symbolic ONNX-adapter output for one frozen diagnosis-card slot."""

    role: DiagnosticRole
    state: CardFieldState
    cardinality: int

    def __post_init__(self) -> None:
        try:
            role = DiagnosticRole(str(self.role))
        except ValueError as exc:
            raise ContractError("controller field role is invalid") from exc
        if role not in CARD_SLOT_ROLES:
            raise ContractError("controller field role must be a frozen card slot")
        object.__setattr__(self, "role", role)
        try:
            state = CardFieldState(str(self.state))
        except ValueError as exc:
            raise ContractError("controller field state is invalid") from exc
        object.__setattr__(self, "state", state)
        cardinality = int(self.cardinality)
        if cardinality < 0:
            raise ContractError("controller field cardinality must be >= 0")
        if state in {
            CardFieldState.INSUFFICIENT,
            CardFieldState.NOT_APPLICABLE,
        } and cardinality != 0:
            raise ContractError(
                f"field state={state.value} requires cardinality=0"
            )
        if state == CardFieldState.SUPPORTED and cardinality < 1:
            raise ContractError("field state=supported requires cardinality >= 1")
        if state == CardFieldState.CONFLICT and cardinality < 2:
            raise ContractError("field state=conflict requires cardinality >= 2")
        object.__setattr__(self, "cardinality", cardinality)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "state": self.state.value,
            "cardinality": self.cardinality,
        }


@dataclass(frozen=True)
class ControllerPrediction:
    decisions: tuple[ControllerEvidenceDecision, ...]
    fields: tuple[ControllerFieldPrediction, ...]
    route_action: RouteAction
    route_confidence: float
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        rows = tuple(
            row
            if isinstance(row, ControllerEvidenceDecision)
            else ControllerEvidenceDecision(**row)
            for row in self.decisions
        )
        object.__setattr__(self, "decisions", rows)
        fields = tuple(
            field
            if isinstance(field, ControllerFieldPrediction)
            else ControllerFieldPrediction(**field)
            for field in self.fields
        )
        roles = tuple(field.role for field in fields)
        if len(fields) != len(CARD_SLOT_ROLES) or set(roles) != set(CARD_SLOT_ROLES):
            raise ContractError(
                "controller fields must contain every frozen card slot exactly once"
            )
        object.__setattr__(
            self,
            "fields",
            tuple(next(field for field in fields if field.role == role) for role in CARD_SLOT_ROLES),
        )
        try:
            object.__setattr__(self, "route_action", RouteAction(str(self.route_action)))
        except ValueError as exc:
            raise ContractError("controller route_action is invalid") from exc
        confidence = float(self.route_confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ContractError("route_confidence must be finite and in [0, 1]")
        object.__setattr__(self, "route_confidence", confidence)
        codes = tuple(str(value).strip() for value in self.reason_codes)
        if any(not value for value in codes) or len(set(codes)) != len(codes):
            raise ContractError("controller reason_codes must be unique non-empty values")
        object.__setattr__(self, "reason_codes", codes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisions": [row.to_dict() for row in self.decisions],
            "fields": [field.to_dict() for field in self.fields],
            "route_action": self.route_action.value,
            "route_confidence": self.route_confidence,
            "reason_codes": list(self.reason_codes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ControllerPrediction":
        return cls(
            decisions=tuple(
                ControllerEvidenceDecision(**row)
                for row in data.get("decisions", ())
            ),
            fields=tuple(
                ControllerFieldPrediction(**field)
                for field in data.get("fields", ())
            ),
            route_action=data.get("route_action", ""),
            route_confidence=data.get("route_confidence", -1.0),
            reason_codes=tuple(data.get("reason_codes", ())),
        )

    @classmethod
    def from_decoded(
        cls,
        decoded: Any,
        candidate_evidence_ids: Sequence[str],
    ) -> "ControllerPrediction":
        """Bridge ``decoding.py`` output to the backend-neutral tool protocol.

        An ONNX Runtime adapter only needs to construct an
        ``EvidenceControllerOutput``, call constrained decoding, and pass the
        resulting symbolic object here.  No PyTorch tensor crosses the tool
        boundary.
        """

        candidate_ids = tuple(str(value) for value in candidate_evidence_ids)
        ranked_ids = tuple(decoded.ranked_evidence_ids)
        if set(ranked_ids) != set(candidate_ids) or len(ranked_ids) != len(candidate_ids):
            raise ContractError("decoded rank IDs must be a permutation of candidates")
        if len(decoded.candidate_order_rank_scores) != len(candidate_ids) or len(
            decoded.support_probabilities
        ) != len(candidate_ids):
            raise ContractError("decoded scores must align with candidates")
        rank_by_id = {
            evidence_id: rank for rank, evidence_id in enumerate(ranked_ids, start=1)
        }
        selected = set(decoded.selected_evidence_ids)
        direct = set(decoded.direct_support_evidence_ids)
        return cls(
            decisions=tuple(
                ControllerEvidenceDecision(
                    evidence_id=evidence_id,
                    rank=rank_by_id[evidence_id],
                    score=float(decoded.candidate_order_rank_scores[index]),
                    support=(
                        SupportVerdict.DIRECT
                        if evidence_id in direct
                        else SupportVerdict.IRRELEVANT
                    ),
                    selected=evidence_id in selected,
                    support_probability=float(decoded.support_probabilities[index]),
                )
                for index, evidence_id in enumerate(candidate_ids)
            ),
            fields=tuple(
                ControllerFieldPrediction(
                    role=field.role,
                    state=field.state,
                    cardinality=field.cardinality,
                )
                for field in decoded.card_fields
            ),
            route_action=decoded.route_action,
            route_confidence=decoded.route_confidence,
            reason_codes=tuple(decoded.reason_codes),
        )


@runtime_checkable
class EvidenceController(Protocol):
    """Small-model interface; implementations may use PyTorch, ONNX, or rules."""

    def predict(
        self,
        *,
        query: QueryContext,
        candidates: tuple[ResolvedCandidate, ...],
        selection_budget: int,
    ) -> ControllerPrediction:
        ...


class EvidenceMemoryResolver:
    """Version-bound, ID-addressed evidence resolver with fail-closed reads."""

    def __init__(
        self,
        records: Sequence[CompactEvidenceRecord],
        manifest: Mapping[str, Any],
    ) -> None:
        rows = tuple(
            sorted(validate_compact_memory(records), key=lambda row: row.memory_index)
        )
        self._records = {row.evidence_id: row for row in rows}
        self.manifest = dict(manifest)
        self._validate_manifest(rows)

    def _validate_manifest(self, rows: Sequence[CompactEvidenceRecord]) -> None:
        manifest = self.manifest
        if manifest.get("artifact_type") != "rp3_compact_evidence_memory":
            raise RuntimeEvidenceError("invalid compact evidence-memory artifact type")
        if manifest.get("contract_version") != CONTRACT_VERSION:
            raise RuntimeEvidenceError("evidence-memory contract version mismatch")
        if int(manifest.get("record_count", -1)) != len(rows):
            raise RuntimeEvidenceError("evidence-memory record count mismatch")
        expected = str(manifest.get("logical_sha256", "")).lower()
        actual = stable_sha256([row.to_dict() for row in rows])
        if expected != actual:
            raise RuntimeEvidenceError("evidence-memory logical hash mismatch")
        graph = manifest.get("teacher_graph")
        if not isinstance(graph, Mapping):
            raise RuntimeEvidenceError("evidence-memory teacher graph binding is missing")
        if not str(manifest.get("memory_id", "")).strip():
            raise RuntimeEvidenceError("evidence-memory ID is missing")
        _digest(str(graph.get("sha256", "")), "teacher_graph.sha256")

    def validate_request_binding(self, request: SelectPumpEvidenceRequest) -> None:
        manifest = self.manifest
        graph = manifest["teacher_graph"]
        if request.contract_version != manifest["contract_version"]:
            raise RuntimeEvidenceError("evidence contract version mismatch")
        if request.tool_api_version != TOOL_API_VERSION:
            raise RuntimeEvidenceError("tool API version mismatch")
        expected = {
            "memory_id": manifest["memory_id"],
            "memory_logical_sha256": manifest["logical_sha256"],
            "teacher_graph_id": graph.get("id"),
            "teacher_graph_sha256": graph.get("sha256"),
        }
        actual = {
            "memory_id": request.memory_id,
            "memory_logical_sha256": request.memory_logical_sha256,
            "teacher_graph_id": request.teacher_graph_id,
            "teacher_graph_sha256": request.teacher_graph_sha256,
        }
        mismatches = [name for name in expected if expected[name] != actual[name]]
        if mismatches:
            raise RuntimeEvidenceError(
                "runtime artifact binding mismatch: " + ", ".join(mismatches)
            )

    def resolve_candidates(
        self, evidence_ids: Sequence[str], availability_mask: Sequence[bool]
    ) -> tuple[ResolvedCandidate, ...]:
        if len(evidence_ids) != len(availability_mask):
            raise RuntimeEvidenceError("candidate mask length mismatch")
        result: list[ResolvedCandidate] = []
        for evidence_id, available in zip(evidence_ids, availability_mask):
            if evidence_id not in self._records:
                raise RuntimeEvidenceError(f"unknown evidence_id={evidence_id}")
            # The controller observes the availability bit but never sees the
            # content/features of an unavailable item.
            result.append(
                ResolvedCandidate(
                    evidence_id=evidence_id,
                    available=available,
                    record=self._records[evidence_id] if available else None,
                )
            )
        return tuple(result)

    def resolve_available(
        self,
        evidence_ids: Sequence[str],
        *,
        available_by_id: Mapping[str, bool],
    ) -> dict[str, CompactEvidenceRecord]:
        result: dict[str, CompactEvidenceRecord] = {}
        for evidence_id in evidence_ids:
            if evidence_id not in self._records:
                raise RuntimeEvidenceError(f"unknown evidence_id={evidence_id}")
            if not available_by_id.get(evidence_id, False):
                raise RuntimeEvidenceError(f"unavailable evidence_id={evidence_id}")
            result[evidence_id] = self._records[evidence_id]
        return result

    def contains(self, evidence_id: str) -> bool:
        """Return whether an ID belongs to this exact frozen memory."""

        return str(evidence_id) in self._records


@dataclass(frozen=True)
class FrozenCandidateBucket:
    fault_id: str
    role: DiagnosticRole
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        fault_id = str(self.fault_id).strip()
        if not fault_id:
            raise ContractError("candidate bucket fault_id must be non-empty")
        object.__setattr__(self, "fault_id", fault_id)
        try:
            role = DiagnosticRole(str(self.role))
        except ValueError as exc:
            raise ContractError("candidate bucket role is invalid") from exc
        if role not in CARD_SLOT_ROLES:
            raise ContractError("candidate bucket role must be a frozen card slot")
        object.__setattr__(self, "role", role)
        ids = tuple(str(value).strip() for value in self.evidence_ids)
        if any(not value for value in ids) or len(set(ids)) != len(ids) or len(ids) > 32:
            raise ContractError("candidate bucket IDs must be unique non-empty values")
        object.__setattr__(self, "evidence_ids", ids)


class FrozenCandidateBucketRegistry:
    """Server-owned fault×role buckets; no online ANN or graph traversal."""

    def __init__(
        self,
        *,
        buckets: Sequence[FrozenCandidateBucket],
        manifest: Mapping[str, Any],
        resolver: EvidenceMemoryResolver,
    ) -> None:
        self.manifest = dict(manifest)
        if self.manifest.get("artifact_type") != BUCKET_REGISTRY_ARTIFACT_TYPE:
            raise RuntimeEvidenceError("invalid frozen candidate-bucket registry")
        if self.manifest.get("contract_version") != CONTRACT_VERSION:
            raise RuntimeEvidenceError("candidate-bucket contract version mismatch")
        memory = self.manifest.get("memory")
        graph = self.manifest.get("teacher_graph")
        expected_memory = {
            "id": resolver.manifest.get("memory_id"),
            "logical_sha256": resolver.manifest.get("logical_sha256"),
        }
        expected_graph = resolver.manifest.get("teacher_graph")
        if not isinstance(memory, Mapping) or {
            key: memory.get(key) for key in expected_memory
        } != expected_memory:
            raise RuntimeEvidenceError("bucket registry binds a different evidence memory")
        if not isinstance(graph, Mapping) or dict(graph) != dict(expected_graph or {}):
            raise RuntimeEvidenceError("bucket registry binds a different teacher graph")
        rows = tuple(buckets)
        keys = [(row.fault_id, row.role) for row in rows]
        if len(set(keys)) != len(keys):
            raise RuntimeEvidenceError("candidate bucket keys must be unique")
        missing = [
            evidence_id
            for row in rows
            for evidence_id in row.evidence_ids
            if not resolver.contains(evidence_id)
        ]
        if missing:
            raise RuntimeEvidenceError("candidate bucket contains an unknown evidence ID")
        logical_rows = [
            {
                "fault_id": row.fault_id,
                "role": row.role.value,
                "evidence_ids": list(row.evidence_ids),
            }
            for row in sorted(rows, key=lambda value: (value.fault_id, value.role.value))
        ]
        if int(self.manifest.get("bucket_count", -1)) != len(rows) or (
            self.manifest.get("logical_sha256") != stable_sha256(logical_rows)
        ):
            raise RuntimeEvidenceError("candidate-bucket registry logical hash mismatch")
        self._buckets = {(row.fault_id, row.role): row.evidence_ids for row in rows}

    def resolve(
        self,
        *,
        fault_id: str,
        role: DiagnosticRole,
        available_evidence_ids: Sequence[str] | None = None,
    ) -> tuple[tuple[str, ...], tuple[bool, ...]]:
        key = (str(fault_id).strip(), DiagnosticRole(str(role)))
        if key not in self._buckets:
            raise RuntimeEvidenceError("no frozen candidate bucket for fault and role")
        bucket = self._buckets[key]
        if available_evidence_ids is None:
            return bucket, tuple(True for _ in bucket)
        available = tuple(str(value).strip() for value in available_evidence_ids)
        if any(not value for value in available) or len(set(available)) != len(available):
            raise RuntimeEvidenceError("available_evidence_ids must be unique non-empty IDs")
        unknown = set(available) - set(bucket)
        if unknown:
            raise RuntimeEvidenceError("available evidence must be a subset of the frozen bucket")
        active = set(available)
        return bucket, tuple(evidence_id in active for evidence_id in bucket)


@dataclass(frozen=True)
class SelectPumpEvidenceResponse:
    ok: bool
    action: RouteAction
    route: RouteDecision
    diagnosis_card: DiagnosisCard
    natural_language_shell: str
    selected_evidence: tuple[dict[str, Any], ...]
    error_codes: tuple[str, ...]
    contract_version: str = CONTRACT_VERSION
    tool_api_version: str = TOOL_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action.value,
            "route": self.route.to_dict(),
            "diagnosis_card": self.diagnosis_card.to_dict(),
            "natural_language_shell": self.natural_language_shell,
            "selected_evidence": list(self.selected_evidence),
            "error_codes": list(self.error_codes),
            "contract_version": self.contract_version,
            "tool_api_version": self.tool_api_version,
        }


class SelectPumpEvidenceTool:
    """Callable safety wrapper around a distilled evidence controller."""

    def __init__(
        self,
        *,
        controller: EvidenceController,
        resolver: EvidenceMemoryResolver,
        router: CostSensitiveRouter | None = None,
        renderer: DeterministicDiagnosisCardRenderer | None = None,
        teacher_available: bool = True,
        minimum_route_confidence: float | None = None,
    ) -> None:
        self.controller = controller
        self.resolver = resolver
        self.router = router or CostSensitiveRouter()
        self.renderer = renderer or DeterministicDiagnosisCardRenderer()
        self.teacher_available = bool(teacher_available)
        if minimum_route_confidence is not None:
            raise ContractError(
                "runtime route thresholds must come from the controller's "
                "version-bound MP008 calibration artifact"
            )
        controller_threshold = getattr(controller, "minimum_route_confidence", None)
        if controller_threshold is None:
            raise ContractError(
                "evidence controller has no bound MP008 route calibration threshold"
            )
        confidence = float(controller_threshold)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ContractError("minimum_route_confidence must be in [0, 1]")
        self.minimum_route_confidence = confidence

    def _guard_route(
        self,
        prediction: ControllerPrediction,
        *,
        direct_support_count: int,
    ) -> RouteDecision:
        """Apply monotone guards to the cost-sensitive LEC route head.

        The head has already learned the three-action cost policy.  Runtime
        guards can only move toward greater escalation: answer -> fallback ->
        abstain.  They can never turn fallback/abstain into a local answer.
        """

        action = prediction.route_action
        reasons = ["lec_route_head", f"lec_selected_{action.value}"]
        if action == RouteAction.ANSWER and any(
            field.state == CardFieldState.CONFLICT for field in prediction.fields
        ):
            action = RouteAction.FALLBACK
            reasons.append("answer_blocked_by_field_conflict")
        if action == RouteAction.ANSWER and direct_support_count == 0:
            action = RouteAction.FALLBACK
            reasons.append("answer_blocked_without_direct_support")
        if (
            action == RouteAction.ANSWER
            and prediction.route_confidence < self.minimum_route_confidence
        ):
            action = RouteAction.FALLBACK
            reasons.append("answer_blocked_by_route_confidence")
        if (
            action == RouteAction.ANSWER
            and self.router.profile.student_compute_cost
            >= self.router.profile.abstain_and_review_cost
        ):
            action = RouteAction.FALLBACK
            reasons.append("answer_blocked_by_cost_guard")
        if action == RouteAction.FALLBACK:
            if not self.teacher_available:
                action = RouteAction.ABSTAIN
                reasons.append("teacher_unavailable")
            elif (
                self.router.profile.teacher_compute_cost
                >= self.router.profile.abstain_and_review_cost
            ):
                action = RouteAction.ABSTAIN
                reasons.append("fallback_blocked_by_cost_guard")
        reasons.extend(prediction.reason_codes)
        reasons.append(f"guarded_{action.value}")
        return RouteDecision(
            action=action,
            reason_codes=tuple(dict.fromkeys(reasons)),
            estimated_student_cost=self.router.profile.student_compute_cost,
            estimated_teacher_cost=self.router.profile.teacher_compute_cost,
            # The LEC emits route-class confidence, not a second success model;
            # do not mislabel it as an answer-error probability.
            estimated_error_cost=(
                1.0 - prediction.route_confidence
            ) * self.router.profile.unsafe_or_wrong_answer_cost,
            confidence=prediction.route_confidence,
        )

    def _empty_card(self, query: QueryContext) -> DiagnosisCard:
        return self.renderer.render(
            query=query,
            records_by_id={},
            decisions=(),
            field_plan=tuple(
                RenderFieldPlan(
                    role=role,
                    state=CardFieldState.INSUFFICIENT,
                    cardinality=0,
                )
                for role in CARD_SLOT_ROLES
            ),
        )

    def _fail_closed(
        self, query: QueryContext, code: str
    ) -> SelectPumpEvidenceResponse:
        card = self._empty_card(query)
        route = RouteDecision(
            action=RouteAction.ABSTAIN,
            reason_codes=("runtime_fail_closed", code, "selected_abstain"),
            estimated_student_cost=self.router.profile.student_compute_cost,
            estimated_teacher_cost=self.router.profile.teacher_compute_cost,
            estimated_error_cost=0.0,
            confidence=1.0,
        )
        return SelectPumpEvidenceResponse(
            ok=False,
            action=RouteAction.ABSTAIN,
            route=route,
            diagnosis_card=card,
            natural_language_shell="",
            selected_evidence=(),
            error_codes=(code,),
        )

    def select_pump_evidence(
        self, request: SelectPumpEvidenceRequest | Mapping[str, Any]
    ) -> SelectPumpEvidenceResponse:
        if not isinstance(request, (SelectPumpEvidenceRequest, Mapping)):
            raise RuntimeEvidenceError("request must be a mapping or SelectPumpEvidenceRequest")
        raw_query = (
            request.query
            if isinstance(request, SelectPumpEvidenceRequest)
            else request.get("query", {})
        )
        try:
            query = raw_query if isinstance(raw_query, QueryContext) else QueryContext.from_dict(raw_query)
        except (ContractError, TypeError, ValueError):
            # A malformed query cannot safely name even a fault/card.  Propagate
            # the contract error because constructing a plausible card here
            # would itself invent context.
            raise RuntimeEvidenceError("invalid query contract")
        try:
            normalized = (
                request
                if isinstance(request, SelectPumpEvidenceRequest)
                else SelectPumpEvidenceRequest.from_dict(request)
            )
            self.resolver.validate_request_binding(normalized)
            candidates = self.resolver.resolve_candidates(
                normalized.candidate_evidence_ids, normalized.availability_mask
            )
            prediction = self.controller.predict(
                query=normalized.query,
                candidates=candidates,
                selection_budget=normalized.selection_budget,
            )
            if not isinstance(prediction, ControllerPrediction):
                raise RuntimeEvidenceError("controller returned an invalid prediction type")
            expected_ids = normalized.candidate_evidence_ids
            output_ids = tuple(row.evidence_id for row in prediction.decisions)
            if output_ids != expected_ids:
                raise RuntimeEvidenceError(
                    "controller decisions must align one-to-one with candidate order"
                )
            ranks = sorted(row.rank for row in prediction.decisions)
            if ranks != list(range(1, len(prediction.decisions) + 1)):
                raise RuntimeEvidenceError("controller ranks must be a permutation of 1..N")
            selected = tuple(row for row in prediction.decisions if row.selected)
            if len(selected) > normalized.selection_budget:
                raise RuntimeEvidenceError("controller selection exceeds budget")
            invalid_support = [
                row.evidence_id
                for row in selected
                if row.support != SupportVerdict.DIRECT
            ]
            if invalid_support:
                raise RuntimeEvidenceError("controller selected non-direct evidence")
            available_by_id = dict(
                zip(normalized.candidate_evidence_ids, normalized.availability_mask)
            )
            records_by_id = self.resolver.resolve_available(
                tuple(row.evidence_id for row in selected),
                available_by_id=available_by_id,
            )
            selected_counts = {role: 0 for role in CARD_SLOT_ROLES}
            for row in selected:
                record = records_by_id[row.evidence_id]
                if record.role not in CARD_SLOT_ROLES:
                    raise RuntimeEvidenceError(
                        "controller selected context or non-card evidence"
                    )
                if normalized.query.fault_id not in record.fault_class_ids:
                    raise RuntimeEvidenceError(
                        "controller selected evidence outside query fault scope"
                    )
                if (
                    normalized.query.requested_role != DiagnosticRole.FULL_CARD
                    and record.role != normalized.query.requested_role
                ):
                    raise RuntimeEvidenceError(
                        "controller selected evidence outside requested diagnostic role"
                    )
                selected_counts[record.role] += 1
            for field in prediction.fields:
                actual = selected_counts[field.role]
                if field.cardinality != actual:
                    raise RuntimeEvidenceError(
                        "controller field cardinality does not match selected evidence role"
                    )
            route = self._guard_route(
                prediction,
                direct_support_count=len(selected),
            )
            if route.action != RouteAction.ANSWER:
                card = self._empty_card(normalized.query)
                return SelectPumpEvidenceResponse(
                    ok=True,
                    action=route.action,
                    route=route,
                    diagnosis_card=card,
                    natural_language_shell="",
                    selected_evidence=(),
                    error_codes=(),
                )
            render_decisions = tuple(
                RenderEvidenceDecision(
                    evidence_id=row.evidence_id,
                    rank=row.rank,
                    support=row.support,
                    selected=row.selected,
                )
                for row in prediction.decisions
            )
            card = self.renderer.render(
                query=normalized.query,
                records_by_id=records_by_id,
                decisions=render_decisions,
                field_plan=tuple(
                    RenderFieldPlan(
                        role=field.role,
                        state=field.state,
                        cardinality=field.cardinality,
                    )
                    for field in prediction.fields
                ),
            )
            shell = self.renderer.render_natural_language_shell(card)
            evidence_packet = tuple(
                {
                    **records_by_id[row.evidence_id].to_dict(),
                    "controller_rank": row.rank,
                    "controller_rank_score": row.score,
                    "support_verdict": row.support.value,
                    "support_probability": row.support_probability,
                }
                for row in sorted(selected, key=lambda item: item.rank)
            )
            return SelectPumpEvidenceResponse(
                ok=True,
                action=RouteAction.ANSWER,
                route=route,
                diagnosis_card=card,
                natural_language_shell=shell,
                selected_evidence=evidence_packet,
                error_codes=(),
            )
        except (ContractError, KeyError, TypeError, ValueError) as exc:
            code = "runtime_contract_failure"
            if "unknown evidence_id" in str(exc):
                code = "unknown_evidence_id"
            elif "unavailable evidence_id" in str(exc):
                code = "unavailable_evidence_id"
            elif "hash mismatch" in str(exc) or "binding mismatch" in str(exc):
                code = "artifact_binding_mismatch"
            elif "version mismatch" in str(exc):
                code = "version_mismatch"
            elif "controller" in str(exc):
                code = "invalid_controller_output"
            return self._fail_closed(query, code)
        except Exception:
            # A controller backend (for example ONNX Runtime) can fail with a
            # backend-specific exception.  The tool boundary must never leak a
            # partially resolved evidence packet in that case.
            return self._fail_closed(query, "controller_runtime_failure")

    __call__ = select_pump_evidence


def select_pump_evidence(
    tool: SelectPumpEvidenceTool,
    request: SelectPumpEvidenceRequest | Mapping[str, Any],
) -> SelectPumpEvidenceResponse:
    """Function-style adapter for registries that do not bind object methods."""

    return tool.select_pump_evidence(request)


class SelectPumpEvidenceFacade:
    """Public LLM/orchestrator facade over server-owned frozen bindings."""

    def __init__(
        self,
        *,
        tool: SelectPumpEvidenceTool,
        registry: FrozenCandidateBucketRegistry,
    ) -> None:
        self.tool = tool
        self.registry = registry
        memory = registry.manifest.get("memory", {})
        if (memory.get("id") != tool.resolver.manifest.get("memory_id") or
            memory.get("logical_sha256") != tool.resolver.manifest.get("logical_sha256") or
            registry.manifest.get("teacher_graph") != tool.resolver.manifest.get("teacher_graph")):
            raise ContractError("facade registry and tool resolver identities differ")

    def select_pump_evidence(
        self,
        *,
        question: str,
        fault_id: str,
        fault_name: str,
        role: DiagnosticRole | str,
        scenario_id: str,
        max_points: int = 3,
        available_evidence_ids: Sequence[str] | None = None,
    ) -> SelectPumpEvidenceResponse:
        try:
            diagnostic_role = DiagnosticRole(str(role))
            if diagnostic_role not in CARD_SLOT_ROLES:
                raise RuntimeEvidenceError("public role must be one frozen card role")
            query = QueryContext(
                query_id=stable_sha256(
                    {
                        "question": str(question),
                        "fault_id": str(fault_id),
                        "role": diagnostic_role.value,
                        "scenario_id": str(scenario_id),
                    }
                )[:24],
                question_zh=question,
                fault_id=fault_id,
                fault_name_zh=fault_name,
                requested_role=diagnostic_role,
                scenario_id=scenario_id,
            )
            ids, mask = self.registry.resolve(
                fault_id=query.fault_id,
                role=query.requested_role,
                available_evidence_ids=available_evidence_ids,
            )
            budget = int(max_points)
            if budget < 1 or budget > 3:
                raise RuntimeEvidenceError("max_points must be in [1, 3]")
            memory = self.tool.resolver.manifest
            graph = memory["teacher_graph"]
            request = SelectPumpEvidenceRequest.create(
                query=query,
                candidate_evidence_ids=ids,
                availability_mask=mask,
                selection_budget=budget,
                memory_id=memory["memory_id"],
                memory_logical_sha256=memory["logical_sha256"],
                teacher_graph_id=graph["id"],
                teacher_graph_sha256=graph["sha256"],
            )
            return self.tool.select_pump_evidence(request)
        except (ContractError, KeyError, TypeError, ValueError):
            # A malformed public request has no trustworthy QueryContext from
            # which to render a response.  Propagate a fact-free contract error
            # to the service layer; never invent missing fault/card metadata.
            raise RuntimeEvidenceError("invalid public select_pump_evidence request")

    __call__ = select_pump_evidence


def select_pump_evidence_audit_schema() -> dict[str, Any]:
    """Low-level audit/replay schema containing all explicit artifact hashes."""

    return {
        "name": AUDIT_TOOL_NAME,
        "description": (
            "Select directly supported pump-system evidence under a bounded "
            "candidate mask and return a deterministic RP2-aligned four-slot diagnosis card."
        ),
        "parameters": {
            "type": "object",
            "required": [
                "query",
                "candidate_evidence_ids",
                "availability_mask",
                "selection_budget",
                "candidate_signature_sha256",
                "memory_id",
                "memory_logical_sha256",
                "teacher_graph_id",
                "teacher_graph_sha256",
                "contract_version",
                "tool_api_version",
            ],
            "properties": {
                "query": {"type": "object"},
                "candidate_evidence_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "availability_mask": {
                    "type": "array",
                    "items": {"type": "boolean"},
                    "minItems": 1,
                },
                "selection_budget": {"type": "integer", "minimum": 1},
                "candidate_signature_sha256": {"type": "string"},
                "memory_id": {"type": "string"},
                "memory_logical_sha256": {"type": "string"},
                "teacher_graph_id": {"type": "string"},
                "teacher_graph_sha256": {"type": "string"},
                "contract_version": {"const": CONTRACT_VERSION},
                "tool_api_version": {"const": TOOL_API_VERSION},
            },
            "additionalProperties": False,
        },
    }


def select_pump_evidence_tool_schema() -> dict[str, Any]:
    """Public schema: artifact hashes and candidate masks stay server-owned."""

    return {
        "name": TOOL_NAME,
        "description": (
            "Select bounded evidence for a known pump fault and diagnostic role; "
            "the server injects frozen candidates and all artifact identities."
        ),
        "parameters": {
            "type": "object",
            "required": [
                "question",
                "fault_id",
                "fault_name",
                "role",
                "scenario_id",
            ],
            "properties": {
                "question": {"type": "string", "minLength": 1},
                "fault_id": {"type": "string", "minLength": 1},
                "fault_name": {"type": "string", "minLength": 1},
                "role": {"enum": [role.value for role in CARD_SLOT_ROLES]},
                "scenario_id": {"type": "string", "minLength": 1},
                "max_points": {"type": "integer", "minimum": 1, "maximum": 3},
                "available_evidence_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
            },
            "additionalProperties": False,
        },
    }


__all__ = [
    "ControllerEvidenceDecision",
    "ControllerFieldPrediction",
    "ControllerPrediction",
    "FrozenCandidateBucket",
    "FrozenCandidateBucketRegistry",
    "EvidenceController",
    "EvidenceMemoryResolver",
    "ResolvedCandidate",
    "RuntimeEvidenceError",
    "SelectPumpEvidenceRequest",
    "SelectPumpEvidenceResponse",
    "SelectPumpEvidenceTool",
    "SelectPumpEvidenceFacade",
    "AUDIT_TOOL_NAME",
    "BUCKET_REGISTRY_ARTIFACT_TYPE",
    "TOOL_API_VERSION",
    "TOOL_NAME",
    "candidate_signature_sha256",
    "select_pump_evidence",
    "select_pump_evidence_audit_schema",
    "select_pump_evidence_tool_schema",
]
