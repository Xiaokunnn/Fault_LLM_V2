"""Deterministic artifact I/O for RP3 teacher traces and evidence memories."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import (
    CONTRACT_VERSION,
    CompactEvidenceRecord,
    ContractError,
    TeacherTrace,
    validate_compact_memory,
    validate_unique_trace_ids,
)
from .splits import assert_memory_partition_boundary, assert_training_trace_boundary


TRACE_FILENAME = "teacher_traces.jsonl"
MEMORY_FILENAME = "evidence_memory.jsonl"
MANIFEST_FILENAME = "manifest.json"


def _require_sha256(value: str, name: str) -> str:
    digest = str(value).strip().lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ContractError(f"{name} must be a 64-character hexadecimal SHA-256")
    return digest


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, set):
        return sorted(_plain(item) for item in value)
    return value


def canonical_json_bytes(value: Any, *, newline: bool = True) -> bytes:
    text = json.dumps(
        _plain(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return (text + ("\n" if newline else "")).encode("utf-8")


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value, newline=False)).hexdigest()


def file_sha256(path: str | Path) -> str:
    """Hash exact file bytes; required for checkpoints, ONNX and binary indexes."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_text_sha256(path: str | Path) -> str:
    """Hash a controlled UTF-8 text artifact after CRLF-to-LF normalization."""

    payload = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


def canonical_jsonl_bytes(rows: Iterable[Any]) -> bytes:
    return b"".join(canonical_json_bytes(row) for row in rows)


