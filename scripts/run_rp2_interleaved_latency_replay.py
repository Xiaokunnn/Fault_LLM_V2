#!/usr/bin/env python3
"""Counterbalanced repeated latency replay for the three frozen RP2 finalists."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.dataset import EvidenceCandidate, SilverQuery, _read_jsonl  # noqa: E402
from research_point_2.dense_index import DenseEvidenceIndex  # noqa: E402
from research_point_2.generation import SYSTEM_PROMPT, fit_prompt_budget  # noqa: E402
from research_point_2.graph_rag_v2 import retrieve_dense_graph  # noqa: E402
from research_point_2.local_models import BgeM3Encoder, QwenLocalGenerator, model_file_manifest  # noqa: E402
from research_point_2.retrieval import RetrievalBudget, RetrievalIndex  # noqa: E402


FINALISTS = ("B1_dense_k4", "B4_metapath_k3", "Ours_k3")


def _candidate(row: dict) -> EvidenceCandidate:
    row = dict(row)
    row["fault_class_ids"] = tuple(row.get("fault_class_ids", []))
    return EvidenceCandidate(**row)


def _query(row: dict) -> SilverQuery:
    row = dict(row)
    row["relevant_evidence_ids"] = tuple(row.get("relevant_evidence_ids", []))
    row["candidate_evidence_ids"] = tuple(row.get("candidate_evidence_ids", []))
    return SilverQuery(**row)


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _read_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def _scenario_map(config: dict) -> dict[str, dict]:
    rows = {str(row["id"]): dict(row) for row in config["scenarios"]}
    missing = set(FINALISTS) - set(rows)
    if missing:
        raise ValueError(f"Frozen latency finalists missing from config: {sorted(missing)}")
    return {name: rows[name] for name in FINALISTS}


def _summarize(records: list[dict], repeats: int, config: dict, encoder, generator) -> dict:
    methods = {}
    for method in FINALISTS:
        rows = [row for row in records if row["method"] == method]
        latencies = [float(row["online_wall_ms"]) for row in rows]
        methods[method] = {
            "samples": len(rows),
            "expected_samples": 40 * repeats,
            "completed": len(rows) == 40 * repeats,
            "online_wall_ms_mean": statistics.fmean(latencies) if latencies else 0.0,
            "online_wall_ms_p50": _percentile(latencies, 0.50),
            "online_wall_ms_p95": _percentile(latencies, 0.95),
            "online_wall_ms_stdev": statistics.pstdev(latencies) if len(latencies) > 1 else 0.0,
            "prompt_tokens_mean": statistics.fmean(
                [float(row["model_metrics"].get("prompt_tokens", 0)) for row in rows]
            ) if rows else 0.0,
            "generated_tokens_mean": statistics.fmean(
                [float(row["model_metrics"].get("generated_tokens", 0)) for row in rows]
            ) if rows else 0.0,
            "json_success_rate": statistics.fmean(
                [float(bool(row["model_metrics"].get("model_output_valid_json", True))) for row in rows]
            ) if rows else 0.0,
            "order_position_counts": {
                str(position): sum(int(row["order_position"]) == position for row in rows)
                for position in range(len(FINALISTS))
            },
            "latency_by_order_position": {
                str(position): {
                    "samples": len(position_rows),
                    "p50_ms": _percentile(position_rows, 0.50),
                    "p95_ms": _percentile(position_rows, 0.95),
                }
                for position in range(len(FINALISTS))
                for position_rows in [[
                    float(row["online_wall_ms"])
                    for row in rows if int(row["order_position"]) == position
                ]]
            },
            "latency_by_repeat": {
                str(repeat): {
                    "samples": len(repeat_rows),
                    "p50_ms": _percentile(repeat_rows, 0.50),
                    "p95_ms": _percentile(repeat_rows, 0.95),
                }
                for repeat in range(repeats)
                for repeat_rows in [[
                    float(row["online_wall_ms"])
                    for row in rows if int(row["repeat"]) == repeat
                ]]
            },
        }
    comparisons = []
    for reference in ("B1_dense_k4", "B4_metapath_k3"):
        paired = []
        for query_id in sorted({row["query_id"] for row in records}):
            ours = [float(row["online_wall_ms"]) for row in records if row["method"] == "Ours_k3" and row["query_id"] == query_id]
            baseline = [float(row["online_wall_ms"]) for row in records if row["method"] == reference and row["query_id"] == query_id]
            if ours and baseline:
                paired.append(statistics.median(ours) - statistics.median(baseline))
        comparisons.append({
            "reference": reference,
            "proposed": "Ours_k3",
            "paired_queries": len(paired),
            "median_of_query_median_latency_delta_ms": statistics.median(paired) if paired else None,
            "mean_of_query_median_latency_delta_ms": statistics.fmean(paired) if paired else None,
            "ours_faster_query_rate": sum(value < 0 for value in paired) / len(paired) if paired else None,
        })
    return {
        "protocol_id": "marine_pump_rp2_interleaved_latency_v1",
        "frozen_parent_protocol": config["protocol_id"] + "@" + config["version"],
        "methods": methods,
        "comparisons": comparisons,
        "repeats_per_query": repeats,
        "query_count": 40,
        "counterbalancing": "Latin rotation by repeat and query index; method order is not blocked",
        "latency_scope": "warm online retrieval + exact prompt fitting + tokenization + deterministic generation",
        "embedding_runtime": encoder.runtime_manifest,
        "embedding_device": encoder.device,
        "generator_runtime": generator.runtime_manifest,
        "embedding_model": model_file_manifest(ROOT / config["embedding"]["model_path"]),
        "generator_model": model_file_manifest(ROOT / config["generator"]["model_path"]),
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/rp2_graphrag_v3_budget_effectiveness.json")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0, help="Smoke-test query limit; formal run must use 0")
    parser.add_argument("--output-dir", default="results/experiments/research_point_2/rp2_v3_interleaved_latency")
    args = parser.parse_args()
    if args.repeats < 1:
        raise ValueError("--repeats must be positive")
    config = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    scenarios = _scenario_map(config)
    benchmark = ROOT / config["benchmark_dir"]
    candidates = [_candidate(row) for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")]
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    if args.limit:
        queries = queries[: args.limit]
    if any(query.candidate_evidence_ids for query in queries):
        raise RuntimeError("Latency replay requires leakage-safe full-graph queries")
    embedding = config["embedding"]
    encoder = BgeM3Encoder(
        ROOT / embedding["model_path"],
        batch_size=int(embedding["batch_size"]),
        max_length=int(embedding["max_length"]),
        device=embedding.get("device"),
        require_cuda=True,
    )
    generator = QwenLocalGenerator(
        ROOT / config["generator"]["model_path"],
        device_map=config["generator"]["device_map"],
        dtype=config["generator"]["dtype"],
        require_cuda=True,
    )
    dense = DenseEvidenceIndex.load(ROOT / embedding["index_dir"])
    graph = RetrievalIndex(candidates)
    by_id = {row.evidence_id: row for row in candidates}
    retrieval_cfg = config["retrieval"]
    contract = config["generation_contract"]
    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / "latency_replay.jsonl"
    records = _read_existing(raw_path)
    completed = {(int(row["repeat"]), row["query_id"], row["method"]) for row in records}

    def retrieve(query: SilverQuery, scenario_id: str):
        scenario = scenarios[scenario_id]
        budget = RetrievalBudget(
            max_scored_candidates=int(scenario.get("max_scored_candidates", retrieval_cfg["max_scored_candidates"])),
            max_selected_evidence=int(scenario["max_selected_evidence"]),
            max_per_source_family=int(scenario.get("max_per_source_family", retrieval_cfg["max_per_source_family"])),
            source_family_bonus=float(scenario.get("source_family_bonus", retrieval_cfg["source_family_bonus"])),
            redundancy_penalty=float(scenario.get("redundancy_penalty", retrieval_cfg["redundancy_penalty"])),
        )
        return retrieve_dense_graph(
            query, candidates, graph, dense, encoder,
            method=str(scenario["retrieval_method"]), budget=budget,
            dense_top_n=int(scenario.get("dense_top_n", retrieval_cfg["dense_top_n"])),
            anchor_evidence_count=int(scenario.get("anchor_evidence_count", retrieval_cfg["anchor_evidence_count"])),
            fixed_hops=int(scenario.get("fixed_hops", retrieval_cfg["fixed_hops"])),
            ours_graph_hops=int(scenario.get("ours_graph_hops", retrieval_cfg["ours_graph_hops"])),
            ours_graph_decay=float(scenario.get("ours_graph_decay", retrieval_cfg["ours_graph_decay"])),
            graph_score_weight=float(scenario.get("graph_score_weight", retrieval_cfg["graph_score_weight"])),
        )

    print(f"[RP2 latency] warmups={args.warmups} per method", flush=True)
    for scenario_id in FINALISTS:
        for _ in range(args.warmups):
            result = retrieve(queries[0], scenario_id)
            evidence = [by_id[row.evidence_id] for row in result.ranked]
            prompt, _, _, _ = fit_prompt_budget(queries[0], evidence, generator, contract)
            generator.generate_json(SYSTEM_PROMPT, prompt, max_new_tokens=int(config["generator"]["max_new_tokens"]))

    total = args.repeats * len(queries) * len(FINALISTS)
    done = len(completed)
    completed_this_run = 0
    started = time.perf_counter()
    with raw_path.open("a", encoding="utf-8", newline="\n") as handle:
        for repeat in range(args.repeats):
            for query_index, query in enumerate(queries):
                offset = (repeat + query_index) % len(FINALISTS)
                order = FINALISTS[offset:] + FINALISTS[:offset]
                for order_position, scenario_id in enumerate(order):
                    key = (repeat, query.query_id, scenario_id)
                    if key in completed:
                        continue
                    wall_started = time.perf_counter()
                    result = retrieve(query, scenario_id)
                    evidence = [by_id[row.evidence_id] for row in result.ranked]
                    fit_started = time.perf_counter()
                    prompt, kept, dropped, planned_tokens = fit_prompt_budget(query, evidence, generator, contract)
                    fit_ms = (time.perf_counter() - fit_started) * 1000
                    answer = generator.generate_json(
                        SYSTEM_PROMPT, prompt,
                        max_new_tokens=int(config["generator"]["max_new_tokens"]),
                    )
                    online_wall_ms = (time.perf_counter() - wall_started) * 1000
                    row = {
                        "repeat": repeat,
                        "query_id": query.query_id,
                        "method": scenario_id,
                        "order_position": order_position,
                        "selected_evidence_ids": [item.evidence_id for item in kept],
                        "retrieval_elapsed_ms": result.elapsed_ms,
                        "prompt_fit_ms": fit_ms,
                        "planned_prompt_tokens": planned_tokens,
                        "prompt_budget_dropped_evidence": dropped,
                        "online_wall_ms": online_wall_ms,
                        "model_metrics": dict(generator.last_metrics),
                        "answer_status": answer.get("status"),
                    }
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                    handle.flush()
                    records.append(row)
                    completed.add(key)
                    done += 1
                    completed_this_run += 1
                    elapsed = time.perf_counter() - started
                    eta = elapsed / max(1, completed_this_run) * (total - done) / 60
                    print(
                        f"[RP2 latency][{done}/{total}] r={repeat} {query.query_id} "
                        f"{scenario_id} pos={order_position} wall={online_wall_ms:.1f}ms ETA={eta:.1f}m",
                        flush=True,
                    )
    summary = _summarize(records, args.repeats, config, encoder, generator)
    summary["formal_full_query_run"] = not args.limit
    (output / "latency_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[RP2 latency] completed: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
