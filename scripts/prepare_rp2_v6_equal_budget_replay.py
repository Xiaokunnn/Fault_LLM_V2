#!/usr/bin/env python3
"""Prepare an immutable, equal-budget RP2 v6 frozen-retrieval replay.

The script only copies already-produced retrieval rows.  It never rebuilds the
graph, embeddings, or dense index.  Source method names are mapped to explicit
v6 scenario IDs so a generation runner cannot silently select the wrong
historical row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _lf_normalized_bytes(content: bytes) -> bytes:
    """Normalize text line endings without changing JSON/JSONL content.

    Git may materialize the same tracked text artifact with LF on Linux and
    CRLF on Windows.  Raw working-tree hashes would therefore make provenance
    and immutable replay checks depend on ``core.autocrlf`` rather than on the
    experiment data.  All RP2 replay inputs are UTF-8 JSON or JSONL, so line
    endings are deliberately excluded from their content identity.
    """

    return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def normalized_file_bytes(path: Path) -> bytes:
    return _lf_normalized_bytes(path.read_bytes())


def sha256_file(path: Path) -> str:
    """Return the cross-platform LF-normalized SHA-256 of a text artifact."""

    return hashlib.sha256(normalized_file_bytes(path)).hexdigest()


def _difference_diagnostic(path: Path, existing: bytes, expected: bytes) -> str:
    existing_normalized = _lf_normalized_bytes(existing)
    expected_normalized = _lf_normalized_bytes(expected)
    details = [
        f"normalized_bytes existing={len(existing_normalized)}, "
        f"expected={len(expected_normalized)}"
    ]
    if path.suffix.lower() == ".jsonl":
        existing_lines = [line for line in existing_normalized.splitlines() if line.strip()]
        expected_lines = [line for line in expected_normalized.splitlines() if line.strip()]
        details.append(
            f"records existing={len(existing_lines)}, expected={len(expected_lines)}"
        )
        for index, (left, right) in enumerate(
            zip(existing_lines, expected_lines), start=1
        ):
            if left == right:
                continue
            try:
                left_row = json.loads(left)
                right_row = json.loads(right)
                details.append(
                    "first_difference="
                    f"record {index}, "
                    f"existing_key=({left_row.get('method')},{left_row.get('query_id')}), "
                    f"expected_key=({right_row.get('method')},{right_row.get('query_id')})"
                )
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                details.append(f"first_difference=record {index}")
            break
    return "; ".join(details)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"JSONL row must be an object at {path}:{line_number}")
            rows.append(row)
    return rows


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )
    return text.encode("utf-8")


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"RP2 v6 artifact must stay inside repository root: {path}") from exc


def _validate_ranked(row: dict[str, Any], *, method_id: str, budget: int) -> int:
    ranked = row.get("ranked")
    if not isinstance(ranked, list):
        raise ValueError(f"{method_id}:{row.get('query_id')} has no ranked list")
    if len(ranked) > budget:
        raise ValueError(
            f"{method_id}:{row.get('query_id')} has {len(ranked)} candidates, budget={budget}"
        )
    if int(row.get("selected_evidence", len(ranked))) != len(ranked):
        raise ValueError(
            f"{method_id}:{row.get('query_id')} selected_evidence disagrees with ranked length"
        )
    evidence_ids = [str(item.get("evidence_id", "")) for item in ranked]
    if not all(evidence_ids) or len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError(f"{method_id}:{row.get('query_id')} has blank/duplicate evidence IDs")
    return len(ranked)


def build_replay(
    root: Path, config: dict[str, Any], config_path: Path
) -> tuple[bytes, dict[str, Any]]:
    preparation = config["replay_preparation"]
    mappings = list(preparation["method_mappings"])
    expected_count = int(preparation.get("expected_query_count", 40))
    if expected_count <= 0:
        raise ValueError("expected_query_count must be positive")

    benchmark_queries = root / config["benchmark_dir"] / "queries.jsonl"
    query_rows = _read_jsonl(benchmark_queries)
    canonical_query_ids = [str(row.get("query_id", "")) for row in query_rows]
    if len(canonical_query_ids) != expected_count:
        raise ValueError(
            f"Benchmark has {len(canonical_query_ids)} queries, expected {expected_count}"
        )
    if not all(canonical_query_ids) or len(canonical_query_ids) != len(set(canonical_query_ids)):
        raise ValueError("Benchmark query IDs must be non-empty and unique")
    canonical_query_set = set(canonical_query_ids)

    source_cache: dict[str, tuple[Path, str, list[dict[str, Any]]]] = {}
    source_manifests: dict[str, dict[str, Any]] = {}
    output_rows: list[dict[str, Any]] = []
    method_manifests: list[dict[str, Any]] = []
    scenario_by_id = {str(row["id"]): row for row in config["scenarios"]}

    mapping_ids = [str(row["id"]) for row in mappings]
    if len(mapping_ids) != len(set(mapping_ids)):
        raise ValueError("replay_preparation method IDs must be unique")
    if set(mapping_ids) != set(scenario_by_id):
        raise ValueError("Replay mappings and scenario IDs must match exactly")

    for mapping in mappings:
        method_id = str(mapping["id"])
        source_path_text = str(mapping["source_file"])
        source_method = str(mapping["source_method"])
        budget = int(mapping["candidate_budget"])
        scenario = scenario_by_id[method_id]
        if str(scenario.get("source_retrieval_method")) != method_id:
            raise ValueError(f"{method_id} scenario must replay its explicit v6 method ID")
        if int(scenario.get("max_selected_evidence", -1)) != budget:
            raise ValueError(f"{method_id} scenario budget disagrees with replay mapping")
        if str(scenario.get("retrieval_method")) != str(mapping["retrieval_method"]):
            raise ValueError(f"{method_id} retrieval method disagrees with replay mapping")

        if source_path_text not in source_cache:
            source_path = root / source_path_text
            if not source_path.is_file():
                raise FileNotFoundError(f"Missing frozen retrieval source: {source_path}")
            digest_before = sha256_file(source_path)
            all_rows = _read_jsonl(source_path)
            digest_after = sha256_file(source_path)
            if digest_before != digest_after:
                raise RuntimeError(f"Frozen retrieval source changed while reading: {source_path}")
            source_cache[source_path_text] = (source_path, digest_after, all_rows)
            source_manifests[source_path_text] = {
                "path": source_path_text,
                "sha256": digest_after,
                "bytes": len(normalized_file_bytes(source_path)),
                "records": len(all_rows),
            }

        _, source_digest, all_rows = source_cache[source_path_text]
        selected = [row for row in all_rows if str(row.get("method")) == source_method]
        by_query: dict[str, dict[str, Any]] = {}
        for row in selected:
            query_id = str(row.get("query_id", ""))
            if not query_id:
                raise ValueError(f"{source_method} contains a blank query ID")
            if query_id in by_query:
                raise ValueError(f"Duplicate source key: {source_method}:{query_id}")
            by_query[query_id] = row
        if len(by_query) != expected_count or set(by_query) != canonical_query_set:
            missing = sorted(canonical_query_set - set(by_query))
            extra = sorted(set(by_query) - canonical_query_set)
            raise ValueError(
                f"{source_method} query set mismatch: rows={len(by_query)}, "
                f"missing={missing}, extra={extra}"
            )

        ranked_counts: Counter[int] = Counter()
        archived_latencies: list[float] = []
        for query_id in canonical_query_ids:
            source_row = dict(by_query[query_id])
            ranked_count = _validate_ranked(source_row, method_id=method_id, budget=budget)
            ranked_counts[ranked_count] += 1
            archived_latencies.append(float(source_row.get("elapsed_ms", 0.0)))
            source_row["method"] = method_id
            source_row["source_method"] = source_method
            source_row["source_file"] = source_path_text
            source_row["replay_provenance"] = {
                "schema": "rp2_v6_frozen_retrieval_replay_v1",
                "source_file_sha256": source_digest,
                "archived_retrieval_latency_only": True,
                "formal_v6_latency_eligible": False,
            }
            output_rows.append(source_row)

        method_manifests.append(
            {
                "id": method_id,
                "display_name": str(mapping["display_name"]),
                "comparison_tier": str(mapping["comparison_tier"]),
                "retrieval_method": str(mapping["retrieval_method"]),
                "source_file": source_path_text,
                "source_file_sha256": source_digest,
                "source_method": source_method,
                "candidate_budget": budget,
                "query_count": len(by_query),
                "ranked_count_distribution": {
                    str(key): ranked_counts[key] for key in sorted(ranked_counts)
                },
                "underfilled_query_count": sum(
                    count for ranked_count, count in ranked_counts.items() if ranked_count < budget
                ),
                "archived_latency_ms_min": min(archived_latencies),
                "archived_latency_ms_max": max(archived_latencies),
            }
        )

    replay_bytes = _jsonl_bytes(output_rows)
    query_set_sha256 = hashlib.sha256("\n".join(canonical_query_ids).encode("utf-8")).hexdigest()
    manifest: dict[str, Any] = {
        "manifest_schema": "rp2_v6_equal_budget_replay_manifest_v2",
        "protocol_id": str(config["protocol_id"]),
        "immutable": True,
        "content_hash_policy": {
            "name": "utf8_text_lf_normalized_sha256_v1",
            "purpose": (
                "Treat Git LF and CRLF materializations as the same JSON/JSONL "
                "experiment content while preserving all parsed values."
            ),
        },
        "label_policy": "Silver only; never Gold",
        "human_expert_reviewed": False,
        "config": {
            "path": _relative(root, config_path),
            "sha256": sha256_file(config_path),
        },
        "benchmark_queries": {
            "path": _relative(root, benchmark_queries),
            "sha256": sha256_file(benchmark_queries),
            "query_count": len(canonical_query_ids),
            "ordered_query_id_set_sha256": query_set_sha256,
        },
        "source_artifacts": [source_manifests[key] for key in sorted(source_manifests)],
        "method_mappings": method_manifests,
        "validation": {
            "methods": len(method_manifests),
            "records": len(output_rows),
            "queries_per_method": expected_count,
            "identical_query_id_sets": True,
            "candidate_budget_upper_bounds_valid": True,
            "source_method_mapping_valid": True,
        },
        "replay_artifact": {
            "path": str(config["frozen_retrieval_results"]),
            "sha256": hashlib.sha256(replay_bytes).hexdigest(),
            "bytes": len(replay_bytes),
            "records": len(output_rows),
        },
        "latency_policy": {
            "archived_elapsed_ms_preserved_for_audit": True,
            "archived_elapsed_ms_formal_v6_eligible": False,
            "warning": (
                "Historical elapsed_ms values were produced under v3/v4 runs and MUST NOT "
                "be added to or reported as formal v6 end-to-end latency. Formal v6 latency "
                "requires a new interleaved replay under the v6 timing protocol."
            ),
        },
    }
    return replay_bytes, manifest


def _write_immutable(path: Path, content: bytes) -> str:
    if path.exists():
        existing = path.read_bytes()
        if existing == content:
            return "VERIFIED"
        if _lf_normalized_bytes(existing) == _lf_normalized_bytes(content):
            return "VERIFIED_EOL_NORMALIZED"
        if existing != content:
            existing_sha = hashlib.sha256(_lf_normalized_bytes(existing)).hexdigest()
            expected_sha = hashlib.sha256(_lf_normalized_bytes(content)).hexdigest()
            raise RuntimeError(
                f"Refusing to overwrite immutable RP2 v6 artifact: {path}. "
                f"LF-normalized sha256 existing={existing_sha}, expected={expected_sha}. "
                f"{_difference_diagnostic(path, existing, content)}. "
                "This is a real content/provenance difference, not an LF/CRLF difference. "
                "Use a new protocol/output path for changed inputs."
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return "CREATED"


def _verify_immutable(path: Path, expected: bytes) -> str:
    if not path.is_file():
        raise RuntimeError(f"RP2 v6 immutable artifact is missing: {path}")
    actual = path.read_bytes()
    if actual == expected:
        return "VERIFIED"
    if _lf_normalized_bytes(actual) == _lf_normalized_bytes(expected):
        return "VERIFIED_EOL_NORMALIZED"
    actual_sha = hashlib.sha256(_lf_normalized_bytes(actual)).hexdigest()
    expected_sha = hashlib.sha256(_lf_normalized_bytes(expected)).hexdigest()
    raise RuntimeError(
        f"RP2 v6 immutable artifact differs: {path}. "
        f"LF-normalized sha256 actual={actual_sha}, expected={expected_sha}. "
        f"{_difference_diagnostic(path, actual, expected)}."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/rp2_graphrag_v6_equal_budget.json")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="validate inputs and require the replay and manifest to already match",
    )
    args = parser.parse_args()

    config_path = ROOT / args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    replay_bytes, manifest = build_replay(ROOT, config, config_path)
    replay_path = ROOT / config["frozen_retrieval_results"]
    manifest_path = ROOT / config["frozen_retrieval_manifest"]
    manifest_bytes = _json_bytes(manifest)

    if args.verify_only:
        replay_status = _verify_immutable(replay_path, replay_bytes)
        manifest_status = _verify_immutable(manifest_path, manifest_bytes)
    else:
        replay_status = _write_immutable(replay_path, replay_bytes)
        manifest_status = _write_immutable(manifest_path, manifest_bytes)

    print(
        f"[RP2 v6 replay] {replay_status}: records={manifest['validation']['records']}, "
        f"methods={manifest['validation']['methods']}, "
        f"queries/method={manifest['validation']['queries_per_method']}",
        flush=True,
    )
    print(f"[RP2 v6 replay] replay={replay_path.relative_to(ROOT)}", flush=True)
    print(
        f"[RP2 v6 replay] {manifest_status}: manifest={manifest_path.relative_to(ROOT)}",
        flush=True,
    )
    print(
        "[RP2 v6 replay] IMPORTANT: archived v3/v4 elapsed_ms is audit-only; "
        "rerun retrieval for formal v6 latency.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
