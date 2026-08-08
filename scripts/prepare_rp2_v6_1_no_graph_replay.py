#!/usr/bin/env python3
"""Create the immutable RP2 v6.1 Full-vs-NoGraph retrieval replay.

The Full rows are copied from the frozen v6 replay.  The fair no-graph control
is recomputed with the same dense index, role gate, fault-affinity settings,
source novelty, underfill policy, and K=3 budget; only graph propagation and
the graph-proximity score are disabled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.dataset import EvidenceCandidate, SilverQuery, _read_jsonl  # noqa: E402
from research_point_2.dense_index import DenseEvidenceIndex  # noqa: E402
from research_point_2.graph_rag_v2 import retrieve_dense_graph  # noqa: E402
from research_point_2.local_models import BgeM3Encoder  # noqa: E402
from research_point_2.retrieval import RetrievalBudget, RetrievalIndex  # noqa: E402


def _normalized_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(_normalized_bytes(path)).hexdigest()


def _candidate(row: dict[str, Any]) -> EvidenceCandidate:
    payload = dict(row)
    payload["fault_class_ids"] = tuple(payload.get("fault_class_ids", []))
    return EvidenceCandidate(**payload)


def _query(row: dict[str, Any]) -> SilverQuery:
    payload = dict(row)
    payload["relevant_evidence_ids"] = tuple(payload.get("relevant_evidence_ids", []))
    payload["candidate_evidence_ids"] = tuple(payload.get("candidate_evidence_ids", []))
    return SilverQuery(**payload)


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _write_immutable(path: Path, content: bytes) -> str:
    if path.is_file():
        if path.read_bytes() == content or _normalized_bytes(path) == content:
            return "VERIFIED"
        raise RuntimeError(
            f"Refusing to overwrite immutable RP2 v6.1 artifact: {path}. "
            "Use a new protocol/output path for changed inputs."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return "CREATED"


def _input_fingerprint(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    benchmark = ROOT / config["benchmark_dir"]
    paths = {
        "config": config_path,
        "base_full_replay": ROOT / config["base_full_replay"],
        "queries": benchmark / "queries.jsonl",
        "evidence_candidates": benchmark / "evidence_candidates.jsonl",
        "dense_index_manifest": ROOT / config["embedding"]["index_dir"] / "manifest.json",
    }
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"Missing {name}: {path}")
    return {
        name: {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha256(path)}
        for name, path in paths.items()
    }


def _verify_existing(config: dict[str, Any], inputs: dict[str, Any]) -> bool:
    replay = ROOT / config["frozen_retrieval_results"]
    manifest_path = ROOT / config["frozen_retrieval_manifest"]
    if not replay.is_file() or not manifest_path.is_file():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("inputs") != inputs:
        raise RuntimeError(
            "Existing immutable v6.1 replay has different inputs. Use a new protocol path."
        )
    if manifest.get("replay", {}).get("sha256") != _sha256(replay):
        raise RuntimeError("Existing immutable v6.1 replay hash does not match its manifest")
    print(
        f"[RP2 v6.1 replay] VERIFIED: records={manifest['replay']['records']}, "
        f"path={replay.relative_to(ROOT)}",
        flush=True,
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", default="configs/rp2_graphrag_v6_1_no_graph_control.json"
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    config_path = ROOT / args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    inputs = _input_fingerprint(config_path, config)
    if _verify_existing(config, inputs):
        return 0
    if args.verify_only:
        raise RuntimeError("Immutable v6.1 replay does not exist")

    benchmark = ROOT / config["benchmark_dir"]
    candidates = [_candidate(row) for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")]
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    if any(query.candidate_evidence_ids for query in queries):
        raise RuntimeError("Positive-seeded candidate pools are forbidden")

    base_method = str(config["base_full_method"])
    base_rows = {
        str(row["query_id"]): row
        for row in _read_jsonl(ROOT / config["base_full_replay"])
        if str(row.get("method")) == base_method
    }
    if set(base_rows) != {query.query_id for query in queries}:
        raise RuntimeError("Base Full replay does not cover the v6.1 query set exactly")

    embedding = config["embedding"]
    encoder = BgeM3Encoder(
        ROOT / embedding["model_path"],
        batch_size=int(embedding["batch_size"]),
        max_length=int(embedding["max_length"]),
        device=embedding.get("device"),
        require_cuda=bool(config.get("runtime", {}).get("require_cuda", True)),
    )
    dense_index = DenseEvidenceIndex.load(ROOT / embedding["index_dir"])
    graph_index = RetrievalIndex(candidates)
    retrieval = config["retrieval"]
    no_graph_scenario = next(
        row for row in config["scenarios"] if row["retrieval_method"] == "dense_ours_v4_no_graph"
    )
    budget = RetrievalBudget(
        max_scored_candidates=int(retrieval["max_scored_candidates"]),
        max_selected_evidence=int(no_graph_scenario["max_selected_evidence"]),
        max_per_source_family=int(retrieval["max_per_source_family"]),
        source_family_bonus=float(retrieval["source_family_bonus"]),
        redundancy_penalty=float(retrieval["redundancy_penalty"]),
    )

    output_rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    total = len(queries)
    for index, query in enumerate(queries, start=1):
        full = dict(base_rows[query.query_id])
        full["method"] = "Full_v6_1_k3"
        full["source_method"] = base_method
        full["elapsed_ms"] = 0.0
        full["replay_provenance"] = {
            "schema": "rp2_v6_1_graph_attribution_replay_v1",
            "origin": "frozen_v6_full_replay",
            "formal_latency_eligible": False,
        }
        output_rows.append(full)

        result = retrieve_dense_graph(
            query,
            candidates,
            graph_index,
            dense_index,
            encoder,
            method="dense_ours_v4_no_graph",
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
        no_graph = replace(
            result, method="FullNoGraph_v6_1_k3", elapsed_ms=0.0
        ).to_dict()
        no_graph["source_method"] = "dense_ours_v4_no_graph"
        no_graph["replay_provenance"] = {
            "schema": "rp2_v6_1_graph_attribution_replay_v1",
            "origin": "fresh_same_constraints_no_graph",
            "formal_latency_eligible": False,
        }
        output_rows.append(no_graph)
        elapsed = time.perf_counter() - started
        eta = elapsed / index * (total - index)
        print(
            f"[RP2 v6.1 replay][{index}/{total}] {query.query_id} "
            f"no_graph_candidates={len(result.ranked)}, elapsed={elapsed:.1f}s, "
            f"ETA={eta / 60:.1f}m",
            flush=True,
        )

    replay_bytes = _jsonl_bytes(output_rows)
    replay_path = ROOT / config["frozen_retrieval_results"]
    manifest_path = ROOT / config["frozen_retrieval_manifest"]
    replay_status = _write_immutable(replay_path, replay_bytes)
    manifest = {
        "manifest_schema": "rp2_v6_1_graph_attribution_replay_manifest_v1",
        "protocol_id": config["protocol_id"],
        "immutable": True,
        "inputs": inputs,
        "comparison": config["primary_comparison"],
        "replay": {
            "path": replay_path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(replay_bytes).hexdigest(),
            "records": len(output_rows),
            "queries_per_method": len(queries),
        },
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    manifest_status = _write_immutable(manifest_path, _json_bytes(manifest))
    print(
        f"[RP2 v6.1 replay] {replay_status}/{manifest_status}: "
        f"records={len(output_rows)}, path={replay_path.relative_to(ROOT)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
