#!/usr/bin/env python3
"""Run the RP2 v6 equal-budget generation and latency protocol.

The runner deliberately keeps quality decisions and performance repetitions
separate.  Repeat zero is the single deterministic deployment decision used
for every quality metric.  Later rotating/interleaved repeats are independent
measurements only; their masks are never fused or voted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from research_point_2.budget_effectiveness import analyze_budget_effectiveness  # noqa: E402
from research_point_2.dataset import _read_jsonl  # noqa: E402
from research_point_2.evaluation import evaluate_results  # noqa: E402
from research_point_2.generation import (  # noqa: E402
    RECALL_REVIEW_SYSTEM_PROMPT,
    apply_evidence_coverage_guard,
    build_recall_review_prompt,
    expand_compact_evidence_mask,
    fit_prompt_budget,
    parse_single_recall_review,
    score_silver_response,
    summarize_generation_rows,
    system_prompt_for_strategy,
    validate_candidate_assessment_contract,
    validate_generated_answer,
)
from research_point_2.local_models import (  # noqa: E402
    QwenLocalGenerator,
    model_file_manifest,
)
from research_point_2.retrieval import RetrievalResult  # noqa: E402
from scripts.run_rp2_graphrag_v2 import (  # noqa: E402
    _candidate,
    _plot_metrics,
    _query,
    _retrieval_result,
    _sha256,
)


CANONICAL_QUALITY_REPEAT = 0
DEFAULT_METHOD_ORDER = (
    "B1_dense_k3_equal",
    "B4_role_k3_equal",
    "A2_role_graph_k3_equal",
    "Ours_v6_k3_equal",
    "B1_dense_k4_secondary",
)
VERIFICATION_MODES = {
    "direct_render",
    "stage1_only",
    "stage1_plus_review",
}


def _median(values: Iterable[float]) -> float:
    rows = [float(value) for value in values]
    return float(statistics.median(rows)) if rows else 0.0


def _rotated(rows: list[dict], offset: int) -> list[dict]:
    if not rows:
        return []
    offset %= len(rows)
    return rows[offset:] + rows[:offset]


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def _atomic_write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(path)


def _checkpoint_key(row: dict) -> tuple[int, str, str]:
    return int(row["repeat"]), str(row["method"]), str(row["query_id"])


def _load_checkpoints(path: Path, protocol_fingerprint: str) -> dict[tuple[int, str, str], dict]:
    if not path.is_file():
        return {}
    rows: dict[tuple[int, str, str], dict] = {}
    for row in _read_jsonl(path):
        if row.get("protocol_fingerprint") != protocol_fingerprint:
            continue
        rows[_checkpoint_key(row)] = row
    return rows


def _call_cached(
    generator: QwenLocalGenerator,
    *,
    system_prompt: str,
    user_prompt: str,
    max_new_tokens: int,
    cache_dir: Path,
    cache_payload: dict,
    force: bool,
) -> tuple[dict, dict, str, float]:
    key = hashlib.sha256(
        json.dumps(cache_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    path = cache_dir / f"{key}.json"
    started = time.perf_counter_ns()
    if path.is_file() and not force:
        cached = json.loads(path.read_text(encoding="utf-8"))
        wall_ms = (time.perf_counter_ns() - started) / 1_000_000
        return (
            cached["answer"],
            cached.get("generation_metrics", {}),
            "CACHE",
            wall_ms,
        )
    answer = generator.generate_json(
        system_prompt, user_prompt, max_new_tokens=max_new_tokens
    )
    metrics = dict(generator.last_metrics)
    wall_ms = (time.perf_counter_ns() - started) / 1_000_000
    _atomic_write_json(
        path,
        {
            "answer": answer,
            "generation_metrics": metrics,
            "cache_payload": cache_payload,
        },
    )
    return answer, metrics, "MODEL", wall_ms


def _call_metric_record(metrics: dict, *, source: str, call_wall_ms: float) -> dict:
    preparation = float(metrics.get("input_preparation_ms", 0.0))
    inference = float(metrics.get("elapsed_ms", 0.0))
    return {
        "source": source,
        "prompt_tokens": int(metrics.get("prompt_tokens", 0)),
        "generated_tokens": int(metrics.get("generated_tokens", 0)),
        "input_preparation_ms": preparation,
        "model_inference_ms": inference,
        "total_inference_ms": preparation + inference,
        "call_wall_ms": float(call_wall_ms),
        "tokens_per_second": float(metrics.get("tokens_per_second", 0.0)),
        "cuda_peak_memory_bytes": int(metrics.get("cuda_peak_memory_bytes", 0)),
        "cuda_allocated_memory_bytes": int(
            metrics.get("cuda_allocated_memory_bytes", 0)
        ),
        "model_output_valid_json": bool(
            metrics.get("model_output_valid_json", True)
        ),
        "model_device": str(metrics.get("model_device", "")),
    }


def _aggregate_stage2(review_rows: list[dict]) -> dict:
    call_rows = [row["call_metrics"] for row in review_rows]
    generated = sum(int(row["generated_tokens"]) for row in call_rows)
    model_ms = sum(float(row["model_inference_ms"]) for row in call_rows)
    return {
        "review_call_count": len(review_rows),
        "prompt_build_ms": sum(float(row["prompt_build_ms"]) for row in review_rows),
        "prompt_tokens": sum(int(row["prompt_tokens"]) for row in call_rows),
        "generated_tokens": generated,
        "input_preparation_ms": sum(
            float(row["input_preparation_ms"]) for row in call_rows
        ),
        "model_inference_ms": model_ms,
        "total_inference_ms": sum(float(row["total_inference_ms"]) for row in call_rows),
        "call_wall_ms": sum(float(row["call_wall_ms"]) for row in call_rows),
        "tokens_per_second": generated / (model_ms / 1000.0) if model_ms else 0.0,
        "cuda_peak_memory_bytes": max(
            (int(row["cuda_peak_memory_bytes"]) for row in call_rows), default=0
        ),
        "cuda_allocated_memory_bytes": max(
            (int(row["cuda_allocated_memory_bytes"]) for row in call_rows),
            default=0,
        ),
        "all_outputs_valid_json": all(
            bool(row["model_output_valid_json"]) for row in call_rows
        ),
        "sources": [str(row["source"]) for row in call_rows],
    }


def _repeat_latency_breakdown(
    *,
    archived_retrieval_ms: float,
    stage1: dict,
    stage2: dict,
    render_ms: float,
) -> dict:
    prompt_build = float(stage1["prompt_build_ms"]) + float(
        stage2["prompt_build_ms"]
    )
    input_preparation = float(stage1["input_preparation_ms"]) + float(
        stage2["input_preparation_ms"]
    )
    model_inference = float(stage1["model_inference_ms"]) + float(
        stage2["model_inference_ms"]
    )
    generation_pipeline = (
        prompt_build + input_preparation + model_inference + float(render_ms)
    )
    return {
        "retrieval_ms": None,
        "archived_retrieval_elapsed_ms": float(archived_retrieval_ms),
        "prompt_build_ms": prompt_build,
        "stage1_ms": float(stage1["total_inference_ms"]),
        "stage1_model_ms": float(stage1["model_inference_ms"]),
        "stage2_ms": float(stage2["total_inference_ms"]),
        "stage2_review_ms": float(stage2["total_inference_ms"]),
        "input_preparation_ms": input_preparation,
        "model_inference_ms": model_inference,
        "render_ms": float(render_ms),
        "generation_pipeline_ms": generation_pipeline,
        "total_ms": None,
        "end_to_end_inference_ms": None,
    }


def _median_measurement_summary(runs: list[dict]) -> tuple[dict, dict]:
    latency_keys = (
        "archived_retrieval_elapsed_ms",
        "prompt_build_ms",
        "stage1_ms",
        "stage1_model_ms",
        "stage2_ms",
        "stage2_review_ms",
        "input_preparation_ms",
        "model_inference_ms",
        "render_ms",
        "generation_pipeline_ms",
    )
    latency = {
        key: _median(run["latency_breakdown_ms"][key] for run in runs)
        for key in latency_keys
    }
    latency.update(
        {
            "retrieval_ms": None,
            "total_ms": None,
            "end_to_end_inference_ms": None,
        }
    )
    prompt_tokens = _median(
        run["stage1"]["prompt_tokens"] + run["stage2"]["prompt_tokens"]
        for run in runs
    )
    generated_tokens = _median(
        run["stage1"]["generated_tokens"] + run["stage2"]["generated_tokens"]
        for run in runs
    )
    call_count = _median(run["model_call_count"] for run in runs)
    model_metrics = {
        "prompt_tokens": int(round(prompt_tokens)),
        "generated_tokens": int(round(generated_tokens)),
        "input_preparation_ms": latency["input_preparation_ms"],
        "elapsed_ms": latency["model_inference_ms"],
        "tokens_per_second": (
            generated_tokens / (latency["model_inference_ms"] / 1000.0)
            if latency["model_inference_ms"]
            else 0.0
        ),
        "cascade_model_call_count": int(round(call_count)),
        "stage1_prompt_tokens": int(
            round(_median(run["stage1"]["prompt_tokens"] for run in runs))
        ),
        "stage1_generated_tokens": int(
            round(_median(run["stage1"]["generated_tokens"] for run in runs))
        ),
        "stage2_prompt_tokens": int(
            round(_median(run["stage2"]["prompt_tokens"] for run in runs))
        ),
        "stage2_generated_tokens": int(
            round(_median(run["stage2"]["generated_tokens"] for run in runs))
        ),
        "stage2_review_call_count": int(
            round(_median(run["stage2"]["review_call_count"] for run in runs))
        ),
        "cuda_peak_memory_bytes": max(
            max(
                int(run["stage1"]["cuda_peak_memory_bytes"]),
                int(run["stage2"]["cuda_peak_memory_bytes"]),
            )
            for run in runs
        ),
        "cuda_allocated_memory_bytes": max(
            max(
                int(run["stage1"]["cuda_allocated_memory_bytes"]),
                int(run["stage2"]["cuda_allocated_memory_bytes"]),
            )
            for run in runs
        ),
        "model_output_valid_json": all(
            bool(run["stage1"]["model_output_valid_json"])
            and bool(run["stage2"]["all_outputs_valid_json"])
            for run in runs
        ),
        "interleaved_measurement_repeats": len(runs),
        "quality_fusion": "none",
        "latency_aggregation": "per_query_median_of_independent_measurement_repeats",
    }
    return latency, model_metrics


def _canonical_run(runs: list[dict], repeat: int = CANONICAL_QUALITY_REPEAT) -> dict:
    matched = [run for run in runs if int(run["repeat"]) == repeat]
    if len(matched) != 1:
        raise RuntimeError(
            f"Expected exactly one canonical quality run for repeat={repeat}, got {len(matched)}"
        )
    return matched[0]


def _frozen_paths(config: dict) -> list[Path]:
    raw = config["frozen_retrieval_results"]
    values = [raw] if isinstance(raw, str) else list(raw)
    if not values:
        raise ValueError("frozen_retrieval_results must not be empty")
    return [ROOT / str(value) for value in values]


def _read_frozen(paths: list[Path]) -> dict[tuple[str, str], RetrievalResult]:
    frozen: dict[tuple[str, str], RetrievalResult] = {}
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Frozen retrieval missing: {path}")
        for row in _read_jsonl(path):
            result = _retrieval_result(row)
            key = (result.method, result.query_id)
            if key in frozen:
                raise RuntimeError(f"Duplicate frozen retrieval row: {key}")
            frozen[key] = result
    return frozen


def _scenario_specs(config: dict, requested: list[str]) -> list[dict]:
    scenarios = [dict(row) for row in config["scenarios"]]
    if requested:
        allowed = {
            value.strip()
            for token in requested
            for value in token.split(",")
            if value.strip()
        }
        scenarios = [
            row
            for row in scenarios
            if str(row["id"]) in allowed
            or str(row.get("retrieval_method", "")) in allowed
        ]
    if not scenarios:
        raise ValueError("No v6 scenarios matched --methods")
    configured_ids = [str(row["id"]) for row in scenarios]
    known = [method for method in DEFAULT_METHOD_ORDER if method in configured_ids]
    unknown = [method for method in configured_ids if method not in DEFAULT_METHOD_ORDER]
    order = known + unknown
    by_id = {str(row["id"]): row for row in scenarios}
    return [by_id[method] for method in order]


def _verification_mode(scenario: dict) -> str:
    mode = str(scenario.get("verification_mode", "stage1_plus_review"))
    if mode not in VERIFICATION_MODES:
        raise ValueError(
            f"Unknown verification_mode={mode!r}; expected one of "
            f"{sorted(VERIFICATION_MODES)}"
        )
    return mode


def _warm_up(
    generator: QwenLocalGenerator,
    *,
    count: int,
    max_new_tokens: int,
) -> list[dict]:
    if count < 0:
        raise ValueError("warmup_runs must be non-negative")
    rows = []
    system_prompt = system_prompt_for_strategy("evidence_mask_v3")
    user_prompt = json.dumps(
        {
            "question": "GPU warm-up only",
            "required_role": "symptom",
            "candidates": [],
            "output": {"direct": []},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    for index in range(count):
        started = time.perf_counter_ns()
        answer = generator.generate_json(
            system_prompt, user_prompt, max_new_tokens=max_new_tokens
        )
        wall_ms = (time.perf_counter_ns() - started) / 1_000_000
        rows.append(
            {
                "warmup": index,
                "answer": answer,
                "metrics": _call_metric_record(
                    dict(generator.last_metrics), source="MODEL", call_wall_ms=wall_ms
                ),
            }
        )
        print(f"[RP2 v6] warm-up {index + 1}/{count} completed", flush=True)
    return rows


def _run_measurement(
    *,
    repeat: int,
    method_order: list[str],
    scenario: dict,
    query,
    retrieval: RetrievalResult,
    evidence: list,
    generator: QwenLocalGenerator,
    contract: dict,
    stage1_system: str,
    stage1_max_new_tokens: int,
    review_max_new_tokens: int,
    cache_dir: Path,
    model_identity: str,
    protocol_version: str,
    protocol_fingerprint: str,
    force_generation: bool,
) -> dict:
    execution_started = time.perf_counter_ns()
    verification_mode = _verification_mode(scenario)
    if verification_mode == "direct_render":
        prompt = ""
        planned_tokens = 0
        prompt_build_ms = 0.0
        first_payload = {"direct": [1] * len(evidence)}
        stage1_call = _call_metric_record(
            {}, source="NO_CALL", call_wall_ms=0.0
        )
    else:
        prompt_started = time.perf_counter_ns()
        prompt, kept, dropped, planned_tokens = fit_prompt_budget(
            query,
            evidence,
            generator,
            contract,
            strategy="evidence_mask_v3",
            system_prompt=stage1_system,
        )
        prompt_build_ms = (time.perf_counter_ns() - prompt_started) / 1_000_000
        if dropped or len(kept) != len(evidence):
            raise RuntimeError(
                "v6 equal-budget protocol forbids changing the frozen candidate list"
            )

    if verification_mode != "direct_render" and evidence:
        first_payload, metrics, source, call_wall_ms = _call_cached(
            generator,
            system_prompt=stage1_system,
            user_prompt=prompt,
            max_new_tokens=stage1_max_new_tokens,
            cache_dir=cache_dir,
            cache_payload={
                "protocol": protocol_version,
                "fingerprint": protocol_fingerprint,
                "stage": "precision_mask",
                "verification_mode": verification_mode,
                "measurement_repeat": repeat,
                "scenario": str(scenario["id"]),
                "query_id": query.query_id,
                "prompt": prompt,
                "model": model_identity,
            },
            force=force_generation,
        )
        stage1_call = _call_metric_record(
            metrics, source=source, call_wall_ms=call_wall_ms
        )
    elif verification_mode != "direct_render":
        first_payload = {"direct": []}
        stage1_call = _call_metric_record({}, source="NO_CALL", call_wall_ms=0.0)
    stage1 = dict(stage1_call, prompt_build_ms=prompt_build_ms)
    _, first_audit = expand_compact_evidence_mask(first_payload, evidence)
    first_mask = first_audit.get("normalized_mask")
    first_valid = bool(first_audit["mask_contract_valid"])
    if first_mask is None:
        first_mask = [0] * len(evidence)
    final_mask = list(first_mask)

    reviews = []
    for index, (item, selected) in enumerate(zip(evidence, first_mask)):
        if selected or verification_mode != "stage1_plus_review":
            continue
        review_prompt_started = time.perf_counter_ns()
        review_prompt = build_recall_review_prompt(query, item)
        review_prompt_ms = (
            time.perf_counter_ns() - review_prompt_started
        ) / 1_000_000
        payload, metrics, source, call_wall_ms = _call_cached(
            generator,
            system_prompt=RECALL_REVIEW_SYSTEM_PROMPT,
            user_prompt=review_prompt,
            max_new_tokens=review_max_new_tokens,
            cache_dir=cache_dir,
            cache_payload={
                "protocol": protocol_version,
                "fingerprint": protocol_fingerprint,
                "stage": "recall_review",
                "verification_mode": verification_mode,
                "measurement_repeat": repeat,
                "scenario": str(scenario["id"]),
                "query_id": query.query_id,
                "candidate_index": index,
                "prompt": review_prompt,
                "model": model_identity,
            },
            force=force_generation,
        )
        decision, audit = parse_single_recall_review(payload)
        final_mask[index] = decision if audit["contract_valid"] else 0
        reviews.append(
            {
                "candidate_index": index,
                "evidence_id": item.evidence_id,
                "payload": payload,
                "audit": audit,
                "prompt_build_ms": review_prompt_ms,
                "call_metrics": _call_metric_record(
                    metrics, source=source, call_wall_ms=call_wall_ms
                ),
            }
        )
    stage2 = _aggregate_stage2(reviews)
    cascade_valid = first_valid and all(
        row["audit"]["contract_valid"] for row in reviews
    )

    render_started = time.perf_counter_ns()
    expanded, mask_audit = expand_compact_evidence_mask(
        {"direct": final_mask}, evidence
    )
    answer, guard_audit = apply_evidence_coverage_guard(
        expanded,
        query,
        evidence,
        contract,
        minimum_fault_affinity=float(
            scenario.get("minimum_visible_fault_affinity", 0.0)
        ),
    )
    render_ms = (time.perf_counter_ns() - render_started) / 1_000_000
    latency = _repeat_latency_breakdown(
        archived_retrieval_ms=retrieval.elapsed_ms,
        stage1=stage1,
        stage2=stage2,
        render_ms=render_ms,
    )
    return {
        "protocol_fingerprint": protocol_fingerprint,
        "repeat": repeat,
        "method": str(scenario["id"]),
        "query_id": query.query_id,
        "verification_mode": verification_mode,
        "method_order": method_order,
        "first_payload": first_payload,
        "first_mask": first_mask,
        "first_audit": first_audit,
        "review_rows": reviews,
        "final_mask": final_mask,
        "cascade_contract_valid": cascade_valid,
        "expanded_model_answer": expanded,
        "compact_mask_audit": mask_audit,
        "answer": answer,
        "faithfulness_guard": guard_audit,
        "planned_prompt_tokens": planned_tokens,
        "stage1": stage1,
        "stage2": stage2,
        "render_ms": render_ms,
        "latency_breakdown_ms": latency,
        "model_call_count": (
            int(bool(evidence) and verification_mode != "direct_render")
            + len(reviews)
        ),
        "execution_wall_ms": (
            time.perf_counter_ns() - execution_started
        ) / 1_000_000,
        "source": (
            "MODEL"
            if stage1["source"] == "MODEL"
            or "MODEL" in stage2["sources"]
            else "CACHE"
            if stage1["source"] == "CACHE"
            or "CACHE" in stage2["sources"]
            else "NO_CALL"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", default="configs/rp2_graphrag_v6_equal_budget.json"
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--methods", nargs="*", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-generation", action="store_true")
    parser.add_argument("--require-cuda", action="store_true")
    parser.add_argument(
        "--resume", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--warmup-runs", type=int)
    args = parser.parse_args()

    config_path = ROOT / args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    benchmark = ROOT / config["benchmark_dir"]
    generator_path = ROOT / config["generator"]["model_path"]
    output = ROOT / config["output_dir"]
    cache_dir = ROOT / config["generator"]["cache_dir"]
    scenarios = _scenario_specs(config, args.methods)
    repeats = int(config["cascade"].get("interleaved_repeats", 3))
    if repeats < 1:
        raise ValueError("interleaved_repeats must be at least one")
    warmup_runs = (
        int(args.warmup_runs)
        if args.warmup_runs is not None
        else int(config["generator"].get("warmup_runs", 1))
    )
    frozen_paths = _frozen_paths(config)
    frozen = _read_frozen(frozen_paths)
    candidates = [
        _candidate(row)
        for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")
    ]
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    if args.limit:
        queries = queries[: args.limit]
    if any(query.candidate_evidence_ids for query in queries):
        raise RuntimeError("Positive-seeded candidate pools are forbidden")
    for scenario in scenarios:
        source_method = str(
            scenario.get("source_retrieval_method", scenario["id"])
        )
        for query in queries:
            key = (source_method, query.query_id)
            if key not in frozen:
                raise RuntimeError(f"Frozen retrieval row missing: {key}")
            maximum = int(scenario["max_selected_evidence"])
            if len(frozen[key].ranked) > maximum:
                raise RuntimeError(
                    f"Frozen retrieval exceeds scenario budget {maximum}: {key}"
                )

    print(
        f"[RP2 v6] queries={len(queries)}, methods={len(scenarios)}, "
        f"measurement_repeats={repeats}, canonical_quality_repeat=0, "
        "quality_fusion=NONE, retrieval=FROZEN",
        flush=True,
    )
    if args.dry_run:
        print(
            f"[RP2 v6] frozen_files={len(frozen_paths)}, "
            f"Qwen={generator_path.is_dir()}, tasks={len(queries)*len(scenarios)*repeats}, "
            f"warmup_runs={warmup_runs}, resume={args.resume}",
            flush=True,
        )
        return 0
    if not generator_path.is_dir():
        raise FileNotFoundError(f"Qwen model missing: {generator_path}")

    require_cuda = bool(
        args.require_cuda or config.get("runtime", {}).get("require_cuda")
    )
    generator = QwenLocalGenerator(
        generator_path,
        device_map=config["generator"]["device_map"],
        dtype=config["generator"]["dtype"],
        require_cuda=require_cuda,
    )
    model_manifest = model_file_manifest(generator_path)
    model_identity = model_manifest["structure_sha256"]
    frozen_manifest = [
        {
            "path": str(path.relative_to(ROOT)),
            "sha256": _sha256(path),
        }
        for path in frozen_paths
    ]
    protocol_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "config": config,
                "model": model_identity,
                "frozen": frozen_manifest,
                "selected_methods": [str(row["id"]) for row in scenarios],
                "limit": args.limit,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output / "measurement_checkpoints.jsonl"
    checkpoints = (
        _load_checkpoints(checkpoint_path, protocol_fingerprint)
        if args.resume and not args.force_generation
        else {}
    )
    if not checkpoints:
        _atomic_write_jsonl(checkpoint_path, [])

    warmups = _warm_up(
        generator,
        count=warmup_runs,
        max_new_tokens=int(config["generator"].get("stage1_max_new_tokens", 64)),
    )
    by_id = {row.evidence_id: row for row in candidates}
    contract = {
        "max_prompt_tokens": int(config["generation_contract"]["max_prompt_tokens"]),
        "max_answer_points": int(config["generation_contract"]["max_answer_points"]),
        "max_point_chars": int(config["generation_contract"]["max_point_chars"]),
        "max_summary_chars": int(config["generation_contract"]["max_summary_chars"]),
    }
    stage1_system = system_prompt_for_strategy("evidence_mask_v3")
    total = len(queries) * len(scenarios) * repeats
    completed = len(checkpoints)
    resumed_count = completed
    process_completed = 0
    started = time.perf_counter()
    if completed:
        print(f"[RP2 v6] resume: reused {completed}/{total} measurements", flush=True)

    for repeat in range(repeats):
        for query_index, query in enumerate(queries):
            order = _rotated(scenarios, query_index + repeat)
            method_order = [str(row["id"]) for row in order]
            for scenario in order:
                scenario_id = str(scenario["id"])
                checkpoint_key = (repeat, scenario_id, query.query_id)
                if checkpoint_key in checkpoints:
                    continue
                task_started = time.perf_counter()
                source_method = str(
                    scenario.get("source_retrieval_method", scenario_id)
                )
                retrieval = frozen[(source_method, query.query_id)]
                missing = [
                    row.evidence_id
                    for row in retrieval.ranked
                    if row.evidence_id not in by_id
                ]
                if missing:
                    raise RuntimeError(
                        f"Frozen retrieval references unknown evidence: {missing}"
                    )
                evidence = [by_id[row.evidence_id] for row in retrieval.ranked]
                row = _run_measurement(
                    repeat=repeat,
                    method_order=method_order,
                    scenario=scenario,
                    query=query,
                    retrieval=retrieval,
                    evidence=evidence,
                    generator=generator,
                    contract=contract,
                    stage1_system=stage1_system,
                    stage1_max_new_tokens=int(
                        config["generator"].get("stage1_max_new_tokens", 64)
                    ),
                    review_max_new_tokens=int(
                        config["generator"].get("review_max_new_tokens", 48)
                    ),
                    cache_dir=cache_dir,
                    model_identity=model_identity,
                    protocol_version=str(config["version"]),
                    protocol_fingerprint=protocol_fingerprint,
                    force_generation=args.force_generation,
                )
                checkpoints[checkpoint_key] = row
                _atomic_write_jsonl(
                    checkpoint_path,
                    [checkpoints[key] for key in sorted(checkpoints)],
                )
                completed += 1
                process_completed += 1
                elapsed = time.perf_counter() - started
                remaining = total - completed
                # Resume rows do not contribute to this process' ETA denominator.
                eta = elapsed / max(1, process_completed) * remaining / 60.0
                print(
                    f"[RP2 v6][{completed}/{total}] r{repeat+1} "
                    f"{scenario_id}:{query.query_id} candidates={len(evidence)}, "
                    f"reviews={row['stage2']['review_call_count']}, "
                    f"direct={sum(row['final_mask'])}, "
                    f"elapsed={time.perf_counter()-task_started:.2f}s, ETA={eta:.1f}m",
                    flush=True,
                )

    results: list[RetrievalResult] = []
    generations: list[dict] = []
    for scenario in scenarios:
        scenario_id = str(scenario["id"])
        source_method = str(
            scenario.get("source_retrieval_method", scenario_id)
        )
        for query in queries:
            retrieval = frozen[(source_method, query.query_id)]
            evidence = [by_id[row.evidence_id] for row in retrieval.ranked]
            runs = [
                checkpoints[(repeat, scenario_id, query.query_id)]
                for repeat in range(repeats)
            ]
            canonical = _canonical_run(runs)
            answer = canonical["answer"]
            expanded = canonical["expanded_model_answer"]
            validation = validate_generated_answer(
                answer,
                {row.evidence_id for row in evidence},
                max_answer_points=contract["max_answer_points"],
                max_point_chars=contract["max_point_chars"],
                max_summary_chars=contract["max_summary_chars"],
            )
            assessment_valid = validate_candidate_assessment_contract(
                expanded, {row.evidence_id for row in evidence}
            ) and bool(canonical["cascade_contract_valid"])
            validation["candidate_assessment_contract_valid"] = assessment_valid
            validation["contract_valid"] = bool(
                validation["contract_valid"] and assessment_valid
            )
            cited = {
                str(evidence_id)
                for point in answer.get("answer_points", [])
                for evidence_id in point.get("evidence_ids", [])
            }
            relevant = set(query.relevant_evidence_ids)
            latency, model_metrics = _median_measurement_summary(runs)
            result = replace(retrieval, method=scenario_id)
            results.append(result)
            generations.append(
                {
                    "query_id": query.query_id,
                    "method": scenario_id,
                    "retrieval_method": scenario.get("retrieval_method", "frozen_replay"),
                    "source_retrieval_method": source_method,
                    "scenario": scenario,
                    "verification_mode": canonical["verification_mode"],
                    "answer": answer,
                    "raw_model_answer": expanded,
                    "generation_strategy": (
                        "single_run_"
                        f"{canonical['verification_mode']}_deterministic_render_v6"
                    ),
                    "faithfulness_guard": canonical["faithfulness_guard"],
                    "compact_mask_audit": canonical["compact_mask_audit"],
                    "canonical_quality_repeat": CANONICAL_QUALITY_REPEAT,
                    "quality_fusion": "none",
                    "measurement_repeats": runs,
                    "validation": validation,
                    "relevant_citation_recall": (
                        len(cited & relevant) / len(relevant) if relevant else None
                    ),
                    "silver_evaluation": score_silver_response(
                        answer, validation, relevant
                    ),
                    "planned_prompt_tokens": int(canonical["planned_prompt_tokens"]),
                    "prompt_budget_dropped_evidence": 0,
                    "archived_retrieval_elapsed_ms": result.elapsed_ms,
                    "formal_retrieval_elapsed_ms": None,
                    "latency_breakdown_ms": latency,
                    "generation_request_wall_ms": _median(
                        run["execution_wall_ms"] for run in runs
                    ),
                    "generation_model_elapsed_ms": model_metrics["elapsed_ms"],
                    "generation_pipeline_elapsed_ms": latency[
                        "generation_pipeline_ms"
                    ],
                    "model_metrics": model_metrics,
                    "source": (
                        "MODEL"
                        if any(run["source"] == "MODEL" for run in runs)
                        else "CACHE"
                        if any(run["source"] == "CACHE" for run in runs)
                        else "NO_CALL"
                    ),
                }
            )

    metrics = evaluate_results(queries, candidates, results)
    query_by_id = {query.query_id: query for query in queries}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in generations:
        grouped[row["method"]].append(row)
    metrics["generation"] = summarize_generation_rows(generations, query_by_id)
    metrics["generation"]["by_method"] = {
        method: summarize_generation_rows(rows, query_by_id)
        for method, rows in grouped.items()
    }
    metrics["generation"]["by_method_and_role"] = {
        method: {
            role: summarize_generation_rows(
                [row for row in rows if query_by_id[row["query_id"]].role == role],
                query_by_id,
            )
            for role in sorted(
                {query_by_id[row["query_id"]].role for row in rows}
            )
        }
        for method, rows in grouped.items()
    }
    metrics["generation"]["latency_scope"] = (
        "per-query median of independent rotating-interleaved measurement repeats; "
        "generation pipeline only until joined with the fresh v6 retrieval-latency "
        "artifact; archived v3/v4 retrieval elapsed_ms is audit-only; model loading "
        "and explicit warm-up are excluded"
    )
    metrics["run_manifest"] = {
        "protocol_id": config["protocol_id"],
        "protocol_version": config["version"],
        "protocol_fingerprint": protocol_fingerprint,
        "config_path": str(config_path.relative_to(ROOT)),
        "config_file_sha256": _sha256(config_path),
        "generator_model": model_manifest,
        "generator_runtime": generator.runtime_manifest,
        "frozen_retrieval_results": frozen_manifest,
        "retrieval_replay": True,
        "archived_retrieval_timing_formal_v6_eligible": False,
        "formal_end_to_end_latency_status": (
            "pending_join_with_fresh_retrieval_latency_artifact"
        ),
        "query_count": len(queries),
        "candidate_count": len(candidates),
        "scenarios": scenarios,
        "generation_contract": contract,
        "cascade": config["cascade"],
        "warmup_runs_requested": warmup_runs,
        "warmup_runs_completed": len(warmups),
        "warmup_metrics": warmups,
        "interleaved_schedule": "rotate method order by query_index + measurement_repeat",
        "measurement_repeats": repeats,
        "canonical_quality_repeat": CANONICAL_QUALITY_REPEAT,
        "quality_decision_policy": "repeat_zero_only_no_vote_no_fusion",
        "timing_repeat_policy": "repeats_one_and_later_are_measurement_only",
        "cuda_synchronization_policy": (
            "QwenLocalGenerator synchronizes CUDA before and after model.generate"
        ),
        "online_forbidden_fields": ["fault_class_ids", "relevant_evidence_ids"],
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
        "resume_enabled": bool(args.resume),
        "measurements_resumed_from_checkpoint": resumed_count,
        "force_generation": bool(args.force_generation),
    }
    effectiveness = {}
    for test in config.get("effectiveness_tests", []):
        effectiveness[str(test["id"])] = analyze_budget_effectiveness(
            generations,
            reference_id=str(test["reference_id"]),
            proposed_ids=[str(value) for value in test["proposed_ids"]],
            latency_noninferiority_margin=float(
                test.get("latency_noninferiority_margin", 0.05)
            ),
            minimum_quality_gain=float(test.get("minimum_quality_gain", 0.0)),
            bootstrap_iterations=int(test.get("bootstrap_iterations", 5000)),
            seed=int(test.get("seed", 20260820)),
        )
    metrics["budget_effectiveness"] = effectiveness
    _atomic_write_json(output / "metrics.json", metrics)
    _atomic_write_jsonl(
        output / "retrieval_results.jsonl", [row.to_dict() for row in results]
    )
    _atomic_write_jsonl(output / "generation_results.jsonl", generations)
    _plot_metrics(metrics, output)
    print(
        f"[RP2 v6] completed: {output}; quality=repeat0 only; "
        "measurement repetitions were not fused",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
