"""Compile the strict teacher graph into governed, ID-addressed RP3 evidence memory."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import (
    CARD_SLOT_ROLES,
    CompactEvidenceRecord,
    ContractError,
    DataSplit,
    DiagnosticRole,
    EvidenceProvenance,
)
from .splits import BUILD_DOCUMENTS


RELATION_ROLE = {
    "manifests_as": DiagnosticRole.SYMPTOM,
    "indicates": DiagnosticRole.SYMPTOM,
    "causes": DiagnosticRole.CAUSE_OR_MECHANISM,
    "evolves_to": DiagnosticRole.CAUSE_OR_MECHANISM,
    "increases_risk_of": DiagnosticRole.CAUSE_OR_MECHANISM,
    "diagnosed_by": DiagnosticRole.INSPECTION,
    "inspected_by": DiagnosticRole.INSPECTION,
    "mitigated_by": DiagnosticRole.MAINTENANCE,
    "prevented_by": DiagnosticRole.MAINTENANCE,
    "maintained_by": DiagnosticRole.MAINTENANCE,
    "operates_under": DiagnosticRole.CONTEXT,
    "specified_by": DiagnosticRole.CONTEXT,
}

UPSTREAM_ROLE = {
    "operating_condition": DiagnosticRole.CONTEXT,
    "standard": DiagnosticRole.CONTEXT,
}


@dataclass(frozen=True)
class MemoryBuildReport:
    record_count: int
    claim_count: int
    document_count: int
    source_family_count: int
    role_counts: dict[str, int]
    bucket_count: int
    maximum_bucket_size: int
    vector_dimension: int


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ContractError(f"invalid JSONL at {path}:{line_number}") from exc
            if not isinstance(value, dict):
                raise ContractError(f"JSONL row must be an object at {path}:{line_number}")
            rows.append(value)
    return rows


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _resolve_role(row: Mapping[str, Any]) -> DiagnosticRole:
    role = str(row.get("evidence_role") or row.get("role") or "").strip()
    if role:
        if role in UPSTREAM_ROLE:
            return UPSTREAM_ROLE[role]
        try:
            return DiagnosticRole(role)
        except ValueError:
            # A declared upstream role is authoritative.  Silently falling
            # back to the relation would turn non-diagnostic standard or
            # operating-condition records into a diagnosis-card field.
            raise ContractError(f"unmapped RP3 evidence role: {role!r}")
    relation = str(row.get("relation") or "")
    if relation not in RELATION_ROLE:
        raise ContractError(f"unmapped RP3 evidence relation: {relation!r}")
    return RELATION_ROLE[relation]


def _graph_eligible(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("decision") or row.get("validation_status") or "")
        in {"silver_candidate", "accepted_silver", "evidence_qualified"}
        and row.get("eligible_for_chinese_graph") is True
        and row.get("inferred_edge") is False
    )


def compile_evidence_memory(
    graph_root: str | Path,
    *,
    split_by_evidence_id: Mapping[str, DataSplit | str] | None = None,
    feature_vectors: Mapping[str, Iterable[float]] | None = None,
) -> tuple[tuple[CompactEvidenceRecord, ...], MemoryBuildReport]:
    """Compile records without embedding or model calls.

    ``feature_vectors`` must be produced offline on the model-capable machine.  If
    supplied, it must cover every evidence ID and use one fixed dimension.
    """

    root = Path(graph_root)
    rows = _read_jsonl(root / "source_records.jsonl")
    split_by_evidence_id = split_by_evidence_id or {}
    feature_vectors = feature_vectors or {}
    records: list[CompactEvidenceRecord] = []
    seen: set[str] = set()
    for row in rows:
        if not _graph_eligible(row):
            raise ContractError(
                "TeacherGraph_RP3_v1 source_records must contain only released, "
                "non-inferred Chinese evidence records"
            )
        evidence_id = str(row.get("evidence_id") or row.get("assertion_id") or "").strip()
        claim_id = str(row.get("claim_id") or "").strip()
        if not evidence_id or not claim_id:
            raise ContractError("teacher evidence requires stable evidence_id and claim_id")
        if evidence_id in seen:
            raise ContractError(f"duplicate evidence ID in teacher graph: {evidence_id}")
        seen.add(evidence_id)
        doc_id = str(row.get("doc_id") or "").strip().upper()
        if doc_id not in BUILD_DOCUMENTS:
            raise ContractError(f"strict teacher graph contains non-build document {doc_id}")
        fault_ids = tuple(sorted(set(_strings(row.get("fault_class_ids")))))
        # Two released strict-208 rows currently have no automatic fault scope.
        # They stay in the immutable teacher memory for identity/audit, but the
        # runtime must never expose them in a fault-scoped candidate bucket.
        if not fault_ids:
            fault_ids = ("__unscoped_nonselectable__",)
        if split_by_evidence_id and evidence_id not in split_by_evidence_id:
            raise ContractError(f"missing group-derived split for evidence {evidence_id}")
        split_value = split_by_evidence_id.get(evidence_id, DataSplit.UNASSIGNED)
        vector = tuple(float(value) for value in feature_vectors.get(evidence_id, ()))
        records.append(
            CompactEvidenceRecord(
                evidence_id=evidence_id,
                claim_id=claim_id,
                head_label_zh=str(row.get("head_canonical_zh") or row.get("head") or ""),
                relation=str(row.get("relation") or ""),
                tail_label_zh=str(row.get("tail_canonical_zh") or row.get("tail") or ""),
                role=_resolve_role(row),
                fault_class_ids=fault_ids,
                evidence_text=str(row.get("evidence_text") or ""),
                provenance=EvidenceProvenance(
                    doc_id=doc_id,
                    physical_pdf_page=int(row.get("pdf_page_number") or 0),
                    source_family_id=str(row.get("source_family_id") or ""),
                    source_url=str(row.get("source_url") or ""),
                    bbox=tuple(row.get("bbox") or ()),
                    document_sha256=str(row.get("document_sha256") or ""),
                    page_sha256=str(row.get("page_text_sha256") or row.get("page_sha256") or ""),
                    evidence_char_start=row.get("evidence_start"),
                    evidence_char_end=row.get("evidence_end"),
                ),
                partition=DataSplit(str(split_value)),
                memory_index=len(records),
                feature_vector=vector,
                evidence_contract_confidence=float(row.get("final_confidence") or 0.0),
                metadata={
                    "evidence_level": str(row.get("evidence_level") or ""),
                    "applicability_scope": str(row.get("applicability_scope") or ""),
                    "terminology_tier": "strict_208",
                    "card_selectable": (
                        _resolve_role(row) in CARD_SLOT_ROLES
                        and fault_ids != ("__unscoped_nonselectable__",)
                    ),
                    "bbox_available": bool(row.get("bbox")),
                    "bbox_unavailable_reason": (
                        "strict_graph_source_record_has_no_bbox"
                        if not row.get("bbox")
                        else ""
                    ),
                    "fault_scope_status": (
                        "missing_nonselectable"
                        if fault_ids == ("__unscoped_nonselectable__",)
                        else "declared"
                    ),
                },
            )
        )
    if feature_vectors:
        missing = sorted(set(seen) - set(feature_vectors))
        unknown = sorted(set(feature_vectors) - set(seen))
        if missing or unknown:
            raise ContractError(
                f"feature-vector IDs disagree with evidence memory; missing={missing}, unknown={unknown}"
            )
    dimensions = {len(record.feature_vector) for record in records}
    if len(dimensions) > 1:
        raise ContractError("all compact evidence feature vectors must use one dimension")
    buckets: dict[tuple[str, str], int] = defaultdict(int)
    for record in records:
        for fault_id in record.fault_class_ids:
            buckets[(fault_id, record.role.value)] += 1
    report = MemoryBuildReport(
        record_count=len(records),
        claim_count=len({record.claim_id for record in records}),
        document_count=len({record.provenance.doc_id for record in records}),
        source_family_count=len({record.provenance.source_family_id for record in records}),
        role_counts=dict(sorted(Counter(record.role.value for record in records).items())),
        bucket_count=len(buckets),
        maximum_bucket_size=max(buckets.values(), default=0),
        vector_dimension=next(iter(dimensions), 0),
    )
    return tuple(records), report


def apply_memory_splits(
    records: Iterable[CompactEvidenceRecord],
    split_by_evidence_id: Mapping[str, DataSplit | str],
) -> tuple[CompactEvidenceRecord, ...]:
    result = []
    for record in records:
        if record.evidence_id not in split_by_evidence_id:
            raise ContractError(f"missing split for evidence {record.evidence_id}")
        result.append(
            replace(record, partition=DataSplit(str(split_by_evidence_id[record.evidence_id])))
        )
    return tuple(result)