def _write_immutable(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes().replace(b"\r\n", b"\n")
        if existing != payload.replace(b"\r\n", b"\n"):
            raise RuntimeError(
                f"refusing to overwrite non-identical frozen RP3 artifact: {path}"
            )
        return "verified"
    path.write_bytes(payload)
    return "created"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ContractError(f"invalid JSON at {path}:{line_number}") from exc
            if not isinstance(value, dict):
                raise ContractError(f"JSONL record at {path}:{line_number} must be an object")
            rows.append(value)
    return rows


def _bundle_data_path(output: Path, declared: Any, default: str) -> Path:
    """Resolve a manifest data file without permitting path traversal."""

    relative = Path(str(declared or default))
    if relative.is_absolute():
        raise ContractError("bundle data_file must be relative")
    root = output.resolve()
    candidate = (output / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ContractError("bundle data_file escapes the bundle directory") from exc
    return candidate


def write_teacher_trace_bundle(
    output_dir: str | Path,
    traces: Iterable[TeacherTrace],
    *,
    dataset_id: str,
    teacher_graph_id: str,
    teacher_graph_sha256: str,
    teacher_replay_id: str,
    teacher_replay_sha256: str,
    candidate_trace_sha256: str,
    candidate_trace_manifest_sha256: str,
    teacher_system_identity_sha256: str,
    split_protocol: Mapping[str, Any],
    validation_report: Mapping[str, Any] | None = None,
    purpose: str = "training",
) -> dict[str, Any]:
    teacher_graph_id = str(teacher_graph_id).strip()
    teacher_replay_id = str(teacher_replay_id).strip()
    if not teacher_graph_id or not teacher_replay_id:
        raise ContractError("teacher graph and replay IDs must be non-empty")
    teacher_graph_sha256 = _require_sha256(
        teacher_graph_sha256, "teacher_graph_sha256"
    )
    teacher_replay_sha256 = _require_sha256(
        teacher_replay_sha256, "teacher_replay_sha256"
    )
    candidate_trace_sha256 = _require_sha256(
        candidate_trace_sha256, "candidate_trace_sha256"
    )
    candidate_trace_manifest_sha256 = _require_sha256(
        candidate_trace_manifest_sha256, "candidate_trace_manifest_sha256"
    )
    teacher_system_identity_sha256 = _require_sha256(
        teacher_system_identity_sha256, "teacher_system_identity_sha256"
    )
    if not isinstance(split_protocol, Mapping):
        raise ContractError("split_protocol must be a JSON object")
    split_mode = str(split_protocol.get("mode", "")).strip()
    if split_mode not in {
        "fixed_memory_query_generalization",
        "inductive_evidence_holdout",
    }:
        raise ContractError("split_protocol.mode is invalid")
    rows = validate_unique_trace_ids(traces)
    if purpose == "training":
        rows = assert_training_trace_boundary(rows)
    elif purpose not in {"development", "external_evaluation", "audit"}:
        raise ContractError(f"unknown teacher-trace bundle purpose: {purpose}")
    expected_splits = {
        "development": {"development"},
        "external_evaluation": {"external_evaluation"},
    }
    if purpose in expected_splits:
        invalid = [
            trace.trace_id
            for trace in rows
            if trace.split.value not in expected_splits[purpose]
        ]
        if invalid:
            raise ContractError(
                f"{purpose} bundle contains traces from another split: {', '.join(invalid)}"
            )
    for trace in rows:
        if trace.teacher_graph_id != teacher_graph_id:
            raise ContractError(f"trace {trace.trace_id} uses a different teacher graph")
        if trace.teacher_replay_id != teacher_replay_id:
            raise ContractError(f"trace {trace.trace_id} uses a different teacher replay")
    ordered = tuple(sorted(rows, key=lambda row: row.trace_id))
    payload = canonical_jsonl_bytes(row.to_dict() for row in ordered)
    split_counts = Counter(row.split.value for row in ordered)
    route_counts = Counter(row.route.action.value for row in ordered)
    manifest = {
        "artifact_type": "rp3_teacher_trace_bundle",
        "contract_version": CONTRACT_VERSION,
        "dataset_id": str(dataset_id),
        "purpose": purpose,
        "teacher_graph": {
            "id": str(teacher_graph_id),
            "sha256": str(teacher_graph_sha256),
        },
        "teacher_replay_id": str(teacher_replay_id),
        "teacher_replay_sha256": str(teacher_replay_sha256),
        "candidate_trace": {
            "data_sha256": candidate_trace_sha256,
            "manifest_sha256": candidate_trace_manifest_sha256,
        },
        "teacher_system_identity_sha256": teacher_system_identity_sha256,
        "split_protocol": _plain(split_protocol),
        "validation": _plain(validation_report or {}),
        "trace_count": len(ordered),
        "split_counts": dict(sorted(split_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "human_expert_reviewed": False,
        "supervision_boundary": "teacher_generated_not_expert_ground_truth",
        "data_file": TRACE_FILENAME,
        "data_sha256": hashlib.sha256(payload).hexdigest(),
        "logical_sha256": stable_sha256([row.to_dict() for row in ordered]),
    }
    output = Path(output_dir)
    _write_immutable(output / TRACE_FILENAME, payload)
    _write_immutable(output / MANIFEST_FILENAME, canonical_json_bytes(manifest))
    return manifest


def read_teacher_trace_bundle(
    output_dir: str | Path, *, purpose: str | None = None
) -> tuple[tuple[TeacherTrace, ...], dict[str, Any]]:
    output = Path(output_dir)
    manifest = json.loads((output / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    if manifest.get("artifact_type") != "rp3_teacher_trace_bundle":
        raise ContractError("manifest is not an RP3 teacher-trace bundle")
    if purpose is not None and manifest.get("purpose") != purpose:
        raise ContractError(
            f"teacher-trace bundle purpose={manifest.get('purpose')!r}, expected {purpose!r}"
        )
    _require_sha256(
        manifest.get("candidate_trace", {}).get("data_sha256", ""),
        "candidate_trace.data_sha256",
    )
    _require_sha256(
        manifest.get("candidate_trace", {}).get("manifest_sha256", ""),
        "candidate_trace.manifest_sha256",
    )
    _require_sha256(
        manifest.get("teacher_system_identity_sha256", ""),
        "teacher_system_identity_sha256",
    )
    split_protocol = manifest.get("split_protocol")
    if not isinstance(split_protocol, Mapping) or split_protocol.get("mode") not in {
        "fixed_memory_query_generalization",
        "inductive_evidence_holdout",
    }:
        raise ContractError("teacher-trace bundle has an invalid split_protocol")
    data_path = _bundle_data_path(output, manifest.get("data_file"), TRACE_FILENAME)
    if file_sha256(data_path) != manifest.get("data_sha256"):
        raise ContractError("teacher-trace artifact SHA-256 mismatch")
    rows = tuple(TeacherTrace.from_dict(row) for row in _read_jsonl(data_path))
    validate_unique_trace_ids(rows)
    if len(rows) != int(manifest.get("trace_count", -1)):
        raise ContractError("teacher-trace count disagrees with manifest")
    if stable_sha256([row.to_dict() for row in rows]) != manifest.get("logical_sha256"):
        raise ContractError("teacher-trace logical hash mismatch")
    if manifest.get("purpose") == "training":
        assert_training_trace_boundary(rows)
    elif manifest.get("purpose") in {"development", "external_evaluation"}:
        expected = manifest["purpose"]
        if any(row.split.value != expected for row in rows):
            raise ContractError(f"{expected} bundle contains traces from another split")
    declared_validation = manifest.get("validation", {})
    if not isinstance(declared_validation, Mapping):
        raise ContractError("teacher-trace validation report must be a JSON object")
    if manifest.get("purpose") == "training":
        required_flags = {
            "exactly_40_original_base_queries",
            "complete_four_slot_cards",
            "cited_selected_pointer_closure",
            "exact_original_trace_count",
            "unique_original_query_ids",
            "candidate_width_bounded_32",
            "four_slot_card_schema",
            "route_card_closure",
            "explicit_three_action_costs",
            "known_fault_single_role_supervision",
        }
        if set(declared_validation) != required_flags or any(
            declared_validation.get(flag) is not True for flag in required_flags
        ):
            raise ContractError(
                "training TeacherTrace bundle lacks required true closure validations"
            )
    return rows, manifest


def validate_trace_memory_references(
    traces: Iterable[TeacherTrace], records: Iterable[CompactEvidenceRecord]
) -> None:
    """Verify that every observed pointer resolves within the same governed split."""

    trace_rows = validate_unique_trace_ids(traces)
    memory_rows = validate_compact_memory(records)
    memory_by_id = {record.evidence_id: record for record in memory_rows}
    for trace in trace_rows:
        missing = sorted(set(trace.candidate_evidence_ids) - set(memory_by_id))
        if missing:
            raise ContractError(
                f"trace {trace.trace_id} references missing evidence: {', '.join(missing)}"
            )
        allowed = {
            "train": {"train", "validation"},
            "validation": {"train", "validation"},
            "development": {"development"},
            "external_evaluation": {"external_evaluation"},
        }.get(trace.split.value)
        if allowed is None:
            raise ContractError(f"trace {trace.trace_id} has not been assigned a data split")
        incompatible = sorted(
            evidence_id
            for evidence_id in trace.candidate_evidence_ids
            if memory_by_id[evidence_id].partition.value not in allowed
        )
        if incompatible:
            raise ContractError(
                f"trace {trace.trace_id} crosses an evidence-memory split: "
                + ", ".join(incompatible)
            )
        decision_by_id = {
            decision.evidence_id: decision for decision in trace.evidence_decisions
        }
        selected = {
            evidence_id
            for evidence_id, decision in decision_by_id.items()
            if decision.selected
        }
        for slot in trace.diagnosis_card.slots:
            for item in slot.items:
                for evidence_id in item.evidence_ids:
                    record = memory_by_id[evidence_id]
                    decision = decision_by_id[evidence_id]
                    if evidence_id not in selected or decision.support.value != "direct":
                        raise ContractError(
                            f"trace {trace.trace_id} card cites non-direct or unselected "
                            f"evidence {evidence_id}"
                        )
                    if record.role != slot.role:
                        raise ContractError(
                            f"trace {trace.trace_id} card slot/evidence role mismatch for "
                            f"{evidence_id}"
                        )
                    if trace.query.fault_id not in record.fault_class_ids:
                        raise ContractError(
                            f"trace {trace.trace_id} card evidence is outside fault scope: "
                            f"{evidence_id}"
                        )
                    if record.claim_id not in trace.claim_group_ids:
                        raise ContractError(
                            f"trace {trace.trace_id} omits cited claim group {record.claim_id}"
                        )
        for conflict in trace.diagnosis_card.conflicts:
            for evidence_id in conflict.evidence_ids:
                decision = decision_by_id[evidence_id]
                if not dict(zip(trace.candidate_evidence_ids, trace.availability_mask)).get(
                    evidence_id, False
                ):
                    raise ContractError(
                        f"trace {trace.trace_id} conflict cites unavailable evidence {evidence_id}"
                    )
                if decision.support.value not in {"direct", "indirect"}:
                    raise ContractError(
                        f"trace {trace.trace_id} conflict cites unsupported evidence {evidence_id}"
                    )


def write_compact_evidence_memory_bundle(
    output_dir: str | Path,
    records: Iterable[CompactEvidenceRecord],
    *,
    memory_id: str,
    teacher_graph_id: str,
    teacher_graph_sha256: str,
    teacher_system_identity_sha256: str,
    purpose: str = "training",
) -> dict[str, Any]:
    teacher_graph_id = str(teacher_graph_id).strip()
    if not teacher_graph_id:
        raise ContractError("teacher_graph_id must be non-empty")
    teacher_graph_sha256 = _require_sha256(
        teacher_graph_sha256, "teacher_graph_sha256"
    )
    teacher_system_identity_sha256 = _require_sha256(
        teacher_system_identity_sha256, "teacher_system_identity_sha256"
    )
    rows = validate_compact_memory(records)
    rows = assert_memory_partition_boundary(rows, purpose=purpose)
    ordered = tuple(sorted(rows, key=lambda row: row.memory_index))
    payload = canonical_jsonl_bytes(row.to_dict() for row in ordered)
    dimensions = {len(row.feature_vector) for row in ordered if row.feature_vector}
    feature_dimension = next(iter(dimensions)) if dimensions else 0
    manifest = {
        "artifact_type": "rp3_compact_evidence_memory",
        "contract_version": CONTRACT_VERSION,
        "memory_id": str(memory_id),
        "purpose": purpose,
        "teacher_graph": {
            "id": str(teacher_graph_id),
            "sha256": str(teacher_graph_sha256),
        },
        "teacher_system_identity_sha256": teacher_system_identity_sha256,
        "record_count": len(ordered),
        "feature_dimension": feature_dimension,
        "partition_counts": dict(
            sorted(Counter(row.partition.value for row in ordered).items())
        ),
        "access_semantics": "bounded_id_addressed_evidence_memory",
        "retrieval_free_claim_allowed": False,
        "human_expert_reviewed": False,
        "data_file": MEMORY_FILENAME,
        "data_sha256": hashlib.sha256(payload).hexdigest(),
        "logical_sha256": stable_sha256([row.to_dict() for row in ordered]),
    }
    output = Path(output_dir)
    _write_immutable(output / MEMORY_FILENAME, payload)
    _write_immutable(output / MANIFEST_FILENAME, canonical_json_bytes(manifest))
    return manifest


def read_compact_evidence_memory_bundle(
    output_dir: str | Path, *, purpose: str
) -> tuple[tuple[CompactEvidenceRecord, ...], dict[str, Any]]:
    output = Path(output_dir)
    manifest = json.loads((output / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    if manifest.get("artifact_type") != "rp3_compact_evidence_memory":
        raise ContractError("manifest is not an RP3 compact evidence memory")
    if manifest.get("purpose") != purpose:
        raise ContractError(
            f"evidence-memory purpose={manifest.get('purpose')!r}, expected {purpose!r}"
        )
    _require_sha256(
        manifest.get("teacher_system_identity_sha256", ""),
        "teacher_system_identity_sha256",
    )
    data_path = _bundle_data_path(output, manifest.get("data_file"), MEMORY_FILENAME)
    if file_sha256(data_path) != manifest.get("data_sha256"):
        raise ContractError("compact evidence-memory SHA-256 mismatch")
    rows = tuple(CompactEvidenceRecord.from_dict(row) for row in _read_jsonl(data_path))
    validate_compact_memory(rows)
    assert_memory_partition_boundary(rows, purpose=purpose)
    if len(rows) != int(manifest.get("record_count", -1)):
        raise ContractError("compact evidence-memory count disagrees with manifest")
    if stable_sha256([row.to_dict() for row in rows]) != manifest.get("logical_sha256"):
        raise ContractError("compact evidence-memory logical hash mismatch")
    return rows, manifest
