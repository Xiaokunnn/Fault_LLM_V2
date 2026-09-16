#!/usr/bin/env python3
"""Build an RP3 ID-addressed evidence memory without running an encoder."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.research_point_3.artifacts import stable_sha256, write_compact_evidence_memory_bundle
from src.research_point_3.contracts import ContractError
from src.research_point_3.evidence_memory import compile_evidence_memory
from src.research_point_3.teacher_freeze import (
    CANONICAL_GRAPH_ROOT,
    DEFAULT_GRAPH_COUNTS,
    TEACHER_FREEZE_ID,
    TEACHER_FREEZE_SCHEMA,
)


ROOT = Path(__file__).resolve().parents[1]


def _resolve_in_repo(value: str) -> Path:
    path = Path(value)
    resolved = (path if path.is_absolute() else ROOT / path).resolve()
    resolved.relative_to(ROOT.resolve())
    return resolved


def _validated_freeze(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != TEACHER_FREEZE_SCHEMA:
        raise ContractError("teacher freeze schema mismatch")
    if value.get("freeze_id") != TEACHER_FREEZE_ID:
        raise ContractError("teacher freeze ID mismatch")
    if value.get("status") != "frozen":
        raise ContractError("teacher freeze manifest is not ready")
    expected_hash = str(
        value.get("freeze_manifest_logical_sha256", "")
    ).lower()
    actual_hash = stable_sha256(
        {
            key: item
            for key, item in value.items()
            if key != "freeze_manifest_logical_sha256"
        }
    )
    if expected_hash != actual_hash:
        raise ContractError("teacher freeze logical hash mismatch")
    if value.get("counts") != DEFAULT_GRAPH_COUNTS:
        raise ContractError("teacher freeze is not the immutable strict-208 identity")
    for name in (
        "immutable_graph_logical_sha256",
        "teacher_system_identity_sha256",
    ):
        digest = str(value.get(name, "")).lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ContractError(f"teacher freeze has no valid {name}")
    checks = value.get("checks")
    if not isinstance(checks, list) or not checks or any(
        not isinstance(item, dict) or item.get("ok") is not True for item in checks
    ):
        raise ContractError("teacher freeze contains a failed or malformed check")
    return value


def _verify_graph_root(graph_root: Path, freeze: dict) -> None:
    expected = {
        str(item.get("path")): str(item.get("raw_sha256", "")).lower()
        for item in freeze.get("graph_artifacts", ())
        if isinstance(item, dict)
    }
    required_names = {
        "evidence_assertions.jsonl",
        "claims.jsonl",
        "entities.jsonl",
        "claim_evidence_links.jsonl",
        "source_records.jsonl",
    }
    actual_paths = {name: graph_root / name for name in required_names}
    from src.research_point_3.artifacts import file_sha256

    for name, path in actual_paths.items():
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
        if not path.is_file() or expected.get(relative) != file_sha256(path):
            raise ContractError(f"graph root disagrees with frozen artifact: {name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--teacher-freeze",
        default="configs/frozen/teacher_graph_rp3_v1.freeze.json",
    )
    parser.add_argument(
        "--graph-root",
        default="data/kg/marine_pump/triples/KG_v1_validated",
    )
    parser.add_argument(
        "--output-dir",
        default="data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/evidence_memory",
    )
    parser.add_argument(
        "--split-map",
        help=(
            "JSON object mapping every evidence_id to train/validation. Required "
            "for a training bundle and generated only after grouped trace splitting."
        ),
    )
    parser.add_argument(
        "--purpose",
        choices=("audit", "training"),
        default="audit",
    )
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    freeze_path = _resolve_in_repo(args.teacher_freeze)
    if not freeze_path.is_file():
        print(
            "BLOCKED: TeacherGraph_RP3_v1 freeze manifest is missing. "
            "Run freeze_rp3_teacher_graph.py after rebuilding the model index."
        )
        return 2
    try:
        freeze = _validated_freeze(freeze_path)
        graph_root = _resolve_in_repo(args.graph_root)
        if graph_root != (ROOT / CANONICAL_GRAPH_ROOT).resolve():
            raise ContractError(
                f"--graph-root is immutable and must equal {CANONICAL_GRAPH_ROOT}"
            )
        _verify_graph_root(graph_root, freeze)
    except (ContractError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    split_map = None
    if args.split_map:
        split_map = json.loads((ROOT / args.split_map).read_text(encoding="utf-8"))
        if not isinstance(split_map, dict):
            print("BLOCKED: --split-map must be a JSON object.")
            return 2
    if args.purpose == "training" and split_map is None:
        print(
            "BLOCKED: a training evidence memory requires --split-map from the "
            "grouped trace split; defaulting every record to training would leak groups."
        )
        return 2
    records, report = compile_evidence_memory(
        graph_root, split_by_evidence_id=split_map
    )
    print(json.dumps(report.__dict__, ensure_ascii=False, indent=2))
    if args.validate_only:
        return 0
    write_compact_evidence_memory_bundle(
        ROOT / args.output_dir,
        records,
        memory_id="RP3_EvidenceMemory_strict208_v1",
        teacher_graph_id="TeacherGraph_RP3_v1",
        teacher_graph_sha256=str(freeze["immutable_graph_logical_sha256"]),
        teacher_system_identity_sha256=str(
            freeze["teacher_system_identity_sha256"]
        ),
        purpose=args.purpose,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
