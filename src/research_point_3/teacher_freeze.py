"""Fail-closed freezing of the RP3 teacher and distillation-trace dependencies.

This module never rebuilds an embedding index and never calls a language model.  It
only verifies that the exact strict-208 graph, vector index, models, and replay
artifacts form a reproducible teacher system.  It separately verifies that a full
top-32 baseline trace export is ready for distillation.  Missing dependencies are
reported as blockers, not silently ignored.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .artifacts import canonical_json_bytes, file_sha256, normalized_text_sha256
from .contracts import ContractError


TEACHER_FREEZE_SCHEMA = "rp3_teacher_graph_freeze_v1"
TEACHER_FREEZE_ID = "TeacherGraph_RP3_v1.freeze_v1"
CANONICAL_TEACHER_GRAPH_ID = "TeacherGraph_RP3_v1"
CANONICAL_TEACHER_METHOD = "Ours_v6_k3_equal"
CANONICAL_BASE_PERTURBATION_ID = "original"
CANONICAL_GRAPH_ROOT = "data/kg/marine_pump/triples/KG_v1_validated"
CANONICAL_VECTOR_INDEX_DIR = (
    "data/kg/marine_pump/vector_indexes/bge_m3_KG_v1_validated"
)
CANONICAL_RP2_REPLAY_PATH = (
    "results/experiments/research_point_2/graphrag_v6_equal_budget/"
    "retrieval_replay.jsonl"
)
CANONICAL_RP2_REPLAY_MANIFEST_PATH = (
    "results/experiments/research_point_2/graphrag_v6_equal_budget/"
    "retrieval_replay_manifest.json"
)
CANONICAL_RP2_CONFIG_PATH = "configs/rp2_graphrag_v6_equal_budget.json"
CANONICAL_RP2_PAPER_FREEZE_PATH = "configs/frozen/rp2_v6_paper_evidence_freeze.json"
CANONICAL_TOP32_TRACE_PATH = (
    "results/experiments/research_point_3/teacher_traces/strict208_base_top32/"
    "teacher_candidate_traces.jsonl"
)
CANONICAL_TOP32_TRACE_MANIFEST_PATH = (
    "results/experiments/research_point_3/teacher_traces/strict208_base_top32/"
    "manifest.json"
)
CANONICAL_REQUIRED_MODEL_PATHS = (
    "data/model/BAAI-bge-m3",
    "data/model/Qwen2.5-7B-Instruct",
)
RP2_PAPER_FREEZE_ID = "marine_pump_rp2_v6_paper_evidence_freeze_v1"
RP2_PAPER_FREEZE_STATUS = "frozen_for_short_paper_drafting"
# Exact-byte and LF-normalized digests are equal for the repository's anchored file.
RP2_PAPER_FREEZE_RAW_SHA256 = (
    "b23bc485468ea284ba21642cc719f53660fed8b3e928f74e5182636e45ab2887"
)
RP2_PAPER_FREEZE_NORMALIZED_SHA256 = RP2_PAPER_FREEZE_RAW_SHA256
CANONICAL_GRAPH_FILES = (
    ("evidence_assertions", "evidence_assertions.jsonl"),
    ("claims", "claims.jsonl"),
    ("entities", "entities.jsonl"),
    ("claim_evidence_links", "claim_evidence_links.jsonl"),
    ("source_records", "source_records.jsonl"),
)
DEFAULT_GRAPH_COUNTS = {
    "evidence_assertions": 208,
    "claims": 203,
    "entities": 281,
    "claim_evidence_links": 208,
    "source_records": 208,
}


def _require_exact_config_value(
    config: Mapping[str, Any], key: str, expected: Any
) -> None:
    if config.get(key) != expected:
        raise ContractError(f"{key} is immutable and must equal {expected!r}")


def _nested_value(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _immutable_graph_logical_sha256(
    graph_artifacts: Iterable[Mapping[str, Any]], counts: Mapping[str, int]
) -> str:
    """Hash the five canonical graph paths, exact bytes, and immutable counts."""

    by_path = {str(item.get("path")): item for item in graph_artifacts}
    rows: list[dict[str, Any]] = []
    for count_name, filename in CANONICAL_GRAPH_FILES:
        path = f"{CANONICAL_GRAPH_ROOT}/{filename}"
        item = by_path.get(path, {})
        rows.append(
            {
                "path": path,
                "raw_sha256": str(item.get("raw_sha256", "")).lower(),
                "count_name": count_name,
                "count": int(counts[count_name]),
            }
        )
    return hashlib.sha256(canonical_json_bytes(rows, newline=False)).hexdigest()


def freeze_manifest_logical_sha256(manifest: Mapping[str, Any]) -> str:
    payload = {
        key: value
        for key, value in manifest.items()
        if key != "freeze_manifest_logical_sha256"
    }
    return hashlib.sha256(canonical_json_bytes(payload, newline=False)).hexdigest()


@dataclass(frozen=True)
class FreezeCheck:
    name: str
    ok: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


@dataclass(frozen=True)
class TeacherFreezeAudit:
    teacher_graph_id: str
    teacher_system_ready: bool
    distillation_trace_ready: bool
    final_training_bundle_ready: bool
    ready: bool
    checks: tuple[FreezeCheck, ...]
    manifest: dict[str, Any]

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(check.detail for check in self.checks if not check.ok)

    @property
    def teacher_system_blockers(self) -> tuple[str, ...]:
        return tuple(
            check.detail
            for check in self.checks
            if check.name.startswith("teacher_system:") and not check.ok
        )

    @property
    def distillation_trace_blockers(self) -> tuple[str, ...]:
        return tuple(
            check.detail
            for check in self.checks
            if check.name.startswith("distillation_trace:") and not check.ok
        )

    @property
    def final_training_bundle_blockers(self) -> tuple[str, ...]:
        return tuple(
            check.detail
            for check in self.checks
            if check.name.startswith("final_training_bundle:") and not check.ok
        )

    def require_ready(self) -> dict[str, Any]:
        if not self.ready:
            raise ContractError(
                "TeacherGraph_RP3_v1 is not ready: " + "; ".join(self.blockers)
            )
        return self.manifest


def _project_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    path = path if path.is_absolute() else root / path
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ContractError(f"teacher artifact escapes repository root: {path}") from exc
    return resolved_path


def _jsonl_count(path: Path) -> int:
    count = 0
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
            count += 1
    return count


def _artifact(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        # These freeze inputs are governed JSON/JSONL/config text.  Preserve the
        # historical cross-platform digest as ``sha256`` and also record exact
        # bytes, so old RP2 manifests remain comparable without weakening binary
        # artifact hashing elsewhere.
        "sha256": normalized_text_sha256(path),
        "raw_sha256": file_sha256(path),
    }


def _directory_inventory(path: Path, root: Path) -> dict[str, Any]:
    """Bind every file in an index/model directory by exact-byte SHA-256."""

    files = []
    total_bytes = 0
    if path.is_dir():
        for item in sorted(
            (candidate for candidate in path.rglob("*") if candidate.is_file()),
            key=lambda candidate: candidate.relative_to(path).as_posix(),
        ):
            size = item.stat().st_size
            total_bytes += size
            files.append(
                {
                    "path": item.relative_to(path).as_posix(),
                    "bytes": size,
                    "sha256": file_sha256(item),
                }
            )
    summary = {
        "root": path.relative_to(root.resolve()).as_posix(),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "files": files,
    }
    summary["logical_sha256"] = hashlib.sha256(
        canonical_json_bytes(summary, newline=False)
    ).hexdigest()
    return summary


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {path}")
    return value


def _read_jsonl_objects(path: Path) -> tuple[dict[str, Any], ...]:
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
    return tuple(rows)


def _normalized_declared_sha256(path: Path) -> str:
    """Use the same LF-normalized text hash policy as the frozen RP2 assets."""

    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _append_replay_content_checks(
    checks: list[FreezeCheck],
    replay_path: Path,
    replay_manifest_path: Path,
    required_replay: Mapping[str, Any],
) -> None:
    """Validate replay identity and content instead of checking existence only."""

    expected_identity = {
        "total_record_count": 200,
        "query_count": 40,
        "method_count": 5,
        "teacher_method": CANONICAL_TEACHER_METHOD,
        "require_exact_replay_identity": True,
    }
    if "require_exact_rank_match" in required_replay:
        raise ContractError(
            "required_replay.require_exact_rank_match is forbidden: the freeze gate "
            "does not replay source ranking computations; use the accurately named "
            "require_exact_replay_identity=true contract"
        )
    if dict(required_replay) != expected_identity:
        raise ContractError(f"required_replay is immutable and must equal {expected_identity}")
    if not replay_path.is_file() or not replay_manifest_path.is_file():
        return
    manifest = _read_json_object(replay_manifest_path)
    expected_total = expected_identity["total_record_count"]
    expected_queries = expected_identity["query_count"]
    expected_method_count = expected_identity["method_count"]
    expected_teacher_method = expected_identity["teacher_method"]
    actual_total = _jsonl_count(replay_path)
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_replay_record_count",
            actual_total == expected_total,
            f"RP2 replay records: actual={actual_total}, expected={expected_total}",
        )
    )
    replay_artifact = manifest.get("replay_artifact", {})
    if not isinstance(replay_artifact, Mapping):
        replay_artifact = {}
    declared_hash = str(replay_artifact.get("sha256", "")).lower()
    actual_hash = _normalized_declared_sha256(replay_path)
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_replay_hash",
            len(declared_hash) == 64 and declared_hash == actual_hash,
            f"RP2 replay hash declared={declared_hash or 'missing'}, actual={actual_hash}",
        )
    )
    validation = manifest.get("validation", {})
    if not isinstance(validation, Mapping):
        validation = {}
    manifest_ok = (
        int(validation.get("records", -1)) == expected_total
        and int(validation.get("methods", -1)) == expected_method_count
        and int(validation.get("queries_per_method", -1)) == expected_queries
        and validation.get("identical_query_id_sets") is True
        and validation.get("source_method_mapping_valid") is True
        and validation.get("candidate_budget_upper_bounds_valid") is True
    )
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_replay_manifest_validation",
            manifest_ok,
            "RP2 replay manifest must validate record/method/query counts, query sets, mappings, and budgets",
        )
    )
    mappings = manifest.get("method_mappings", ())
    if not isinstance(mappings, list):
        mappings = ()
    teacher_mapping = [
        row
        for row in mappings
        if isinstance(row, Mapping) and row.get("id") == expected_teacher_method
    ]
    teacher_ok = (
        len(teacher_mapping) == 1
        and int(teacher_mapping[0].get("query_count", -1)) == expected_queries
        and int(teacher_mapping[0].get("candidate_budget", -1)) == 3
    )
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_teacher_method_identity",
            teacher_ok,
            f"teacher method={expected_teacher_method}, queries={expected_queries}, budget=3",
        )
    )


def _append_rp2_config_checks(
    checks: list[FreezeCheck], rp2_config_path: Path
) -> None:
    if not rp2_config_path.is_file():
        return
    try:
        value = _read_json_object(rp2_config_path)
    except ContractError as exc:
        checks.append(FreezeCheck("teacher_system:rp2_config_content", False, str(exc)))
        return
    required = {
        ("protocol_id",): "marine_pump_rp2_graphrag_v6_equal_budget",
        ("graph_root",): CANONICAL_GRAPH_ROOT,
        ("frozen_retrieval_results",): CANONICAL_RP2_REPLAY_PATH,
        ("frozen_retrieval_manifest",): CANONICAL_RP2_REPLAY_MANIFEST_PATH,
        ("embedding", "model_path"): CANONICAL_REQUIRED_MODEL_PATHS[0],
        ("embedding", "index_dir"): CANONICAL_VECTOR_INDEX_DIR,
        ("embedding", "normalize_embeddings"): True,
        ("generator", "model_path"): CANONICAL_REQUIRED_MODEL_PATHS[1],
        ("retrieval", "dense_top_n"): 32,
        ("retrieval", "max_scored_candidates"): 32,
        ("retrieval", "ours_graph_hops"): 1,
        ("generation_contract", "max_answer_points"): 3,
        ("cascade", "decision_policy"): "single_run",
        ("replay_preparation", "expected_query_count"): 40,
        ("primary_comparison", "evidence_budget"): 3,
        ("anti_leakage", "frozen_retrieval_reused_without_reranking"): True,
    }
    mismatches = [
        ".".join(keys)
        for keys, expected in required.items()
        if _nested_value(value, *keys) != expected
    ]
    scenarios = value.get("scenarios")
    teacher_rows = [
        row
        for row in scenarios if isinstance(row, Mapping)
        and row.get("id") == CANONICAL_TEACHER_METHOD
    ] if isinstance(scenarios, list) else []
    teacher_scenario_ok = (
        len(teacher_rows) == 1
        and teacher_rows[0].get("retrieval_method") == "dense_ours_v4"
        and teacher_rows[0].get("max_selected_evidence") == 3
        and teacher_rows[0].get("components") == {
            "role_filter": True,
            "graph_expansion": True,
            "fault_affinity": True,
            "source_family_novelty": True,
            "source_family_cap_active_at_k3": False,
        }
    )
    method_mappings = _nested_value(value, "replay_preparation", "method_mappings")
    teacher_mappings = [
        row
        for row in method_mappings
        if isinstance(row, Mapping)
        and row.get("id") == CANONICAL_TEACHER_METHOD
    ] if isinstance(method_mappings, list) else []
    teacher_mapping_ok = (
        len(teacher_mappings) == 1
        and teacher_mappings[0].get("source_method") == "Ours_v4_k3"
        and teacher_mappings[0].get("retrieval_method") == "dense_ours_v4"
        and teacher_mappings[0].get("candidate_budget") == 3
    )
    primary_methods = _nested_value(value, "primary_comparison", "methods")
    primary_ok = (
        isinstance(primary_methods, list)
        and CANONICAL_TEACHER_METHOD in primary_methods
    )
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_config_content",
            not mismatches and teacher_scenario_ok and teacher_mapping_ok and primary_ok,
            "RP2 config immutable path/model/index/method bindings; mismatches="
            + (", ".join(mismatches) if mismatches else "none")
            + f", teacher_scenario_ok={teacher_scenario_ok}"
            + f", teacher_mapping_ok={teacher_mapping_ok}, primary_ok={primary_ok}",
        )
    )


def _append_paper_freeze_checks(
    checks: list[FreezeCheck], *, project_root: Path, freeze_path: Path
) -> None:
    if not freeze_path.is_file():
        return
    raw = file_sha256(freeze_path)
    normalized = normalized_text_sha256(freeze_path)
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_paper_freeze_anchor",
            raw == RP2_PAPER_FREEZE_RAW_SHA256
            and normalized == RP2_PAPER_FREEZE_NORMALIZED_SHA256,
            f"trusted RP2 paper freeze anchor raw={raw}, normalized={normalized}",
        )
    )
    paper_freeze = _read_json_object(freeze_path)
    identity_ok = (
        paper_freeze.get("freeze_id") == RP2_PAPER_FREEZE_ID
        and paper_freeze.get("status") == RP2_PAPER_FREEZE_STATUS
        and paper_freeze.get("human_expert_reviewed") is False
    )
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_paper_freeze_identity",
            identity_ok,
            "RP2 paper freeze must preserve its immutable freeze_id/status/review boundary",
        )
    )
    artifacts = paper_freeze.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        checks.append(
            FreezeCheck(
                "teacher_system:rp2_paper_freeze_artifacts",
                False,
                "RP2 paper freeze has no artifact inventory",
            )
        )
        return
    declared: dict[str, str] = {}
    malformed = False
    for row in artifacts:
        if not isinstance(row, Mapping):
            malformed = True
            continue
        path = str(row.get("path", ""))
        digest = str(row.get("sha256", "")).lower()
        if not path or path in declared or len(digest) != 64:
            malformed = True
            continue
        declared[path] = digest
    required_paths = {CANONICAL_RP2_CONFIG_PATH, CANONICAL_RP2_REPLAY_MANIFEST_PATH}
    all_bound = not malformed and required_paths.issubset(declared)
    mismatched: list[str] = []
    for relative, digest in declared.items():
        try:
            path = _project_path(project_root, relative)
        except ContractError:
            mismatched.append(relative)
            continue
        # The RP2 freeze stores exact bytes for several CRLF JSON reports and
        # normalized hashes for replay text. Do not misclassify its own files.
        if not path.is_file() or digest not in {file_sha256(path), normalized_text_sha256(path)}:
            mismatched.append(relative)
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_paper_freeze_artifacts",
            all_bound and not mismatched,
            f"paper freeze artifacts={len(declared)}, mismatched={mismatched}",
        )
    )


def _teacher_method(row: Mapping[str, Any]) -> str:
    return str(
        row.get("teacher_method")
        or row.get("source_teacher_method")
        or row.get("method")
        or row.get("source_method")
        or ""
    ).strip()


def _candidate_evidence_ids(row: Mapping[str, Any]) -> tuple[str, ...]:
    candidates = row.get("candidates", row.get("ranked"))
    if not isinstance(candidates, list):
        return ()
    return tuple(
        str(item.get("evidence_id", "")).strip() if isinstance(item, Mapping) else ""
        for item in candidates
    )


def _complete_candidate_decision_row(
    row: Mapping[str, Any], candidate_ids: tuple[str, ...], *, maximum_selected: int
) -> bool:
    """Reject ID-only exports that omit ranking/support/availability decisions."""

    candidates = row.get("candidates", row.get("ranked"))
    if not isinstance(candidates, list) or len(candidates) != len(candidate_ids):
        return False
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            return False
        if type(candidate.get("available")) is not bool:
            return False
        try:
            score = float(candidate["score"])
        except (KeyError, TypeError, ValueError):
            return False
        if not math.isfinite(score):
            return False
    support = row.get("final_support_by_evidence_id")
    selected = row.get("selected_evidence_ids")
    reasons = row.get("underfill_reason_codes")
    if not isinstance(support, Mapping) or not isinstance(selected, list):
        return False
    if not isinstance(reasons, list) or any(not str(value).strip() for value in reasons):
        return False
    support_keys = {str(value).strip() for value in support}
    selected_ids = tuple(str(value).strip() for value in selected)
    if (
        not support_keys.issubset(candidate_ids)
        or not all(selected_ids)
        or len(selected_ids) != len(set(selected_ids))
        or not set(selected_ids).issubset(candidate_ids)
        or len(selected_ids) > maximum_selected
    ):
        return False
    allowed_support = (1, 0, True, False, "1", "0", "direct", "irrelevant", "indirect")
    if any(value not in allowed_support for value in support.values()):
        return False
    available_by_id = {
        evidence_id: bool(candidate["available"])
        for evidence_id, candidate in zip(candidate_ids, candidates)
    }
    if any(not available_by_id[evidence_id] for evidence_id in selected_ids):
        return False
    if any(support.get(evidence_id) not in {1, True, "1", "direct"} for evidence_id in selected_ids):
        return False
    return (len(selected_ids) < maximum_selected and bool(reasons)) or (
        len(selected_ids) == maximum_selected and not reasons
    )


def _append_teacher_trace_checks(
    checks: list[FreezeCheck],
    *,
    project_root: Path,
    trace_path: Path,
    trace_manifest_path: Path,
    required_trace: Mapping[str, Any],
    strict_evidence_ids: set[str],
    strict_evidence_sha256: str,
    replay_path: Path,
) -> None:
    """Validate a complete baseline candidate export for rank distillation.

    This is intentionally stronger than the archived RP2 top-three replay gate.
    The trace data and its manifest are both content-validated; manifest booleans
    alone cannot make the gate pass.
    """

    prefix = "distillation_trace:"
    data_exists = trace_path.is_file()
    manifest_exists = trace_manifest_path.is_file()
    checks.append(
        FreezeCheck(
            prefix + "data_exists",
            data_exists,
            f"full teacher trace data {'present' if data_exists else 'missing'}: {trace_path}",
        )
    )
    checks.append(
        FreezeCheck(
            prefix + "manifest_exists",
            manifest_exists,
            "full teacher trace manifest "
            f"{'present' if manifest_exists else 'missing'}: {trace_manifest_path}",
        )
    )
    if not data_exists or not manifest_exists:
        return

    expected_queries = int(required_trace.get("base_query_count", 40))
    expected_width = int(required_trace.get("candidates_per_query", 32))
    width_policy = str(required_trace.get("candidate_count_policy", "exact"))
    expected_method = str(
        required_trace.get("teacher_method", "Ours_v6_k3_equal")
    ).strip()
    base_perturbation_id = str(
        required_trace.get("base_perturbation_id", "original")
    ).strip()
    expected_strict_count = int(required_trace.get("strict_evidence_count", 208))
    maximum_selected = int(required_trace.get("maximum_selected", 3))
    require_complete_top32 = required_trace.get("require_complete_top32", True)
    if expected_queries < 1 or expected_width < 1 or maximum_selected < 1:
        raise ContractError("required_teacher_trace counts must be positive")
    if expected_queries != 40 or expected_strict_count != 208 or maximum_selected != 3:
        raise ContractError(
            "main RP3 teacher trace identity is immutable: 40 base queries, "
            "strict 208 evidence records, maximum selection budget 3"
        )
    if width_policy not in {"exact", "at_most"}:
        raise ContractError(
            "required_teacher_trace.candidate_count_policy must be exact or at_most"
        )
    if not expected_method:
        raise ContractError("required_teacher_trace.teacher_method cannot be empty")
    if require_complete_top32 is not True:
        raise ContractError(
            "required_teacher_trace.require_complete_top32 must be true for rank distillation"
        )
    if expected_width != 32:
        raise ContractError(
            "full top-32 rank distillation requires candidates_per_query=32 and "
            "candidate_count_policy=exact"
        )

    try:
        rows = _read_jsonl_objects(trace_path)
        manifest = _read_json_object(trace_manifest_path)
    except ContractError as exc:
        checks.append(FreezeCheck(prefix + "parse", False, str(exc)))
        return

    query_ids = tuple(str(row.get("query_id", "")).strip() for row in rows)
    candidate_lists = tuple(_candidate_evidence_ids(row) for row in rows)
    methods = tuple(_teacher_method(row) for row in rows)
    perturbations = tuple(str(row.get("perturbation_id", "")).strip() for row in rows)
    if width_policy == "exact":
        width_ok = all(len(candidates) == expected_width for candidates in candidate_lists)
    else:
        width_ok = all(len(candidates) <= expected_width for candidates in candidate_lists)
    candidate_ids_valid = all(
        all(candidates)
        and len(candidates) == len(set(candidates))
        for candidates in candidate_lists
    )
    complete_decisions = all(
        _complete_candidate_decision_row(
            row, candidate_ids, maximum_selected=maximum_selected
        )
        for row, candidate_ids in zip(rows, candidate_lists)
    )
    observed_ids = {evidence_id for candidates in candidate_lists for evidence_id in candidates}
    strict_closure_ok = (
        len(strict_evidence_ids) == expected_strict_count
        and bool(observed_ids)
        and observed_ids.issubset(strict_evidence_ids)
    )
    base_query_ok = (
        len(rows) == expected_queries
        and all(query_ids)
        and len(set(query_ids)) == expected_queries
        and all(value == base_perturbation_id for value in perturbations)
    )
    checks.extend(
        (
            FreezeCheck(
                prefix + "base_queries",
                base_query_ok,
                f"baseline traces: actual={len(rows)}, expected={expected_queries}; "
                f"unique_query_ids={len(set(query_ids))}",
            ),
            FreezeCheck(
                prefix + "teacher_method",
                bool(rows) and all(value == expected_method for value in methods),
                f"every baseline trace must use teacher method {expected_method}",
            ),
            FreezeCheck(
                prefix + "candidate_width",
                width_ok,
                f"candidate width policy={width_policy}, bound={expected_width}",
            ),
            FreezeCheck(
                prefix + "candidate_ids",
                candidate_ids_valid,
                "candidate evidence IDs must be non-empty and unique within each query",
            ),
            FreezeCheck(
                prefix + "complete_decisions",
                complete_decisions,
                "every candidate row must retain finite rank scores, explicit availability, "
                "support decisions, selected pointers, and consistent underfill reasons",
            ),
            FreezeCheck(
                prefix + "strict208_id_closure",
                strict_closure_ok,
                "all trace candidate IDs must belong to the strict graph; "
                f"strict_ids={len(strict_evidence_ids)}, observed_ids={len(observed_ids)}, "
                f"outside={len(observed_ids - strict_evidence_ids)}",
            ),
        )
    )

    replay_query_ids: set[str] = set()
    if replay_path.is_file():
        try:
            replay_query_ids = {
                str(row.get("query_id", "")).strip()
                for row in _read_jsonl_objects(replay_path)
                if _teacher_method(row) == expected_method
                and str(row.get("query_id", "")).strip()
            }
        except ContractError:
            replay_query_ids = set()
    if required_trace.get("require_fresh_execution_audit") is True:
        fresh_path=trace_path.parent/"fresh_retrieval_audit.json"
        fresh_ok=False
        if fresh_path.is_file():
            try:
                fresh=_read_json_object(fresh_path)
                expected_order={
                    str(item["query_id"]):[str(x["evidence_id"]) for x in item["ranked"]]
                    for item in _read_jsonl_objects(replay_path)
                    if _teacher_method(item)==expected_method
                }
                observed={str(item["query_id"]):item["selected_ids"] for item in fresh["queries"]}
                fresh_ok=(fresh.get("schema")=="rp3_fresh_retrieval_audit_v1"
                    and fresh.get("smoke_only") is False and fresh.get("query_count")==40
                    and len(fresh["queries"])==40 and observed==expected_order
                    and fresh.get("all_rankings_match") is True
                    and manifest.get("fresh_retrieval_audit_sha256")==normalized_text_sha256(fresh_path))
            except (ContractError,KeyError,TypeError):
                fresh_ok=False
        checks.append(FreezeCheck(prefix+"fresh_execution_audit",fresh_ok,
            "fresh 40-query K3 order and execution-report hash must match frozen RP2 replay"))
    checks.append(
        FreezeCheck(
            prefix + "query_set_matches_replay",
            len(replay_query_ids) == expected_queries and set(query_ids) == replay_query_ids,
            "top-32 baseline query IDs must exactly match the frozen teacher-method replay; "
            f"trace={len(set(query_ids))}, replay={len(replay_query_ids)}",
        )
    )

    declared_data = manifest.get("data_artifact", {})
    if not isinstance(declared_data, Mapping):
        declared_data = {}
    declared_path = str(declared_data.get("path", ""))
    declared_sha256 = str(declared_data.get("sha256", "")).lower()
    actual_relative_path = trace_path.relative_to(project_root).as_posix()
    actual_sha256 = _normalized_declared_sha256(trace_path)
    checks.append(
        FreezeCheck(
            prefix + "data_hash",
            declared_path == actual_relative_path
            and len(declared_sha256) == 64
            and declared_sha256 == actual_sha256,
            f"trace data binding path={declared_path or 'missing'}, "
            f"sha256={declared_sha256 or 'missing'}, actual={actual_sha256}",
        )
    )
    declared_logical_hash = str(manifest.get("logical_sha256", "")).lower()
    unhashed_manifest = {
        key: value for key, value in manifest.items() if key != "logical_sha256"
    }
    actual_logical_hash = hashlib.sha256(
        canonical_json_bytes(unhashed_manifest, newline=False)
    ).hexdigest()
    checks.append(
        FreezeCheck(
            prefix + "manifest_hash",
            len(declared_logical_hash) == 64
            and declared_logical_hash == actual_logical_hash,
            "teacher trace manifest logical hash "
            f"declared={declared_logical_hash or 'missing'}, actual={actual_logical_hash}",
        )
    )

    teacher_graph = manifest.get("teacher_graph", {})
    if not isinstance(teacher_graph, Mapping):
        teacher_graph = {}
    manifest_identity_ok = (
        manifest.get("schema") == "rp3_teacher_candidate_trace_manifest_v1"
        and manifest.get("trace_schema") == "rp3_teacher_candidate_trace_v1"
        and teacher_graph.get("id") == "TeacherGraph_RP3_v1"
        and teacher_graph.get("terminology_tier") == "strict_208"
        and int(teacher_graph.get("evidence_count", -1)) == expected_strict_count
        and teacher_graph.get("evidence_assertions_sha256") == strict_evidence_sha256
        and manifest.get("teacher_method") == expected_method
        and manifest.get("rp2_replay_sha256")
        == (_normalized_declared_sha256(replay_path) if replay_path.is_file() else "")
        and int(manifest.get("base_query_count", -1)) == expected_queries
        and int(manifest.get("candidates_per_query", -1)) == expected_width
        and manifest.get("candidate_count_policy") == width_policy
        and int(manifest.get("maximum_selected", -1)) == maximum_selected
    )
    checks.append(
        FreezeCheck(
            prefix + "manifest_identity",
            manifest_identity_ok,
            "trace manifest must bind schema, strict-208 evidence hash, RP2 replay hash, "
            "teacher method, base-query count, and candidate-width policy",
        )
    )
    validation = manifest.get("validation", {})
    if not isinstance(validation, Mapping):
        validation = {}
    required_flags = tuple(
        str(value)
        for value in required_trace.get(
            "required_validation_flags",
            (
                "unique_base_query_ids",
                "base_queries_only",
                "teacher_method_consistent",
                "candidate_width_valid",
                "candidate_ids_unique_within_query",
                "complete_teacher_decisions",
                "strict_evidence_id_closure",
                "query_set_matches_replay",
            ),
        )
    )
    checks.append(
        FreezeCheck(
            prefix + "manifest_validation",
            bool(required_flags) and all(validation.get(flag) is True for flag in required_flags),
            "trace manifest validation flags required true: " + ", ".join(required_flags),
        )
    )


def _append_final_training_bundle_checks(
    checks: list[FreezeCheck],
    *,
    project_root: Path,
    required_bundle: Mapping[str, Any],
    immutable_graph_sha256: str,
    teacher_system_identity_sha256: str,
) -> tuple[dict[str, Any], ...]:
    """Bind the final 40-row four-field card/route training bundles."""

    expected = {
        "trace_dir": (
            "data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/traces/training"
        ),
        "memory_dir": (
            "data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/evidence_memory/training"
        ),
        "trace_count": 40,
        "base_perturbation_id": CANONICAL_BASE_PERTURBATION_ID,
        "required_card_roles": [
            "symptom",
            "cause_or_mechanism",
            "inspection",
            "maintenance",
        ],
        "require_route_closure": True,
    }
    if dict(required_bundle) != expected:
        raise ContractError(
            "required_training_bundle is immutable and must equal the canonical "
            "40-row four-field training-bundle contract"
        )
    trace_dir = _project_path(project_root, expected["trace_dir"])
    memory_dir = _project_path(project_root, expected["memory_dir"])
    trace_manifest_path = trace_dir / "manifest.json"
    trace_data_path = trace_dir / "teacher_traces.jsonl"
    memory_manifest_path = memory_dir / "manifest.json"
    memory_data_path = memory_dir / "evidence_memory.jsonl"
    paths = (
        trace_manifest_path,
        trace_data_path,
        memory_manifest_path,
        memory_data_path,
    )
    for path in paths:
        checks.append(
            FreezeCheck(
                "final_training_bundle:exists:" + path.name,
                path.is_file(),
                f"final training artifact {'present' if path.is_file() else 'missing'}: {path}",
            )
        )
    if not all(path.is_file() for path in paths):
        return ()
    try:
        trace_manifest = _read_json_object(trace_manifest_path)
        memory_manifest = _read_json_object(memory_manifest_path)
        trace_rows = _read_jsonl_objects(trace_data_path)
    except ContractError as exc:
        checks.append(FreezeCheck("final_training_bundle:parse", False, str(exc)))
        return ()

    def _binding_ok(manifest: Mapping[str, Any]) -> bool:
        graph = manifest.get("teacher_graph")
        return (
            isinstance(graph, Mapping)
            and graph.get("id") == CANONICAL_TEACHER_GRAPH_ID
            and graph.get("sha256") == immutable_graph_sha256
            and manifest.get("teacher_system_identity_sha256")
            == teacher_system_identity_sha256
        )

    manifests_ok = (
        trace_manifest.get("artifact_type") == "rp3_teacher_trace_bundle"
        and memory_manifest.get("artifact_type") == "rp3_compact_evidence_memory"
        and trace_manifest.get("purpose") == "training"
        and memory_manifest.get("purpose") == "training"
        and int(trace_manifest.get("trace_count", -1)) == expected["trace_count"]
        and int(memory_manifest.get("record_count", -1))
        == DEFAULT_GRAPH_COUNTS["source_records"]
        and _binding_ok(trace_manifest)
        and _binding_ok(memory_manifest)
        and trace_manifest.get("data_sha256") == file_sha256(trace_data_path)
        and memory_manifest.get("data_sha256") == file_sha256(memory_data_path)
    )
    checks.append(
        FreezeCheck(
            "final_training_bundle:manifest_bindings",
            manifests_ok,
            "trace/memory manifests must bind graph identity, teacher-system identity, "
            "purpose, and exact data content",
        )
    )
    expected_roles = tuple(expected["required_card_roles"])
    rows_ok = len(trace_rows) == expected["trace_count"]
    validation = trace_manifest.get("validation")
    validation_ok = isinstance(validation, Mapping) and all(
        validation.get(flag) is True
        for flag in (
            "exact_original_trace_count",
            "unique_original_query_ids",
            "candidate_width_bounded_32",
            "four_slot_card_schema",
            "route_card_closure",
            "explicit_three_action_costs",
            "known_fault_single_role_supervision",
        )
    )
    closure_ok = rows_ok and validation_ok
    for row in trace_rows:
        card = row.get("diagnosis_card")
        route = row.get("route")
        slots = card.get("slots") if isinstance(card, Mapping) else None
        roles = tuple(
            str(slot.get("role", "")) for slot in slots if isinstance(slot, Mapping)
        ) if isinstance(slots, list) else ()
        action = str(route.get("action", "")) if isinstance(route, Mapping) else ""
        card_status = str(card.get("status", "")) if isinstance(card, Mapping) else ""
        selected = {
            str(item.get("evidence_id", ""))
            for item in row.get("evidence_decisions", ())
            if isinstance(item, Mapping) and item.get("selected") is True
        }
        cited = {
            str(evidence_id)
            for slot in (slots or ()) if isinstance(slot, Mapping)
            for item in slot.get("items", ()) if isinstance(item, Mapping)
            for evidence_id in item.get("evidence_ids", ())
        }
        metadata = row.get("metadata")
        route_costs = (
            metadata.get("route_action_costs", {})
            if isinstance(metadata, Mapping)
            else {}
        )
        closure_ok = closure_ok and (
            row.get("perturbation_id") == expected["base_perturbation_id"]
            and row.get("selection_budget") == 3
            and len(row.get("candidate_evidence_ids", ())) <= 32
            and roles == expected_roles
            and action in {"answer", "fallback", "abstain"}
            and cited.issubset(selected)
            and isinstance(route_costs, Mapping)
            and set(route_costs) == {"answer", "fallback", "abstain"}
            and all(
                type(route_costs[key]) in {int, float}
                and math.isfinite(float(route_costs[key]))
                and float(route_costs[key]) >= 0
                for key in ("answer", "fallback", "abstain")
            )
            and (
                (action == "answer" and card_status in {"answered", "partial"})
                or (
                    action in {"fallback", "abstain"}
                    and card_status == "insufficient_evidence"
                    and not cited
                )
            )
        )
    checks.append(
        FreezeCheck(
            "final_training_bundle:row_closure",
            closure_ok,
            "training bundle must contain exactly 40 original rows with ordered four-slot "
            "cards, budget=3, valid routes, and cited-selected pointer closure",
        )
    )
    return tuple(_artifact(path, project_root) for path in paths)


def audit_teacher_freeze(
    root: str | Path,
    config: Mapping[str, Any],
) -> TeacherFreezeAudit:
    """Audit all freeze prerequisites without mutating any artifact."""

    project_root = Path(root).resolve()
    _require_exact_config_value(
        config, "schema", "rp3_teacher_graph_freeze_config_v1"
    )
    _require_exact_config_value(config, "teacher_graph_id", CANONICAL_TEACHER_GRAPH_ID)
    _require_exact_config_value(config, "terminology_tier", "strict_208")
    _require_exact_config_value(config, "graph_root", CANONICAL_GRAPH_ROOT)
    _require_exact_config_value(config, "vector_index_dir", CANONICAL_VECTOR_INDEX_DIR)
    _require_exact_config_value(config, "rp2_replay_path", CANONICAL_RP2_REPLAY_PATH)
    _require_exact_config_value(
        config, "rp2_replay_manifest_path", CANONICAL_RP2_REPLAY_MANIFEST_PATH
    )
    _require_exact_config_value(config, "rp2_config_path", CANONICAL_RP2_CONFIG_PATH)
    _require_exact_config_value(
        config, "rp2_paper_freeze_path", CANONICAL_RP2_PAPER_FREEZE_PATH
    )
    _require_exact_config_value(
        config, "required_model_paths", list(CANONICAL_REQUIRED_MODEL_PATHS)
    )
    if config.get("human_expert_reviewed") is not False:
        raise ContractError("human_expert_reviewed must be the boolean false")
    teacher_graph_id = CANONICAL_TEACHER_GRAPH_ID

    graph_root = _project_path(project_root, config.get("graph_root", ""))
    index_dir = _project_path(project_root, config.get("vector_index_dir", ""))
    replay_path = _project_path(project_root, config.get("rp2_replay_path", ""))
    replay_manifest_path = _project_path(
        project_root, config.get("rp2_replay_manifest_path", "")
    )
    rp2_config_path = _project_path(project_root, config.get("rp2_config_path", ""))
    rp2_paper_freeze_path = _project_path(
        project_root, config.get("rp2_paper_freeze_path", "")
    )
    required_models = tuple(
        _project_path(project_root, value) for value in config.get("required_model_paths", ())
    )
    declared_counts = {
        str(key): int(value) for key, value in config.get("expected_counts", {}).items()
    }
    if declared_counts and declared_counts != DEFAULT_GRAPH_COUNTS:
        raise ContractError(
            "TeacherGraph_RP3_v1 counts are immutable and must equal strict "
            f"{DEFAULT_GRAPH_COUNTS}"
        )
    expected_counts = dict(DEFAULT_GRAPH_COUNTS)
    required_replay = config.get("required_replay", {})
    if not isinstance(required_replay, Mapping):
        raise ContractError("required_replay must be a JSON object")
    required_teacher_trace = config.get("required_teacher_trace")
    if not isinstance(required_teacher_trace, Mapping):
        raise ContractError(
            "required_teacher_trace must be a JSON object; a replay-only teacher "
            "cannot be declared ready for distillation"
        )
    required_training_bundle = config.get("required_training_bundle")
    if not isinstance(required_training_bundle, Mapping):
        raise ContractError("required_training_bundle must be a JSON object")
    trace_path_value = required_teacher_trace.get("data_path")
    trace_manifest_value = required_teacher_trace.get("manifest_path")
    if not isinstance(trace_path_value, str) or not trace_path_value.strip():
        raise ContractError("required_teacher_trace.data_path must be a non-empty path")
    if not isinstance(trace_manifest_value, str) or not trace_manifest_value.strip():
        raise ContractError("required_teacher_trace.manifest_path must be a non-empty path")
    trace_identity = {
        "data_path": CANONICAL_TOP32_TRACE_PATH,
        "manifest_path": CANONICAL_TOP32_TRACE_MANIFEST_PATH,
        "base_query_count": 40,
        "base_perturbation_id": CANONICAL_BASE_PERTURBATION_ID,
        "candidates_per_query": 32,
        "candidate_count_policy": required_teacher_trace.get("candidate_count_policy"),
        "require_complete_top32": True,
        "maximum_selected": 3,
        "teacher_method": CANONICAL_TEACHER_METHOD,
        "strict_evidence_count": 208,
    }
    mismatched_trace_identity = [
        key
        for key, expected in trace_identity.items()
        if required_teacher_trace.get(key) != expected
    ]
    if mismatched_trace_identity:
        raise ContractError(
            "required_teacher_trace immutable identity mismatch: "
            + ", ".join(mismatched_trace_identity)
        )
    trace_path = _project_path(project_root, trace_path_value)
    trace_manifest_path = _project_path(project_root, trace_manifest_value)

    checks: list[FreezeCheck] = []
    graph_artifacts: list[dict[str, Any]] = []
    file_by_count = dict(CANONICAL_GRAPH_FILES)
    checks.append(
        FreezeCheck("teacher_system:graph_root", graph_root.is_dir(), str(graph_root))
    )
    strict_evidence_ids: set[str] = set()
    strict_evidence_sha256 = ""
    if graph_root.is_dir():
        for count_name, filename in file_by_count.items():
            path = graph_root / filename
            if not path.is_file():
                checks.append(
                    FreezeCheck(
                        f"teacher_system:graph_file:{filename}", False, f"missing {path}"
                    )
                )
                continue
            actual = _jsonl_count(path)
            expected = expected_counts[count_name]
            checks.append(
                FreezeCheck(
                    f"teacher_system:graph_count:{count_name}",
                    actual == expected,
                    f"{count_name}: actual={actual}, expected={expected}",
                )
            )
            graph_artifacts.append(_artifact(path, project_root))
            if count_name == "evidence_assertions":
                strict_evidence_sha256 = _normalized_declared_sha256(path)
                rows = _read_jsonl_objects(path)
                evidence_ids = tuple(
                    str(row.get("evidence_id", "")).strip() for row in rows
                )
                ids_ok = (
                    len(evidence_ids) == expected_counts["evidence_assertions"]
                    and all(evidence_ids)
                    and len(set(evidence_ids)) == len(evidence_ids)
                )
                checks.append(
                    FreezeCheck(
                        "teacher_system:strict_evidence_ids",
                        ids_ok,
                        "strict graph evidence IDs must be non-empty and unique; "
                        f"rows={len(evidence_ids)}, unique={len(set(evidence_ids))}",
                    )
                )
                if ids_ok:
                    strict_evidence_ids = set(evidence_ids)

    checks.append(
        FreezeCheck(
            "teacher_system:vector_index",
            index_dir.is_dir() and any(path.is_file() for path in index_dir.rglob("*")),
            f"vector index {'present' if index_dir.is_dir() else 'missing'}: {index_dir}",
        )
    )
    _append_replay_content_checks(
        checks, replay_path, replay_manifest_path, required_replay
    )
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_config",
            rp2_config_path.is_file(),
            f"RP2 config: {rp2_config_path}",
        )
    )
    _append_rp2_config_checks(checks, rp2_config_path)
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_paper_freeze",
            rp2_paper_freeze_path.is_file(),
            f"RP2 paper freeze: {rp2_paper_freeze_path}",
        )
    )
    _append_paper_freeze_checks(
        checks, project_root=project_root, freeze_path=rp2_paper_freeze_path
    )
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_replay",
            replay_path.is_file(),
            f"RP2 replay: {replay_path}",
        )
    )
    checks.append(
        FreezeCheck(
            "teacher_system:rp2_replay_manifest",
            replay_manifest_path.is_file(),
            f"RP2 replay manifest: {replay_manifest_path}",
        )
    )
    for model_path in required_models:
        checks.append(
            FreezeCheck(
                f"teacher_system:model:{model_path.name}",
                model_path.is_dir() and any(path.is_file() for path in model_path.rglob("*")),
                f"required model {'present' if model_path.is_dir() else 'missing'}: {model_path}",
            )
        )

    index_inventory = _directory_inventory(index_dir, project_root)
    model_inventories = [
        _directory_inventory(path, project_root) for path in required_models
    ]

    # A reproducible teacher system and a distillation-ready trace export are
    # deliberately distinct gates.  ``ready`` below requires both.
    teacher_system_checks = tuple(
        check for check in checks if check.name.startswith("teacher_system:")
    )
    teacher_system_ready = bool(teacher_system_checks) and all(
        check.ok for check in teacher_system_checks
    )
    _append_teacher_trace_checks(
        checks,
        project_root=project_root,
        trace_path=trace_path,
        trace_manifest_path=trace_manifest_path,
        required_trace=required_teacher_trace,
        strict_evidence_ids=strict_evidence_ids,
        strict_evidence_sha256=strict_evidence_sha256,
        replay_path=replay_path,
    )
    distillation_checks = tuple(
        check for check in checks if check.name.startswith("distillation_trace:")
    )
    distillation_trace_ready = bool(distillation_checks) and all(
        check.ok for check in distillation_checks
    )

    replay_artifacts = [
        _artifact(path, project_root)
        for path in (
            replay_path,
            replay_manifest_path,
            rp2_config_path,
            rp2_paper_freeze_path,
        )
        if path.is_file()
    ]
    trace_artifacts = [
        _artifact(path, project_root)
        for path in (trace_path, trace_manifest_path)
        if path.is_file()
    ]
    immutable_graph_hash = _immutable_graph_logical_sha256(
        graph_artifacts, expected_counts
    )
    teacher_system_identity = {
        "teacher_graph_id": teacher_graph_id,
        "terminology_tier": "strict_208",
        "immutable_graph_logical_sha256": immutable_graph_hash,
        "vector_index_logical_sha256": index_inventory["logical_sha256"],
        "model_inventory_logical_sha256": [
            item["logical_sha256"] for item in model_inventories
        ],
        "replay_artifacts": [
            {
                "path": item["path"],
                "raw_sha256": item["raw_sha256"],
                "sha256": item["sha256"],
            }
            for item in replay_artifacts
        ],
        "teacher_trace_artifacts": [
            {
                "path": item["path"],
                "raw_sha256": item["raw_sha256"],
                "sha256": item["sha256"],
            }
            for item in trace_artifacts
        ],
        "rp2_config_parameters": {
            "dense_top_n": 32,
            "max_scored_candidates": 32,
            "graph_hops": 1,
            "maximum_selected": 3,
            "decision_policy": "single_run",
        },
        "teacher_method": CANONICAL_TEACHER_METHOD,
        "base_perturbation_id": CANONICAL_BASE_PERTURBATION_ID,
        "candidate_width": 32,
        "selection_budget": 3,
    }
    teacher_system_identity_sha256 = hashlib.sha256(
        canonical_json_bytes(teacher_system_identity, newline=False)
    ).hexdigest()
    final_training_bundle_artifacts = _append_final_training_bundle_checks(
        checks,
        project_root=project_root,
        required_bundle=required_training_bundle,
        immutable_graph_sha256=immutable_graph_hash,
        teacher_system_identity_sha256=teacher_system_identity_sha256,
    )
    final_training_checks = tuple(
        check for check in checks if check.name.startswith("final_training_bundle:")
    )
    final_training_bundle_ready = bool(final_training_checks) and all(
        check.ok for check in final_training_checks
    )
    ready = (
        teacher_system_ready
        and distillation_trace_ready
        and final_training_bundle_ready
    )
    manifest = {
        "schema": TEACHER_FREEZE_SCHEMA,
        "freeze_id": TEACHER_FREEZE_ID,
        "teacher_graph_id": teacher_graph_id,
        "status": (
            "ready_to_freeze"
            if ready
            else (
                "ready_to_export_training_bundle"
                if teacher_system_ready and distillation_trace_ready
                else "blocked"
            )
        ),
        "teacher_system_status": "ready_to_freeze" if teacher_system_ready else "blocked",
        "distillation_trace_status": (
            "ready" if distillation_trace_ready else "blocked"
        ),
        "final_training_bundle_status": (
            "ready" if final_training_bundle_ready else "blocked"
        ),
        "terminology_tier": "strict_208",
        "counts": expected_counts,
        "immutable_graph_logical_sha256": immutable_graph_hash,
        "teacher_system_identity": teacher_system_identity,
        "teacher_system_identity_sha256": teacher_system_identity_sha256,
        "graph_artifacts": graph_artifacts,
        "vector_index": {
            "path": index_dir.relative_to(project_root).as_posix(),
            "present": index_dir.is_dir(),
            "inventory": index_inventory,
        },
        "replay_artifacts": replay_artifacts,
        "teacher_trace_artifacts": trace_artifacts,
        "final_training_bundle_artifacts": list(final_training_bundle_artifacts),
        "required_model_paths": [
            path.relative_to(project_root).as_posix() for path in required_models
        ],
        "model_inventories": model_inventories,
        "human_expert_reviewed": False,
        "claim_boundary": (
            "Freezing binds an automatically evidence-qualified teacher system; "
            "it does not establish expert factual or diagnostic correctness."
        ),
        "checks": [check.to_dict() for check in checks],
    }
    manifest["freeze_manifest_logical_sha256"] = freeze_manifest_logical_sha256(
        manifest
    )
    return TeacherFreezeAudit(
        teacher_graph_id=teacher_graph_id,
        teacher_system_ready=teacher_system_ready,
        distillation_trace_ready=distillation_trace_ready,
        final_training_bundle_ready=final_training_bundle_ready,
        ready=ready,
        checks=tuple(checks),
        manifest=manifest,
    )


def freeze_teacher_manifest(
    output_path: str | Path,
    audit: TeacherFreezeAudit,
) -> dict[str, Any]:
    """Write an immutable distillation-ready freeze only after both gates pass."""

    ready_manifest = audit.require_ready()
    manifest = dict(ready_manifest)
    manifest["status"] = "frozen"
    manifest.pop("freeze_manifest_logical_sha256", None)
    manifest["freeze_manifest_logical_sha256"] = freeze_manifest_logical_sha256(
        manifest
    )
    path = Path(output_path)
    payload = canonical_json_bytes(manifest)
    if path.exists():
        existing = path.read_bytes().replace(b"\r\n", b"\n")
        if existing != payload:
            raise RuntimeError(f"refusing to overwrite non-identical teacher freeze: {path}")
        return manifest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return manifest
