#!/usr/bin/env python3
"""Compile full top-32 teacher decisions into the frozen RP3 training bundles.

This command is intentionally offline with respect to models.  It consumes the
candidate trace produced on a model-capable machine, audits its teacher-system
identity, compiles the strict-208 local memory, creates one four-slot (single-role
supervision) TeacherTrace per RP2 query, assigns leakage-safe query splits, and
writes immutable trace/memory bundles.  The final teacher freeze is a subsequent
step because it binds the hashes written here.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.research_point_3.artifacts import (
    file_sha256,
    normalized_text_sha256,
    write_compact_evidence_memory_bundle,
    write_teacher_trace_bundle,
)
from src.research_point_3.contracts import (
    ContractError,
    DataSplit,
    QueryContext,
)
from src.research_point_3.evidence_memory import apply_memory_splits, compile_evidence_memory
from src.research_point_3.splits import assign_fixed_memory_query_splits
from src.research_point_3.teacher_freeze import audit_teacher_freeze
from src.research_point_3.trace_export import (
    TEACHER_TRACE_BUNDLE_SOURCE_SCHEMA,
    assemble_single_role_teacher_trace,
    export_candidate_decisions,
    route_from_teacher_row,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEACHER_ID = "TeacherGraph_RP3_v1"
DEFAULT_REPLAY_ID = "RP2_v6_replay_on_TeacherGraph_RP3_v1"


def _resolve_in_repo(value: str) -> Path:
    path = Path(value)
    resolved = (path if path.is_absolute() else ROOT / path).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ContractError(f"artifact escapes repository root: {value}") from exc
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {path}")
    return value


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
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


def _hex_digest(value: Any, name: str) -> str:
    digest = str(value or "").strip().lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ContractError(f"{name} must be a 64-character SHA-256")
    return digest


def _candidate_data_hash(manifest: Mapping[str, Any], path: Path) -> str:
    declared = manifest.get("data_artifact", {})
    if not isinstance(declared, Mapping):
        raise ContractError("candidate manifest has no data_artifact object")
    expected = _hex_digest(declared.get("sha256"), "candidate data SHA-256")
    actual = normalized_text_sha256(path)
    if expected != actual:
        raise ContractError("candidate trace data disagrees with its manifest")
    return actual


def _candidate_manifest_hash(manifest: Mapping[str, Any], path: Path) -> str:
    # Bind the immutable on-disk manifest, not only its self-declared logical
    # hash.  This makes later additions or policy-field changes observable.
    logical = _hex_digest(manifest.get("logical_sha256"), "candidate logical SHA-256")
    if not logical:
        raise ContractError("candidate manifest logical hash is missing")
    return normalized_text_sha256(path)


def _query_map(path: Path) -> dict[str, QueryContext]:
    rows = _read_jsonl(path)
    result: dict[str, QueryContext] = {}
    for row in rows:
        query = QueryContext.from_dict(
            {
                **row,
                "scenario_id": row.get("scenario_id")
                or f"fault:{row.get('fault_id', '')}",
            }
        )
        if query.query_id in result:
            raise ContractError(f"duplicate query metadata: {query.query_id}")
        result[query.query_id] = query
    return result


def _validation_report(traces: tuple, *, expected_count: int) -> dict[str, Any]:
    original = tuple(trace for trace in traces if trace.perturbation_id == "original")
    route_fact_free = all(
        trace.route.action.value == "answer"
        or (
            not trace.diagnosis_card.cited_evidence_ids
            and not trace.diagnosis_card.conflicts
            and not any(slot.items for slot in trace.diagnosis_card.slots)
        )
        for trace in original
    )
    four_slot_schema = all(len(trace.diagnosis_card.slots) == 4 for trace in original)
    route_costs_complete = all(
        isinstance(trace.metadata.get("route_action_costs"), Mapping)
        and set(trace.metadata["route_action_costs"]) == {"answer", "fallback", "abstain"}
        for trace in original
    )
    return {
        "exactly_40_original_base_queries": len(original) == expected_count
        and len({trace.query.query_id for trace in original}) == expected_count,
        "complete_four_slot_cards": four_slot_schema,
        "cited_selected_pointer_closure": all(
            set(trace.diagnosis_card.cited_evidence_ids).issubset(
                set(trace.selected_evidence_ids)
            )
            for trace in original
        ),
        "exact_original_trace_count": len(original) == expected_count,
        "unique_original_query_ids": len({trace.query.query_id for trace in original})
        == expected_count,
        "candidate_width_bounded_32": all(
            len(trace.candidate_evidence_ids) <= 32 for trace in original
        ),
        "four_slot_card_schema": four_slot_schema,
        "route_card_closure": route_fact_free,
        "explicit_three_action_costs": route_costs_complete,
        "known_fault_single_role_supervision": all(
            trace.query.requested_role.value != "full_card" for trace in original
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--freeze-config",
        default="configs/research_point_3/teacher_graph_rp3_v1.json",
    )
    parser.add_argument(
        "--query-metadata",
        default="data/kg/marine_pump/silver_evidencebench/rp2_full_graph_development_v2/queries.jsonl",
        help="Historical path retained for reproducibility; rows are automatic benchmark metadata.",
    )
    parser.add_argument(
        "--output-traces",
        default="data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/traces/training",
    )
    parser.add_argument(
        "--output-memory",
        default="data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/evidence_memory/training",
    )
    parser.add_argument("--split-seed", default="rp3-fixed-memory-query-v1")
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = _read_json(_resolve_in_repo(args.freeze_config))
        audit = audit_teacher_freeze(
            ROOT,
            config,
            progress=lambda message: print(f"[RP3 inventory] {message}", flush=True),
        )
        if not audit.teacher_system_ready or not audit.distillation_trace_ready:
            blockers = (*audit.teacher_system_blockers, *audit.distillation_trace_blockers)
            raise ContractError("teacher/candidate gate is blocked: " + "; ".join(blockers))
        graph_hash = _hex_digest(
            audit.manifest.get("immutable_graph_logical_sha256"),
            "immutable_graph_logical_sha256",
        )
        system_hash = _hex_digest(
            audit.manifest.get("teacher_system_identity_sha256"),
            "teacher_system_identity_sha256",
        )
        required = config["required_teacher_trace"]
        candidate_path = _resolve_in_repo(required["data_path"])
        candidate_manifest_path = _resolve_in_repo(required["manifest_path"])
        candidate_manifest = _read_json(candidate_manifest_path)
        candidate_hash = _candidate_data_hash(candidate_manifest, candidate_path)
        candidate_manifest_hash = _candidate_manifest_hash(
            candidate_manifest, candidate_manifest_path
        )
        replay_path = _resolve_in_repo(config["rp2_replay_path"])
        replay_hash = normalized_text_sha256(replay_path)
        graph_root = _resolve_in_repo(config["graph_root"])
        records, memory_report = compile_evidence_memory(graph_root)
        records_by_id = {record.evidence_id: record for record in records}
        queries = _query_map(_resolve_in_repo(args.query_metadata))
        candidate_rows = _read_jsonl(candidate_path)
        expected_count = int(required.get("base_query_count", 40))
        if len(candidate_rows) != expected_count or set(queries) != {
            str(row.get("query_id", "")) for row in candidate_rows
        }:
            raise ContractError(
                "candidate rows and query metadata must expose the same 40-query identity"
            )
        traces = []
        for row in candidate_rows:
            query_id = str(row.get("query_id", ""))
            candidate = export_candidate_decisions(
                row,
                require_complete_top_n=32,
                maximum_selected=3,
                required_teacher_method=str(required["teacher_method"]),
                allowed_evidence_ids=records_by_id,
                candidate_count_policy=str(required["candidate_count_policy"]),
            )
            route, route_costs = route_from_teacher_row(
                row,
                default_student_cost=1.0,
                default_teacher_cost=8.0,
                default_abstention_cost=2.0,
            )
            traces.append(
                assemble_single_role_teacher_trace(
                    trace_id=f"RP3-{query_id}-original",
                    query=queries[query_id],
                    candidate_trace=candidate,
                    records_by_id=records_by_id,
                    route=route,
                    route_action_costs=route_costs,
                    split=DataSplit.UNASSIGNED,
                    teacher_graph_id=DEFAULT_TEACHER_ID,
                    teacher_replay_id=DEFAULT_REPLAY_ID,
                    metadata={
                        "source_schema": TEACHER_TRACE_BUNDLE_SOURCE_SCHEMA,
                        "route_supervision_status": row.get("route_supervision_status", "explicit"),
                        "candidate_trace_data_sha256": candidate_hash,
                        "candidate_trace_manifest_sha256": candidate_manifest_hash,
                    },
                )
            )
        split_traces, split_report = assign_fixed_memory_query_splits(
            traces,
            seed=args.split_seed,
            validation_fraction=args.validation_fraction,
        )
        if any(trace.split not in {DataSplit.TRAIN, DataSplit.VALIDATION} for trace in split_traces):
            raise ContractError("build-set candidate traces must split only into train/validation")
        # Fixed-memory query generalization keeps the same strict-208 memory in
        # both learning splits.  Candidate IDs are therefore deliberately not
        # used as split components; otherwise top-32 lists collapse into one
        # giant connected component.  A separate corpus-rebuilt protocol is
        # required for a genuine unseen-document/evidence claim.
        split_by_evidence_id = {record.evidence_id: DataSplit.TRAIN for record in records}
        split_records = apply_memory_splits(records, split_by_evidence_id)
        report = _validation_report(split_traces, expected_count=expected_count)
        if not all(value is True for value in report.values()):
            raise ContractError(f"TeacherTrace closure validation failed: {report}")
        split_protocol = {
            "mode": "fixed_memory_query_generalization",
            "seed": args.split_seed,
            "validation_fraction": args.validation_fraction,
            "component_keys": ["fault_scenario"],
            "candidate_evidence_ids_are_split_keys": False,
            "shared_memory_across_train_validation": True,
            "inductive_holdout_claim_allowed": False,
            "inductive_protocol_required": (
                "rebuild the teacher candidate universe and local memory after holding out "
                "documents/source families before retrieval"
            ),
            "split_report": asdict(split_report),
        }
        summary = {
            "memory_report": asdict(memory_report),
            "split_protocol": split_protocol,
            "validation": report,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if args.validate_only:
            return 0
        write_teacher_trace_bundle(
            _resolve_in_repo(args.output_traces),
            split_traces,
            dataset_id="RP3_TeacherTrace_strict208_v1",
            teacher_graph_id=DEFAULT_TEACHER_ID,
            teacher_graph_sha256=graph_hash,
            teacher_replay_id=DEFAULT_REPLAY_ID,
            teacher_replay_sha256=replay_hash,
            candidate_trace_sha256=candidate_hash,
            candidate_trace_manifest_sha256=candidate_manifest_hash,
            teacher_system_identity_sha256=system_hash,
            split_protocol=split_protocol,
            validation_report=report,
            purpose="training",
        )
        write_compact_evidence_memory_bundle(
            _resolve_in_repo(args.output_memory),
            split_records,
            memory_id="RP3_EvidenceMemory_strict208_v1",
            teacher_graph_id=DEFAULT_TEACHER_ID,
            teacher_graph_sha256=graph_hash,
            teacher_system_identity_sha256=system_hash,
            purpose="training",
        )
        return 0
    except (ContractError, KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
