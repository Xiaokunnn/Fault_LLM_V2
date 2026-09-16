"""Typed data contracts for research-point-3 decision distillation.

The classes in this module deliberately describe *teacher-generated supervision*.
They do not imply expert-confirmed truth.  Runtime text rendering stays outside the
contract: a student predicts evidence pointers, field states, and a route action;
the referenced evidence is resolved verbatim from the compact evidence memory.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


CONTRACT_VERSION = "rp3_evidence_contract_v1"
CARD_SCHEMA_VERSION = "rp3_complete_diagnosis_card_v1"


class ContractError(ValueError):
    """Raised when an RP3 record violates an executable data contract."""


class _StringEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class DiagnosticRole(_StringEnum):
    SYMPTOM = "symptom"
    CAUSE_OR_MECHANISM = "cause_or_mechanism"
    INSPECTION = "inspection"
    MAINTENANCE = "maintenance"
    # Reserved for a future, separately governed safety teacher.  RP2 v6 has
    # no safety-warning query or label, so this enum value is intentionally not
    # part of the frozen trainable card schema below.
    SAFETY_WARNING = "safety_warning"
    # Contextual evidence remains addressable in the frozen 208-record memory,
    # but can never be rendered as a diagnosis-card field.
    CONTEXT = "context"
    FULL_CARD = "full_card"


CARD_SLOT_ROLES = (
    DiagnosticRole.SYMPTOM,
    DiagnosticRole.CAUSE_OR_MECHANISM,
    DiagnosticRole.INSPECTION,
    DiagnosticRole.MAINTENANCE,
)


class SupportVerdict(_StringEnum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    IRRELEVANT = "irrelevant"
    NOT_ASSESSED = "not_assessed"


class CardFieldState(_StringEnum):
    SUPPORTED = "supported"
    INSUFFICIENT = "insufficient"
    NOT_APPLICABLE = "not_applicable"
    CONFLICT = "conflict"


class CardStatus(_StringEnum):
    ANSWERED = "answered"
    PARTIAL = "partial"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class RouteAction(_StringEnum):
    ANSWER = "answer"
    FALLBACK = "fallback"
    ABSTAIN = "abstain"


class DataSplit(_StringEnum):
    UNASSIGNED = "unassigned"
    TRAIN = "train"
    VALIDATION = "validation"
    DEVELOPMENT = "development"
    EXTERNAL_EVALUATION = "external_evaluation"


def _enum(enum_type: type[_StringEnum], value: Any, name: str) -> _StringEnum:
    try:
        return enum_type(str(value))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ContractError(f"{name} must be one of: {allowed}") from exc


def _text(value: Any, name: str, *, allow_empty: bool = False) -> str:
    text = str(value or "").strip()
    if not text and not allow_empty:
        raise ContractError(f"{name} must be non-empty")
    return text


def _strings(values: Iterable[Any] | None, name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ContractError(f"{name} must be an array, not a scalar string")
    result = tuple(_text(value, name) for value in (values or ()))
    if len(set(result)) != len(result):
        raise ContractError(f"{name} must not contain duplicates")
    return result


def _finite(value: Any, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ContractError(f"{name} must be finite")
    return number


def _json_dict(value: Mapping[str, Any] | None, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be a JSON object")
    return dict(value)


@dataclass(frozen=True)
class QueryContext:
    query_id: str
    question_zh: str
    fault_id: str
    fault_name_zh: str
    requested_role: DiagnosticRole
    scenario_id: str
    operating_context: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("query_id", "question_zh", "fault_id", "fault_name_zh", "scenario_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "requested_role",
            _enum(DiagnosticRole, self.requested_role, "requested_role"),
        )
        object.__setattr__(
            self,
            "operating_context",
            _strings(self.operating_context, "operating_context"),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["requested_role"] = self.requested_role.value
        data["operating_context"] = list(self.operating_context)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QueryContext":
        # ``role`` is accepted only as an adapter for frozen RP2 rows.
        return cls(
            query_id=data.get("query_id", ""),
            question_zh=data.get("question_zh", data.get("question", "")),
            fault_id=data.get("fault_id", ""),
            fault_name_zh=data.get("fault_name_zh", data.get("fault_name", "")),
            requested_role=data.get("requested_role", data.get("role", "")),
            scenario_id=data.get("scenario_id", data.get("base_scenario_id", "")),
            operating_context=tuple(data.get("operating_context", ())),
        )


@dataclass(frozen=True)
class EvidenceProvenance:
    doc_id: str
    physical_pdf_page: int
    source_family_id: str
    source_url: str = ""
    bbox: tuple[float, ...] = ()
    document_sha256: str = ""
    page_sha256: str = ""
    evidence_char_start: int | None = None
    evidence_char_end: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "doc_id", _text(self.doc_id, "doc_id"))
        object.__setattr__(
            self, "source_family_id", _text(self.source_family_id, "source_family_id")
        )
        page = int(self.physical_pdf_page)
        if page < 1:
            raise ContractError("physical_pdf_page must be >= 1")
        object.__setattr__(self, "physical_pdf_page", page)
        bbox = tuple(_finite(value, "bbox") for value in self.bbox)
        if bbox and len(bbox) != 4:
            raise ContractError("bbox must be empty or contain exactly four coordinates")
        object.__setattr__(self, "bbox", bbox)
        for name in ("source_url", "document_sha256", "page_sha256"):
            object.__setattr__(self, name, _text(getattr(self, name), name, allow_empty=True))
        start = self.evidence_char_start
        end = self.evidence_char_end
        if (start is None) != (end is None):
            raise ContractError(
                "evidence_char_start and evidence_char_end must either both be set or both be absent"
            )
        if start is not None:
            start = int(start)
            end = int(end)
            if start < 0 or end <= start:
                raise ContractError("evidence character offsets must satisfy 0 <= start < end")
            object.__setattr__(self, "evidence_char_start", start)
            object.__setattr__(self, "evidence_char_end", end)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["bbox"] = list(self.bbox)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceProvenance":
        return cls(
            doc_id=data.get("doc_id", ""),
            physical_pdf_page=data.get(
                "physical_pdf_page", data.get("pdf_page_number", data.get("pdf_page", 0))
            ),
            source_family_id=data.get("source_family_id", ""),
            source_url=data.get("source_url", ""),
            bbox=tuple(data.get("bbox", ())),
            document_sha256=data.get("document_sha256", data.get("doc_hash", "")),
            page_sha256=data.get("page_sha256", data.get("page_hash", "")),
            evidence_char_start=data.get("evidence_char_start", data.get("evidence_start")),
            evidence_char_end=data.get("evidence_char_end", data.get("evidence_end")),
        )


@dataclass(frozen=True)
class CompactEvidenceRecord:
    """ID-addressed evidence payload stored on the edge.

    ``feature_vector`` may hold a compressed or projected vector.  It is optional
    because a deployment may store vectors in a separate binary matrix addressed
    by ``memory_index``.
    """

    evidence_id: str
    claim_id: str
    head_label_zh: str
    relation: str
    tail_label_zh: str
    role: DiagnosticRole
    fault_class_ids: tuple[str, ...]
    evidence_text: str
    provenance: EvidenceProvenance
    partition: DataSplit
    memory_index: int
    feature_vector: tuple[float, ...] = ()
    evidence_contract_confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "claim_id",
            "head_label_zh",
            "relation",
            "tail_label_zh",
            "evidence_text",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "role", _enum(DiagnosticRole, self.role, "role"))
        if self.role == DiagnosticRole.FULL_CARD:
            raise ContractError("an evidence record cannot have role=full_card")
        fault_ids = _strings(self.fault_class_ids, "fault_class_ids")
        if not fault_ids:
            raise ContractError("fault_class_ids must contain at least one fault")
        object.__setattr__(self, "fault_class_ids", fault_ids)
        if not isinstance(self.provenance, EvidenceProvenance):
            object.__setattr__(self, "provenance", EvidenceProvenance.from_dict(self.provenance))
        object.__setattr__(self, "partition", _enum(DataSplit, self.partition, "partition"))
        index = int(self.memory_index)
        if index < 0:
            raise ContractError("memory_index must be >= 0")
        object.__setattr__(self, "memory_index", index)
        object.__setattr__(
            self,
            "feature_vector",
            tuple(_finite(value, "feature_vector") for value in self.feature_vector),
        )
        if self.evidence_contract_confidence is not None:
            confidence = _finite(
                self.evidence_contract_confidence, "evidence_contract_confidence"
            )
            if not 0.0 <= confidence <= 1.0:
                raise ContractError("evidence_contract_confidence must be in [0, 1]")
            object.__setattr__(self, "evidence_contract_confidence", confidence)
        object.__setattr__(self, "metadata", _json_dict(self.metadata, "metadata"))

    @property
    def canonical_claim(self) -> str:
        return f"{self.head_label_zh} --{self.relation}--> {self.tail_label_zh}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "claim_id": self.claim_id,
            "head_label_zh": self.head_label_zh,
            "relation": self.relation,
            "tail_label_zh": self.tail_label_zh,
            "role": self.role.value,
            "fault_class_ids": list(self.fault_class_ids),
            "evidence_text": self.evidence_text,
            "provenance": self.provenance.to_dict(),
            "partition": self.partition.value,
            "memory_index": self.memory_index,
            "feature_vector": list(self.feature_vector),
            "evidence_contract_confidence": self.evidence_contract_confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompactEvidenceRecord":
        provenance = data.get("provenance")
        if provenance is None:
            provenance = data
        return cls(
            evidence_id=data.get("evidence_id", ""),
            claim_id=data.get("claim_id", ""),
            head_label_zh=data.get("head_label_zh", data.get("head_canonical_zh", "")),
            relation=data.get("relation", ""),
            tail_label_zh=data.get("tail_label_zh", data.get("tail_canonical_zh", "")),
            role=data.get("role", ""),
            fault_class_ids=tuple(data.get("fault_class_ids", ())),
            evidence_text=data.get("evidence_text", ""),
            provenance=EvidenceProvenance.from_dict(provenance),
            partition=data.get("partition", DataSplit.UNASSIGNED.value),
            memory_index=data.get("memory_index", 0),
            feature_vector=tuple(data.get("feature_vector", ())),
            evidence_contract_confidence=data.get(
                "evidence_contract_confidence", data.get("final_confidence")
            ),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class TeacherEvidenceDecision:
    evidence_id: str
    rank: int
    teacher_score: float
    support: SupportVerdict
    selected: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _text(self.evidence_id, "evidence_id"))
        rank = int(self.rank)
        if rank < 1:
            raise ContractError("rank must be >= 1")
        object.__setattr__(self, "rank", rank)
        object.__setattr__(self, "teacher_score", _finite(self.teacher_score, "teacher_score"))
        object.__setattr__(self, "support", _enum(SupportVerdict, self.support, "support"))
        if type(self.selected) is not bool:
            raise ContractError("selected must be a JSON boolean")
        if self.selected and self.support != SupportVerdict.DIRECT:
            raise ContractError("selected evidence must have support=direct")

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "rank": self.rank,
            "teacher_score": self.teacher_score,
            "support": self.support.value,
            "selected": self.selected,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TeacherEvidenceDecision":
        return cls(
            evidence_id=data.get("evidence_id", ""),
            rank=data.get("rank", 0),
            teacher_score=data.get("teacher_score", data.get("score", 0.0)),
            support=data.get("support", data.get("verdict", SupportVerdict.NOT_ASSESSED.value)),
            selected=data.get("selected", False),
        )


@dataclass(frozen=True)
class CardItem:
    item_id: str
    text_zh: str
    evidence_ids: tuple[str, ...]
    order: int = 1
    applicability_conditions: tuple[str, ...] = ()
    action_boundary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", _text(self.item_id, "item_id"))
        object.__setattr__(self, "text_zh", _text(self.text_zh, "text_zh"))
        evidence_ids = _strings(self.evidence_ids, "evidence_ids")
        if not evidence_ids:
            raise ContractError("a card item must cite at least one evidence_id")
        object.__setattr__(self, "evidence_ids", evidence_ids)
        order = int(self.order)
        if order < 1:
            raise ContractError("card item order must be >= 1")
        object.__setattr__(self, "order", order)
        object.__setattr__(
            self,
            "applicability_conditions",
            _strings(self.applicability_conditions, "applicability_conditions"),
        )
        object.__setattr__(
            self, "action_boundary", _text(self.action_boundary, "action_boundary", allow_empty=True)
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_ids"] = list(self.evidence_ids)
        data["applicability_conditions"] = list(self.applicability_conditions)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CardItem":
        return cls(
            item_id=data.get("item_id", ""),
            text_zh=data.get("text_zh", data.get("text", "")),
            evidence_ids=tuple(data.get("evidence_ids", ())),
            order=data.get("order", 1),
            applicability_conditions=tuple(data.get("applicability_conditions", ())),
            action_boundary=data.get("action_boundary", ""),
        )


@dataclass(frozen=True)
class DiagnosisCardSlot:
    role: DiagnosticRole
    state: CardFieldState
    items: tuple[CardItem, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _enum(DiagnosticRole, self.role, "role"))
        if self.role not in CARD_SLOT_ROLES:
            raise ContractError("diagnosis-card slot role must be a concrete card field")
        object.__setattr__(self, "state", _enum(CardFieldState, self.state, "state"))
        items = tuple(
            item if isinstance(item, CardItem) else CardItem.from_dict(item) for item in self.items
        )
        item_ids = [item.item_id for item in items]
        if len(set(item_ids)) != len(item_ids):
            raise ContractError("card item IDs must be unique within a slot")
        orders = [item.order for item in items]
        if len(set(orders)) != len(orders):
            raise ContractError("card item order values must be unique within a slot")
        if self.state == CardFieldState.SUPPORTED and not items:
            raise ContractError("a supported card slot must contain at least one item")
        if self.state in {CardFieldState.INSUFFICIENT, CardFieldState.NOT_APPLICABLE} and items:
            raise ContractError(f"a {self.state.value} card slot must not contain items")
        object.__setattr__(self, "items", tuple(sorted(items, key=lambda item: item.order)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "state": self.state.value,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DiagnosisCardSlot":
        return cls(
            role=data.get("role", ""),
            state=data.get("state", ""),
            items=tuple(CardItem.from_dict(item) for item in data.get("items", ())),
        )


@dataclass(frozen=True)
class EvidenceConflict:
    conflict_id: str
    evidence_ids: tuple[str, ...]
    description_zh: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conflict_id", _text(self.conflict_id, "conflict_id"))
        evidence_ids = _strings(self.evidence_ids, "evidence_ids")
        if len(evidence_ids) < 2:
            raise ContractError("an evidence conflict must reference at least two evidence IDs")
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(
            self, "description_zh", _text(self.description_zh, "description_zh")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "evidence_ids": list(self.evidence_ids),
            "description_zh": self.description_zh,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceConflict":
        return cls(
            conflict_id=data.get("conflict_id", ""),
            evidence_ids=tuple(data.get("evidence_ids", ())),
            description_zh=data.get("description_zh", data.get("description", "")),
        )


@dataclass(frozen=True)
class DiagnosisCard:
    card_id: str
    status: CardStatus
    fault_ids: tuple[str, ...]
    applicability_conditions: tuple[str, ...]
    slots: tuple[DiagnosisCardSlot, ...]
    conflicts: tuple[EvidenceConflict, ...] = ()
    schema_version: str = CARD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "card_id", _text(self.card_id, "card_id"))
        object.__setattr__(self, "status", _enum(CardStatus, self.status, "status"))
        fault_ids = _strings(self.fault_ids, "fault_ids")
        if not fault_ids:
            raise ContractError("diagnosis card must declare at least one candidate fault")
        object.__setattr__(self, "fault_ids", fault_ids)
        object.__setattr__(
            self,
            "applicability_conditions",
            _strings(self.applicability_conditions, "applicability_conditions"),
        )
        slots = tuple(
            slot if isinstance(slot, DiagnosisCardSlot) else DiagnosisCardSlot.from_dict(slot)
            for slot in self.slots
        )
        roles = tuple(slot.role for slot in slots)
        if len(set(roles)) != len(roles):
            raise ContractError("diagnosis-card slot roles must be unique")
        missing = set(CARD_SLOT_ROLES) - set(roles)
        extra = set(roles) - set(CARD_SLOT_ROLES)
        if missing or extra:
            raise ContractError(
                "complete diagnosis card requires exactly these slots: "
                + ", ".join(role.value for role in CARD_SLOT_ROLES)
            )
        object.__setattr__(
            self,
            "slots",
            tuple(next(slot for slot in slots if slot.role == role) for role in CARD_SLOT_ROLES),
        )
        conflicts = tuple(
            item if isinstance(item, EvidenceConflict) else EvidenceConflict.from_dict(item)
            for item in self.conflicts
        )
        object.__setattr__(self, "conflicts", conflicts)
        object.__setattr__(self, "schema_version", _text(self.schema_version, "schema_version"))
        supported_count = sum(slot.state == CardFieldState.SUPPORTED for slot in slots)
        if self.status == CardStatus.ANSWERED and supported_count == 0:
            raise ContractError("an answered card must have a supported field")
        if self.status == CardStatus.INSUFFICIENT_EVIDENCE and supported_count:
            raise ContractError("an insufficient-evidence card cannot have supported fields")
        if self.status == CardStatus.CONFLICTING_EVIDENCE and not conflicts:
            raise ContractError("a conflicting-evidence card must describe at least one conflict")

    @property
    def cited_evidence_ids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                evidence_id
                for slot in self.slots
                for item in slot.items
                for evidence_id in item.evidence_ids
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "status": self.status.value,
            "fault_ids": list(self.fault_ids),
            "applicability_conditions": list(self.applicability_conditions),
            "slots": [slot.to_dict() for slot in self.slots],
            "conflicts": [item.to_dict() for item in self.conflicts],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DiagnosisCard":
        return cls(
            card_id=data.get("card_id", ""),
            status=data.get("status", ""),
            fault_ids=tuple(data.get("fault_ids", ())),
            applicability_conditions=tuple(data.get("applicability_conditions", ())),
            slots=tuple(DiagnosisCardSlot.from_dict(slot) for slot in data.get("slots", ())),
            conflicts=tuple(
                EvidenceConflict.from_dict(item) for item in data.get("conflicts", ())
            ),
            schema_version=data.get("schema_version", CARD_SCHEMA_VERSION),
        )


@dataclass(frozen=True)
class RouteDecision:
    action: RouteAction
    reason_codes: tuple[str, ...]
    estimated_student_cost: float
    estimated_teacher_cost: float
    estimated_error_cost: float
    confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", _enum(RouteAction, self.action, "action"))
        reason_codes = _strings(self.reason_codes, "reason_codes")
        if not reason_codes:
            raise ContractError("route decision must contain at least one reason code")
        object.__setattr__(self, "reason_codes", reason_codes)
        for name in (
            "estimated_student_cost",
            "estimated_teacher_cost",
            "estimated_error_cost",
        ):
            value = _finite(getattr(self, name), name)
            if value < 0:
                raise ContractError(f"{name} must be >= 0")
            object.__setattr__(self, name, value)
        confidence = _finite(self.confidence, "confidence")
        if not 0.0 <= confidence <= 1.0:
            raise ContractError("route confidence must be in [0, 1]")
        object.__setattr__(self, "confidence", confidence)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["action"] = self.action.value
        data["reason_codes"] = list(self.reason_codes)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RouteDecision":
        return cls(
            action=data.get("action", ""),
            reason_codes=tuple(data.get("reason_codes", ())),
            estimated_student_cost=data.get("estimated_student_cost", 0.0),
            estimated_teacher_cost=data.get("estimated_teacher_cost", 0.0),
            estimated_error_cost=data.get("estimated_error_cost", 0.0),
            confidence=data.get("confidence", 0.0),
        )


@dataclass(frozen=True)
class TeacherTrace:
    trace_id: str
    query: QueryContext
    candidate_evidence_ids: tuple[str, ...]
    availability_mask: tuple[bool, ...]
    selection_budget: int
    underfill_reason_codes: tuple[str, ...]
    evidence_decisions: tuple[TeacherEvidenceDecision, ...]
    diagnosis_card: DiagnosisCard
    route: RouteDecision
    split: DataSplit
    claim_group_ids: tuple[str, ...]
    document_group_ids: tuple[str, ...]
    source_family_group_ids: tuple[str, ...]
    teacher_graph_id: str
    teacher_replay_id: str
    perturbation_id: str = "original"
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _text(self.trace_id, "trace_id"))
        if not isinstance(self.query, QueryContext):
            object.__setattr__(self, "query", QueryContext.from_dict(self.query))
        candidates = _strings(self.candidate_evidence_ids, "candidate_evidence_ids")
        object.__setattr__(self, "candidate_evidence_ids", candidates)
        if any(type(value) is not bool for value in self.availability_mask):
            raise ContractError("availability_mask must contain only JSON booleans")
        mask = tuple(self.availability_mask)
        if len(mask) != len(candidates):
            raise ContractError("availability_mask length must equal candidate_evidence_ids length")
        object.__setattr__(self, "availability_mask", mask)
        decisions = tuple(
            item
            if isinstance(item, TeacherEvidenceDecision)
            else TeacherEvidenceDecision.from_dict(item)
            for item in self.evidence_decisions
        )
        decision_ids = tuple(item.evidence_id for item in decisions)
        if decision_ids != candidates:
            raise ContractError(
                "evidence_decisions must align one-to-one with candidate_evidence_ids order"
            )
        ranks = tuple(item.rank for item in decisions)
        if sorted(ranks) != list(range(1, len(decisions) + 1)):
            raise ContractError("teacher evidence ranks must be a permutation of 1..N")
        available_by_id = dict(zip(candidates, mask))
        selected = {item.evidence_id for item in decisions if item.selected}
        unavailable_selected = sorted(eid for eid in selected if not available_by_id[eid])
        if unavailable_selected:
            raise ContractError(
                "unavailable evidence cannot be selected: " + ", ".join(unavailable_selected)
            )
        object.__setattr__(self, "evidence_decisions", decisions)
        selection_budget = int(self.selection_budget)
        if selection_budget < 1:
            raise ContractError("selection_budget must be >= 1")
        object.__setattr__(self, "selection_budget", selection_budget)
        underfill_reason_codes = _strings(
            self.underfill_reason_codes, "underfill_reason_codes"
        )
        if len(selected) > selection_budget:
            raise ContractError("teacher-selected evidence exceeds selection_budget")
        if len(selected) < selection_budget and not underfill_reason_codes:
            raise ContractError(
                "active underfilling must declare at least one underfill reason code"
            )
        if len(selected) == selection_budget and underfill_reason_codes:
            raise ContractError(
                "underfill reason codes must be empty when the selection budget is full"
            )
        object.__setattr__(self, "underfill_reason_codes", underfill_reason_codes)
        if not isinstance(self.diagnosis_card, DiagnosisCard):
            object.__setattr__(
                self, "diagnosis_card", DiagnosisCard.from_dict(self.diagnosis_card)
            )
        if self.query.fault_id not in self.diagnosis_card.fault_ids:
            raise ContractError("diagnosis card must include the query fault_id")
        if not set(self.diagnosis_card.cited_evidence_ids).issubset(selected):
            raise ContractError("every diagnosis-card evidence pointer must be teacher-selected")
        conflict_evidence = {
            evidence_id
            for conflict in self.diagnosis_card.conflicts
            for evidence_id in conflict.evidence_ids
        }
        if not conflict_evidence.issubset(set(candidates)):
            raise ContractError("diagnosis-card conflicts must reference candidate evidence")
        if not isinstance(self.route, RouteDecision):
            object.__setattr__(self, "route", RouteDecision.from_dict(self.route))
        if self.route.action == RouteAction.ANSWER:
            if self.diagnosis_card.status not in {CardStatus.ANSWERED, CardStatus.PARTIAL}:
                raise ContractError("route=answer requires an answered or partial card")
            if not selected:
                raise ContractError("route=answer requires at least one selected evidence pointer")
        else:
            # Ranking/support labels may still retain the teacher's internal
            # pointers for fallback/abstain supervision, but the local result
            # is not accepted as an answer.  Its rendered card must therefore
            # be fact-free rather than leaking rejected teacher propositions.
            if self.diagnosis_card.status != CardStatus.INSUFFICIENT_EVIDENCE:
                raise ContractError(
                    "route=fallback/abstain requires an insufficient-evidence card"
                )
            if self.diagnosis_card.cited_evidence_ids or self.diagnosis_card.conflicts:
                raise ContractError(
                    "route=fallback/abstain diagnosis card must contain no factual pointers"
                )
            if any(
                slot.items or slot.state not in {
                    CardFieldState.INSUFFICIENT,
                    CardFieldState.NOT_APPLICABLE,
                }
                for slot in self.diagnosis_card.slots
            ):
                raise ContractError(
                    "route=fallback/abstain requires a fact-free served diagnosis card"
                )
        object.__setattr__(self, "split", _enum(DataSplit, self.split, "split"))
        for name in (
            "claim_group_ids",
            "document_group_ids",
            "source_family_group_ids",
        ):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        if not (
            self.query.scenario_id
            or self.claim_group_ids
            or self.document_group_ids
            or self.source_family_group_ids
        ):
            raise ContractError("trace must expose at least one leakage-control grouping key")
        for name in ("teacher_graph_id", "teacher_replay_id", "perturbation_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "metadata", _json_dict(self.metadata, "metadata"))
        object.__setattr__(
            self, "contract_version", _text(self.contract_version, "contract_version")
        )

    @property
    def selected_evidence_ids(self) -> tuple[str, ...]:
        return tuple(
            item.evidence_id
            for item in sorted(self.evidence_decisions, key=lambda item: item.rank)
            if item.selected
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "query": self.query.to_dict(),
            "candidate_evidence_ids": list(self.candidate_evidence_ids),
            "availability_mask": list(self.availability_mask),
            "selection_budget": self.selection_budget,
            "underfill_reason_codes": list(self.underfill_reason_codes),
            "evidence_decisions": [item.to_dict() for item in self.evidence_decisions],
            "diagnosis_card": self.diagnosis_card.to_dict(),
            "route": self.route.to_dict(),
            "split": self.split.value,
            "claim_group_ids": list(self.claim_group_ids),
            "document_group_ids": list(self.document_group_ids),
            "source_family_group_ids": list(self.source_family_group_ids),
            "teacher_graph_id": self.teacher_graph_id,
            "teacher_replay_id": self.teacher_replay_id,
            "perturbation_id": self.perturbation_id,
            "metadata": self.metadata,
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TeacherTrace":
        return cls(
            trace_id=data.get("trace_id", ""),
            query=QueryContext.from_dict(data.get("query", {})),
            candidate_evidence_ids=tuple(data.get("candidate_evidence_ids", ())),
            availability_mask=tuple(data.get("availability_mask", ())),
            selection_budget=data.get("selection_budget", 3),
            underfill_reason_codes=tuple(data.get("underfill_reason_codes", ())),
            evidence_decisions=tuple(
                TeacherEvidenceDecision.from_dict(item)
                for item in data.get("evidence_decisions", ())
            ),
            diagnosis_card=DiagnosisCard.from_dict(data.get("diagnosis_card", {})),
            route=RouteDecision.from_dict(data.get("route", {})),
            split=data.get("split", DataSplit.UNASSIGNED.value),
            claim_group_ids=tuple(data.get("claim_group_ids", ())),
            document_group_ids=tuple(data.get("document_group_ids", ())),
            source_family_group_ids=tuple(data.get("source_family_group_ids", ())),
            teacher_graph_id=data.get("teacher_graph_id", ""),
            teacher_replay_id=data.get("teacher_replay_id", ""),
            perturbation_id=data.get("perturbation_id", "original"),
            metadata=data.get("metadata", {}),
            contract_version=data.get("contract_version", CONTRACT_VERSION),
        )


def validate_unique_trace_ids(traces: Iterable[TeacherTrace]) -> tuple[TeacherTrace, ...]:
    result = tuple(traces)
    ids = [trace.trace_id for trace in result]
    if len(set(ids)) != len(ids):
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        raise ContractError("duplicate trace IDs: " + ", ".join(duplicates))
    return result


def validate_compact_memory(
    records: Iterable[CompactEvidenceRecord],
) -> tuple[CompactEvidenceRecord, ...]:
    result = tuple(records)
    evidence_ids = [record.evidence_id for record in result]
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ContractError("compact evidence memory contains duplicate evidence IDs")
    indices = [record.memory_index for record in result]
    if sorted(indices) != list(range(len(result))):
        raise ContractError("memory_index values must be a contiguous permutation of 0..N-1")
    dimensions = {len(record.feature_vector) for record in result if record.feature_vector}
    if len(dimensions) > 1:
        raise ContractError("all non-empty compact feature vectors must have one dimension")
    return result
