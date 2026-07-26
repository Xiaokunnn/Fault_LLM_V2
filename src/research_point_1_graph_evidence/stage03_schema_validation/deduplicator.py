"""Stable identifiers and evidence-preserving candidate deduplication."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping
import unicodedata


SEPARATOR = "\u241f"


def normalize_identity_text(value: object) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", str(value or "")).casefold().split()
    )


def _stable_id(prefix: str, parts: Iterable[object]) -> str:
    identity = SEPARATOR.join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]}"


def stable_entity_id(
    label: str,
    node_type: str,
    *,
    terminology_id: str | None = None,
) -> str:
    return _stable_id(
        "MPE",
        (
            node_type,
            (
                f"terminology:{terminology_id}"
                if terminology_id
                else f"label:{normalize_identity_text(label)}"
            ),
        ),
    )


def stable_claim_id(
    head_entity_id: str,
    relation: str,
    tail_entity_id: str,
    *,
    schema_major_version: str = "2",
) -> str:
    return _stable_id(
        "MPC",
        (schema_major_version, head_entity_id, relation, tail_entity_id),
    )


def stable_evidence_id(
    record: Mapping[str, object], *, claim_id: str | None = None
) -> str:
    if claim_id is None:
        claim_id = str(record.get("claim_id") or "")
    if not claim_id and all(
        key in record
        for key in ("head", "head_type", "relation", "tail", "tail_type")
    ):
        head_id = stable_entity_id(
            str(
                record.get("head_canonical_zh")
                or record.get("head_normalized")
                or record.get("head", "")
            ),
            str(record.get("head_type", "")),
            terminology_id=(
                str(record.get("head_terminology_id"))
                if record.get("head_terminology_id")
                else None
            ),
        )
        tail_id = stable_entity_id(
            str(
                record.get("tail_canonical_zh")
                or record.get("tail_normalized")
                or record.get("tail", "")
            ),
            str(record.get("tail_type", "")),
            terminology_id=(
                str(record.get("tail_terminology_id"))
                if record.get("tail_terminology_id")
                else None
            ),
        )
        claim_id = stable_claim_id(
            head_id, str(record.get("relation", "")), tail_id
        )
    units = record.get("evidence_units") or []
    serialized_units = json.dumps(
        units, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return _stable_id(
        "MPA",
        (
            claim_id,
            record.get("doc_id", ""),
            record.get("pdf_page_number", ""),
            record.get("printed_page_label", ""),
            record.get("evidence_start", ""),
            record.get("evidence_end", ""),
            record.get("evidence_text", ""),
            serialized_units,
        ),
    )


def stable_triple_id(claim_id: str, evidence_id: str) -> str:
    return _stable_id("MPT", (claim_id, evidence_id))


def enrich_stable_ids(record: Mapping[str, object]) -> dict[str, object]:
    result = dict(record)
    head_id = str(
        result.get("head_entity_id")
        or stable_entity_id(
            str(
                result.get("head_canonical_zh")
                or result.get("head_normalized")
                or result.get("head", "")
            ),
            str(result.get("head_type", "")),
            terminology_id=(
                str(result.get("head_terminology_id"))
                if result.get("head_terminology_id")
                else None
            ),
        )
    )
    tail_id = str(
        result.get("tail_entity_id")
        or stable_entity_id(
            str(
                result.get("tail_canonical_zh")
                or result.get("tail_normalized")
                or result.get("tail", "")
            ),
            str(result.get("tail_type", "")),
            terminology_id=(
                str(result.get("tail_terminology_id"))
                if result.get("tail_terminology_id")
                else None
            ),
        )
    )
    claim_id = str(
        result.get("claim_id")
        or stable_claim_id(head_id, str(result.get("relation", "")), tail_id)
    )
    evidence_id = str(
        result.get("evidence_id")
        or stable_evidence_id(result, claim_id=claim_id)
    )
    triple_id = stable_triple_id(claim_id, evidence_id)
    result.update(
        {
            "head_entity_id": head_id,
            "tail_entity_id": tail_id,
            "claim_id": claim_id,
            "evidence_id": evidence_id,
            "assertion_id": evidence_id,
            "triple_id": triple_id,
        }
    )
    return result


@dataclass(frozen=True)
class DeduplicationResult:
    records: tuple[dict[str, object], ...]
    duplicates_removed: int


def deduplicate_triples(
    records: Iterable[Mapping[str, object]],
) -> DeduplicationResult:
    """Remove exact claim/evidence duplicates, retaining distinct evidence."""

    by_id: dict[str, dict[str, object]] = {}
    count = 0
    for source_record in records:
        count += 1
        record = enrich_stable_ids(source_record)
        triple_id = str(record["triple_id"])
        existing = by_id.get(triple_id)
        if existing is None:
            by_id[triple_id] = record
            continue
        existing_confidence = float(
            existing.get("final_confidence", existing.get("triple_confidence", 0))
            or 0
        )
        new_confidence = float(
            record.get("final_confidence", record.get("triple_confidence", 0))
            or 0
        )
        if new_confidence > existing_confidence:
            by_id[triple_id] = record
    ordered = tuple(by_id[key] for key in sorted(by_id))
    return DeduplicationResult(
        records=ordered,
        duplicates_removed=count - len(ordered),
    )
