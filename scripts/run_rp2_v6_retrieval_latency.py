#!/usr/bin/env python3
"""Rerun only RP2 v6 retrieval with paired, interleaved latency measurements.

The existing BGE-M3 index and graph are loaded read-only.  No generation is
performed.  Every fresh ranking must match the immutable v6 replay before its
latency can be paired with the generation-stage measurements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.dataset import (  # noqa: E402
    EvidenceCandidate,
    SilverQuery,
    _read_jsonl,
)
from research_point_2.dense_index import DenseEvidenceIndex  # noqa: E402
from research_point_2.graph_rag_v2 import retrieve_dense_graph  # noqa: E402
from research_point_2.local_models import (  # noqa: E402
    BgeM3Encoder,
    model_file_manifest,
)
from research_point_2.retrieval import RetrievalBudget, RetrievalIndex  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate(row: dict[str, Any]) -> EvidenceCandidate:
    payload = dict(row)
    payload["fault_class_ids"] = tuple(payload.get("fault_class_ids", []))
    return EvidenceCandidate(**payload)


def _query(row: dict[str, Any]) -> SilverQuery:
    payload = dict(row)
    payload["relevant_evidence_ids"] = tuple(payload.get("relevant_evidence_ids", []))
    payload["candidate_evidence_ids"] = tuple(payload.get("candidate_evidence_ids", []))
    return SilverQuery(**payload)


def _rotated(rows: list[dict[str, Any]], offset: int) -> list[dict[str, Any]]:
    if not rows:
        return []
    position = offset % len(rows)
    return rows[position:] + rows[:position]


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _load_expected(path: Path) -> dict[tuple[str, str], tuple[str, ...]]:
    expected: dict[tuple[str, str], tuple[str, ...]] = {}
    for row in _read_jsonl(path):
        key = (str(row["method"]), str(row["query_id"]))
        if key in expected:
            raise RuntimeError(f"Duplicate immutable replay key: {key}")
        expected[key] = tuple(str(item["evidence_id"]) for item in row.get("ranked", []))
    return expected


def _cuda_sync_factory(require_cuda: bool) -> tuple[Callable[[], None], dict[str, Any]]:
    try:
        import torch
    except ImportError:
        if require_cuda:
            raise RuntimeError("PyTorch is required for CUDA-synchronized latency")
        return lambda: None, {"cuda_available": False, "device": "cpu"}
    available = bool(torch.cuda.is_available())
    if require_cuda and not available:
        raise RuntimeError("CUDA is required by the v6 latency protocol but is unavailable")
    if not available:
        return lambda: None, {"cuda_available": False, "device": "cpu"}
    return torch.cuda.synchronize, {
        "cuda_available": True,
        "device": str(torch.cuda.current_device()),
        "gpu_name": torch.cuda.get_device_name(torch.cuda.current_device()),
        "torch_version": str(torch.__version__),
        "compiled_cuda": str(torch.version.cuda),
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/rp2_graphrag_v6_equal_budget.json")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--methods", nargs="*")
    parser.add_argument("--output-dir")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config_path = ROOT / args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    scenarios = [dict(row) for row in config["scenarios"]]
    if args.methods:
        requested = set(args.methods)
        scenarios = [
            row
            for row in scenarios
            if str(row["id"]) in requested or str(row["retrieval_method"]) in requested
        ]
        if not scenarios:
            raise ValueError("No v6 retrieval latency scenarios matched --methods")

    benchmark = ROOT / config["benchmark_dir"]
    candidates = [_candidate(row) for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")]
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    if args.limit:
        queries = queries[: args.limit]
    if any(query.candidate_evidence_ids for query in queries):
        raise RuntimeError("Positive-seeded candidate pools are forbidden in the v6 main result")

    if args.output_dir:
        output = ROOT / args.output_dir
    elif args.limit:
        output = ROOT / ".tmp/rp2_v6_retrieval_latency_smoke"
    else:
        output = ROOT / config["retrieval_latency_output_dir"]
    if output.exists() and any(output.iterdir()) and not args.force:
        raise RuntimeError(f"Output is not empty: {output}; pass --force or choose a new directory")

    replay_path = ROOT / config["frozen_retrieval_results"]
    manifest_path = ROOT / config["frozen_retrieval_manifest"]
    if not replay_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(
            "Prepare and verify the immutable v6 replay before measuring retrieval latency"
        )
    expected = _load_expected(replay_path)

    embedding = config["embedding"]
    model_path = ROOT / embedding["model_path"]
    index_path = ROOT / embedding["index_dir"]
    if not model_path.is_dir():
        raise FileNotFoundError(f"BGE-M3 model missing: {model_path}")
    if not index_path.is_dir():
        raise FileNotFoundError(
            f"Existing BGE-M3 index missing: {index_path}; this runner does not rebuild it"
        )

    require_cuda = bool(config.get("runtime", {}).get("require_cuda", True))
    synchronize, cuda_manifest = _cuda_sync_factory(require_cuda)
    encoder = BgeM3Encoder(
        model_path,
        batch_size=int(embedding.get("batch_size", 16)),
        max_length=int(embedding.get("max_length", 8192)),
        device=embedding.get("device"),
        require_cuda=require_cuda,
    )
    dense_index = DenseEvidenceIndex.load(index_path)
    graph_index = RetrievalIndex(candidates)
    retrieval = config["retrieval"]

    def retrieve(query: SilverQuery, scenario: dict[str, Any]):
        budget = RetrievalBudget(
            max_scored_candidates=int(retrieval["max_scored_candidates"]),
            max_selected_evidence=int(scenario["max_selected_evidence"]),
            max_per_source_family=int(retrieval["max_per_source_family"]),
            source_family_bonus=float(retrieval["source_family_bonus"]),
            redundancy_penalty=float(retrieval["redundancy_penalty"]),
        )
        return retrieve_dense_graph(
            query,
            candidates,
            graph_index,
            dense_index,
            encoder,
            method=str(scenario["retrieval_method"]),
            budget=budget,
            dense_top_n=int(retrieval["dense_top_n"]),
            anchor_evidence_count=int(retrieval["anchor_evidence_count"]),
            fixed_hops=int(retrieval["fixed_hops"]),
            ours_graph_hops=int(retrieval["ours_graph_hops"]),
            ours_graph_decay=float(retrieval["ours_graph_decay"]),
            graph_score_weight=float(retrieval["graph_score_weight"]),
            fault_affinity_weight=float(retrieval["fault_affinity_weight"]),
            fault_affinity_floor=float(retrieval["fault_affinity_floor"]),
        )

    warmup_runs = int(config["latency_protocol"].get("warmup_runs", 2))
    if queries:
        print(f"[RP2 v6 retrieval latency] warmup={warmup_runs} full method rounds", flush=True)
        for warmup in range(warmup_runs):
            for scenario in _rotated(scenarios, warmup):
                retrieve(queries[0], scenario)
        synchronize()

    repeats = int(config["latency_protocol"].get("interleaved_repeats", 3))
    rows: list[dict[str, Any]] = []
    total = repeats * len(queries) * len(scenarios)
    completed = 0
    started_all = time.perf_counter()
    for repeat in range(repeats):
        for query_index, query in enumerate(queries):
            ordered = _rotated(scenarios, query_index + repeat)
            order_ids = [str(row["id"]) for row in ordered]
            for order_position, scenario in enumerate(ordered):
                method_id = str(scenario["id"])
                synchronize()
                started = time.perf_counter_ns()
                result = retrieve(query, scenario)
                synchronize()
                wall_ms = (time.perf_counter_ns() - started) / 1_000_000
                actual_ids = tuple(item.evidence_id for item in result.ranked)
                expected_ids = expected.get((method_id, query.query_id))
                if expected_ids is None:
                    raise RuntimeError(f"Immutable replay row missing: {method_id}:{query.query_id}")
                if actual_ids != expected_ids:
                    raise RuntimeError(
                        f"Fresh ranking differs from immutable replay for {method_id}:{query.query_id}; "
                        f"expected={expected_ids}, actual={actual_ids}. Do not pair this latency with "
                        "the frozen generation result."
                    )
                completed += 1
                rows.append(
                    {
                        "protocol_id": config["protocol_id"],
                        "repeat": repeat,
                        "query_index": query_index,
                        "query_id": query.query_id,
                        "method": method_id,
                        "method_order": order_ids,
                        "method_order_position": order_position,
                        "candidate_budget": int(scenario["max_selected_evidence"]),
                        "retrieval_ms": wall_ms,
                        "internal_retrieval_ms": float(result.elapsed_ms),
                        "ranked_evidence_ids": list(actual_ids),
                        "ranking_matches_immutable_replay": True,
                    }
                )
                elapsed = time.perf_counter() - started_all
                eta = elapsed / completed * (total - completed) if completed else 0.0
                print(
                    f"[RP2 v6 retrieval latency][{completed}/{total}] "
                    f"repeat={repeat + 1}/{repeats} {method_id}:{query.query_id} "
                    f"retrieval={wall_ms:.2f}ms ETA={eta / 60:.1f}m",
                    flush=True,
                )

    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row["method"])].append(float(row["retrieval_ms"]))
    summary = {
        "protocol_id": config["protocol_id"],
        "latency_scope": "fresh CUDA-synchronized retrieval only; model loading/warmup excluded",
        "decision_policy": "single_run",
        "measurement_repeats": repeats,
        "warmup_runs": warmup_runs,
        "queries": len(queries),
        "methods": {
            method: {
                "samples": len(values),
                "retrieval_ms_mean": statistics.fmean(values),
                "retrieval_ms_median": statistics.median(values),
                "retrieval_ms_p95": _percentile(values, 0.95),
            }
            for method, values in grouped.items()
        },
        "all_rankings_match_immutable_replay": True,
        "runtime": {
            "cuda": cuda_manifest,
            "encoder": getattr(encoder, "runtime_manifest", {}),
            "embedding_model": model_file_manifest(model_path),
        },
        "inputs": {
            "config": {"path": args.config, "sha256": _sha256(config_path)},
            "replay": {
                "path": str(replay_path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _sha256(replay_path),
            },
            "replay_manifest": {
                "path": str(manifest_path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _sha256(manifest_path),
            },
        },
    }

    output.mkdir(parents=True, exist_ok=True)
    rows_path = output / "retrieval_latency_runs.jsonl"
    summary_path = output / "retrieval_latency_summary.json"
    _write_jsonl(rows_path, rows)
    summary["artifacts"] = {
        "retrieval_latency_runs": {
            "path": str(rows_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256(rows_path),
        }
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[RP2 v6 retrieval latency] completed: {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
