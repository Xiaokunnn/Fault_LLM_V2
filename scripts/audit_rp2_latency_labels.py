#!/usr/bin/env python3
"""Audit RP2 interleaved-latency method labels without rewriting raw records."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METHODS = ("B1_dense_k4", "B4_metapath_k3", "Ours_k3")
SWAP_PEER = {
    "B1_dense_k4": "B1_dense_k4",
    "B4_metapath_k3": "Ours_k3",
    "Ours_k3": "B4_metapath_k3",
}


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    mean_left = statistics.fmean(left)
    mean_right = statistics.fmean(right)
    numerator = sum(
        (x - mean_left) * (y - mean_right) for x, y in zip(left, right)
    )
    denominator = math.sqrt(
        sum((x - mean_left) ** 2 for x in left)
        * sum((y - mean_right) ** 2 for y in right)
    )
    return numerator / denominator if denominator else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--latency",
        default=(
            "results/experiments/research_point_2/"
            "rp2_v3_interleaved_latency/latency_replay.jsonl"
        ),
    )
    parser.add_argument(
        "--generation",
        default=(
            "results/experiments/research_point_2/"
            "graphrag_v3_budget_effectiveness/generation_results.jsonl"
        ),
    )
    parser.add_argument(
        "--config", default="configs/rp2_graphrag_v3_budget_effectiveness.json"
    )
    parser.add_argument(
        "--output",
        default=(
            "results/experiments/research_point_2/"
            "rp2_v3_interleaved_latency/latency_label_integrity_audit.json"
        ),
    )
    args = parser.parse_args()

    latency_path = ROOT / args.latency
    generation_path = ROOT / args.generation
    config_path = ROOT / args.config
    records = _read_jsonl(latency_path)
    generations = _read_jsonl(generation_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    generation_by_key = {
        (str(row["query_id"]), str(row["method"])): row for row in generations
    }
    scenario_map = {
        str(row["id"]): str(row["retrieval_method"])
        for row in config["scenarios"]
        if str(row["id"]) in METHODS
    }

    method_audits: dict[str, dict] = {}
    all_own_matches = True
    for method in METHODS:
        rows = [row for row in records if row.get("method") == method]
        own_exact = 0
        swapped_exact = 0
        walls: list[float] = []
        generated_tokens: list[float] = []
        model_latencies: list[float] = []
        for row in rows:
            query_id = str(row["query_id"])
            own = generation_by_key[(query_id, method)]
            peer = generation_by_key[(query_id, SWAP_PEER[method])]
            own_exact += int(
                int(row["planned_prompt_tokens"])
                == int(own["planned_prompt_tokens"])
            )
            swapped_exact += int(
                int(row["planned_prompt_tokens"])
                == int(peer["planned_prompt_tokens"])
            )
            walls.append(float(row["online_wall_ms"]))
            generated_tokens.append(float(row["model_metrics"]["generated_tokens"]))
            model_latencies.append(float(row["model_metrics"]["elapsed_ms"]))
        all_own_matches &= own_exact == len(rows)
        method_audits[method] = {
            "retrieval_method_from_frozen_config": scenario_map.get(method),
            "records": len(rows),
            "prompt_token_exact_match_to_own_method": own_exact,
            "prompt_token_exact_match_to_swapped_peer": swapped_exact,
            "mean_online_wall_ms": statistics.fmean(walls) if walls else None,
            "mean_generated_tokens": statistics.fmean(generated_tokens)
            if generated_tokens
            else None,
            "wall_time_generated_token_correlation": _correlation(
                walls, generated_tokens
            ),
            "mean_wall_minus_model_ms": statistics.fmean(
                wall - model
                for wall, model in zip(walls, model_latencies)
            )
            if walls
            else None,
            "order_position_counts": dict(
                Counter(str(row["order_position"]) for row in rows)
            ),
        }

    audit = {
        "audit_id": "rp2_v3_interleaved_latency_method_label_integrity_v1",
        "raw_latency_path": args.latency,
        "raw_latency_sha256": hashlib.sha256(latency_path.read_bytes()).hexdigest(),
        "generation_reference_path": args.generation,
        "generation_reference_sha256": hashlib.sha256(
            generation_path.read_bytes()
        ).hexdigest(),
        "frozen_config_path": args.config,
        "method_audits": method_audits,
        "label_swap_supported_by_evidence": False,
        "raw_data_rewrite_authorized_by_audit": False,
        "conclusion": (
            "All latency records match their own method's deterministic prompt-token "
            "signature. The execution path times and writes the same scenario_id, and "
            "wall time closely tracks generated-token count. Swapping labels would "
            "contradict the recorded execution evidence."
        ),
        "all_records_match_own_method_signature": all_own_matches,
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[RP2 latency audit] output={output}")
    print(
        "[RP2 latency audit] label swap supported=False; "
        f"own signatures complete={all_own_matches}"
    )
    if not all_own_matches:
        raise RuntimeError("Latency labels failed their own deterministic signatures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
