#!/usr/bin/env python3
"""Run interleaved repeated RP2 compact-mask + single-candidate recall review."""

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
from research_point_2.local_models import QwenLocalGenerator, model_file_manifest  # noqa: E402
from research_point_2.retrieval import RetrievalResult  # noqa: E402
from scripts.run_rp2_graphrag_v2 import (  # noqa: E402
    _candidate,
    _plot_metrics,
    _query,
    _retrieval_result,
    _sha256,
)


def _median(rows: list[float]) -> float:
    return float(statistics.median(rows)) if rows else 0.0


def _rotated(rows: list[dict], offset: int) -> list[dict]:
    if not rows:
        return []
    offset %= len(rows)
    return rows[offset:] + rows[:offset]


def _call_cached(
    generator: QwenLocalGenerator,
    *,
    system_prompt: str,
    user_prompt: str,
    max_new_tokens: int,
    cache_dir: Path,
    cache_payload: dict,
    force: bool,
) -> tuple[dict, dict, str]:
    key = hashlib.sha256(
        json.dumps(cache_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    path = cache_dir / f"{key}.json"
    if path.is_file() and not force:
        cached = json.loads(path.read_text(encoding="utf-8"))
        return cached["answer"], cached.get("generation_metrics", {}), "CACHE"
    answer = generator.generate_json(
        system_prompt, user_prompt, max_new_tokens=max_new_tokens
    )
    metrics = dict(generator.last_metrics)
    path.write_text(
        json.dumps(
            {"answer": answer, "generation_metrics": metrics},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return answer, metrics, "MODEL"


def _aggregate_call_metrics(call_metrics: list[dict]) -> dict:
    elapsed = sum(float(row.get("elapsed_ms", 0.0)) for row in call_metrics)
    generated = sum(int(row.get("generated_tokens", 0)) for row in call_metrics)
    return {
        "prompt_tokens": sum(int(row.get("prompt_tokens", 0)) for row in call_metrics),
        "generated_tokens": generated,
        "input_preparation_ms": sum(
            float(row.get("input_preparation_ms", 0.0)) for row in call_metrics
        ),
        "elapsed_ms": elapsed,
        "tokens_per_second": generated / (elapsed / 1000.0) if elapsed else 0.0,
        "cuda_peak_memory_bytes": max(
            (int(row.get("cuda_peak_memory_bytes", 0)) for row in call_metrics),
            default=0,
        ),
        "cuda_allocated_memory_bytes": max(
            (int(row.get("cuda_allocated_memory_bytes", 0)) for row in call_metrics),
            default=0,
        ),
        "model_output_valid_json": all(
            bool(row.get("model_output_valid_json", True)) for row in call_metrics
        ),
        "cascade_model_call_count": len(call_metrics),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", default="configs/rp2_graphrag_v5_2_recall_cascade.json"
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-generation", action="store_true")
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()

    config = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    benchmark = ROOT / config["benchmark_dir"]
    generator_path = ROOT / config["generator"]["model_path"]
    frozen_path = ROOT / config["frozen_retrieval_results"]
    output = ROOT / config["output_dir"]
    cache_dir = ROOT / config["generator"]["cache_dir"]
    scenarios = [dict(row) for row in config["scenarios"]]
    repeats = int(config["cascade"]["interleaved_repeats"])
    candidates = [_candidate(row) for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")]
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    if args.limit:
        queries = queries[: args.limit]
    if any(query.candidate_evidence_ids for query in queries):
        raise RuntimeError("Positive-seeded candidate pools are forbidden")
    frozen: dict[tuple[str, str], RetrievalResult] = {}
    for row in _read_jsonl(frozen_path):
        result = _retrieval_result(row)
        frozen[(result.method, result.query_id)] = result
    print(
        f"[RP2 v5.2] queries={len(queries)}, methods={len(scenarios)}, "
        f"repeats={repeats}, schedule=rotating_interleaved, retrieval=FROZEN",
        flush=True,
    )
    if args.dry_run:
        print(
            f"[RP2 v5.2] frozen={frozen_path.is_file()}, "
            f"Qwen={generator_path.is_dir()}, tasks={len(queries)*len(scenarios)*repeats}",
            flush=True,
        )
        return 0
    if not frozen_path.is_file():
        raise FileNotFoundError(f"Frozen retrieval missing: {frozen_path}")
    if not generator_path.is_dir():
        raise FileNotFoundError(f"Qwen model missing: {generator_path}")

    require_cuda = bool(args.require_cuda or config.get("runtime", {}).get("require_cuda"))
    generator = QwenLocalGenerator(
        generator_path,
        device_map=config["generator"]["device_map"],
        dtype=config["generator"]["dtype"],
        require_cuda=require_cuda,
    )
    identity = model_file_manifest(generator_path)["structure_sha256"]
    output.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    by_id = {row.evidence_id: row for row in candidates}
    contract = {
        "max_prompt_tokens": int(config["generation_contract"]["max_prompt_tokens"]),
        "max_answer_points": int(config["generation_contract"]["max_answer_points"]),
        "max_point_chars": int(config["generation_contract"]["max_point_chars"]),
        "max_summary_chars": int(config["generation_contract"]["max_summary_chars"]),
    }
    stage1_system = system_prompt_for_strategy("evidence_mask_v3")
    repeat_rows: dict[tuple[str, str], list[dict]] = defaultdict(list)
    total = len(queries) * len(scenarios) * repeats
    completed = 0
    run_started = time.perf_counter()

    for repeat in range(repeats):
        for query_index, query in enumerate(queries):
            order = _rotated(scenarios, query_index + repeat)
            for scenario in order:
                task_started = time.perf_counter()
                scenario_id = str(scenario["id"])
                source_method = str(scenario["source_retrieval_method"])
                key = (source_method, query.query_id)
                if key not in frozen:
                    raise RuntimeError(f"Frozen retrieval row missing: {key}")
                retrieval = frozen[key]
                missing = [row.evidence_id for row in retrieval.ranked if row.evidence_id not in by_id]
                if missing:
                    raise RuntimeError(f"Frozen retrieval references unknown evidence: {missing}")
                evidence = [by_id[row.evidence_id] for row in retrieval.ranked]
                prompt, kept, dropped, planned_tokens = fit_prompt_budget(
                    query,
                    evidence,
                    generator,
                    contract,
                    strategy="evidence_mask_v3",
                    system_prompt=stage1_system,
                )
                if dropped or len(kept) != len(evidence):
                    raise RuntimeError("v5.2 forbids changing the frozen candidate list")

                call_metrics: list[dict] = []
                call_sources: list[str] = []
                if evidence:
                    first_payload, first_metrics, first_source = _call_cached(
                        generator,
                        system_prompt=stage1_system,
                        user_prompt=prompt,
                        max_new_tokens=int(config["generator"]["stage1_max_new_tokens"]),
                        cache_dir=cache_dir,
                        cache_payload={
                            "protocol": config["version"],
                            "stage": "precision_mask",
                            "repeat": repeat,
                            "scenario": scenario_id,
                            "query_id": query.query_id,
                            "prompt": prompt,
                            "model": identity,
                        },
                        force=args.force_generation,
                    )
                    call_metrics.append(first_metrics)
                    call_sources.append(first_source)
                else:
                    first_payload = {"direct": []}
                _, first_audit = expand_compact_evidence_mask(
                    first_payload, evidence
                )
                first_mask = first_audit.get("normalized_mask")
                first_valid = bool(first_audit["mask_contract_valid"])
                if first_mask is None:
                    first_mask = [0] * len(evidence)
                final_mask = list(first_mask)
                reviews = []
                for index, (item, selected) in enumerate(zip(evidence, first_mask)):
                    if selected:
                        continue
                    review_prompt = build_recall_review_prompt(query, item)
                    payload, metrics, source = _call_cached(
                        generator,
                        system_prompt=RECALL_REVIEW_SYSTEM_PROMPT,
                        user_prompt=review_prompt,
                        max_new_tokens=int(config["generator"]["review_max_new_tokens"]),
                        cache_dir=cache_dir,
                        cache_payload={
                            "protocol": config["version"],
                            "stage": "recall_review",
                            "repeat": repeat,
                            "scenario": scenario_id,
                            "query_id": query.query_id,
                            "candidate_index": index,
                            "prompt": review_prompt,
                            "model": identity,
                        },
                        force=args.force_generation,
                    )
                    decision, audit = parse_single_recall_review(payload)
                    final_mask[index] = decision if audit["contract_valid"] else 0
                    call_metrics.append(metrics)
                    call_sources.append(source)
                    reviews.append({
                        "candidate_index": index,
                        "evidence_id": item.evidence_id,
                        "payload": payload,
                        "audit": audit,
                    })
                aggregate = _aggregate_call_metrics(call_metrics)
                cascade_valid = first_valid and all(
                    row["audit"]["contract_valid"] for row in reviews
                )
                repeat_rows[(scenario_id, query.query_id)].append({
                    "repeat": repeat,
                    "method_order": [str(row["id"]) for row in order],
                    "first_payload": first_payload,
                    "first_mask": first_mask,
                    "first_audit": first_audit,
                    "review_rows": reviews,
                    "final_mask": final_mask,
                    "cascade_contract_valid": cascade_valid,
                    "model_metrics": aggregate,
                    "request_wall_ms": (time.perf_counter() - task_started) * 1000,
                    "source": "MODEL" if "MODEL" in call_sources else "CACHE",
                    "planned_prompt_tokens": planned_tokens,
                })
                completed += 1
                eta = ((time.perf_counter() - run_started) / completed) * (total - completed) / 60
                print(
                    f"[RP2 v5.2][{completed}/{total}] r{repeat+1} "
                    f"{scenario_id}:{query.query_id} candidates={len(evidence)}, "
                    f"reviews={len(reviews)}, final_direct={sum(final_mask)}, "
                    f"elapsed={time.perf_counter()-task_started:.2f}s, ETA={eta:.1f}m",
                    flush=True,
                )

    results: list[RetrievalResult] = []
    generations: list[dict] = []
    for scenario in scenarios:
        scenario_id = str(scenario["id"])
        source_method = str(scenario["source_retrieval_method"])
        for query in queries:
            retrieval = frozen[(source_method, query.query_id)]
            evidence = [by_id[row.evidence_id] for row in retrieval.ranked]
            runs = repeat_rows[(scenario_id, query.query_id)]
            majority_threshold = repeats // 2 + 1
            first_majority = [
                int(sum(run["first_mask"][index] for run in runs) >= majority_threshold)
                for index in range(len(evidence))
            ]
            review_majority = [
                int(
                    sum(
                        run["final_mask"][index]
                        for run in runs
                        if not run["first_mask"][index]
                    )
                    >= majority_threshold
                )
                for index in range(len(evidence))
            ]
            majority = [
                int(first or review)
                for first, review in zip(first_majority, review_majority)
            ]
            expanded, mask_audit = expand_compact_evidence_mask(
                {"direct": majority}, evidence
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
            validation = validate_generated_answer(
                answer,
                {row.evidence_id for row in evidence},
                max_answer_points=contract["max_answer_points"],
                max_point_chars=contract["max_point_chars"],
                max_summary_chars=contract["max_summary_chars"],
            )
            assessment_valid = validate_candidate_assessment_contract(
                expanded, {row.evidence_id for row in evidence}
            ) and all(run["cascade_contract_valid"] for run in runs)
            validation["candidate_assessment_contract_valid"] = assessment_valid
            validation["contract_valid"] = bool(
                validation["contract_valid"] and assessment_valid
            )
            cited = {
                str(eid)
                for point in answer.get("answer_points", [])
                for eid in point.get("evidence_ids", [])
            }
            relevant = set(query.relevant_evidence_ids)
            model_metrics = {
                key: _median([float(run["model_metrics"].get(key, 0.0)) for run in runs])
                for key in (
                    "prompt_tokens",
                    "generated_tokens",
                    "input_preparation_ms",
                    "elapsed_ms",
                    "tokens_per_second",
                    "cascade_model_call_count",
                )
            }
            model_metrics.update({
                "prompt_tokens": int(round(model_metrics["prompt_tokens"])),
                "generated_tokens": int(round(model_metrics["generated_tokens"])),
                "cascade_model_call_count": int(round(model_metrics["cascade_model_call_count"])),
                "cuda_peak_memory_bytes": max(
                    int(run["model_metrics"].get("cuda_peak_memory_bytes", 0))
                    for run in runs
                ),
                "cuda_allocated_memory_bytes": max(
                    int(run["model_metrics"].get("cuda_allocated_memory_bytes", 0))
                    for run in runs
                ),
                "model_output_valid_json": all(
                    run["model_metrics"].get("model_output_valid_json", True)
                    for run in runs
                ),
                "interleaved_repeats": repeats,
                "latency_aggregation": "median_of_repeated_serial_stage1_plus_stage2_calls",
            })
            generation_wall = _median([run["request_wall_ms"] for run in runs])
            result = replace(retrieval, method=scenario_id)
            results.append(result)
            generations.append({
                "query_id": query.query_id,
                "method": scenario_id,
                "retrieval_method": scenario["retrieval_method"],
                "source_retrieval_method": source_method,
                "scenario": scenario,
                "answer": answer,
                "raw_model_answer": expanded,
                "generation_strategy": "precision_mask_plus_independent_recall_review_v1",
                "faithfulness_guard": guard_audit,
                "compact_mask_audit": mask_audit,
                "cascade_repeats": runs,
                "cascade_first_stage_majority": first_majority,
                "cascade_review_stage_majority": review_majority,
                "cascade_final_majority": majority,
                "cascade_promoted_candidate_count": sum(
                    final and not first
                    for first, final in zip(
                        first_majority,
                        majority,
                    )
                ),
                "validation": validation,
                "relevant_citation_recall": (
                    len(cited & relevant) / len(relevant) if relevant else None
                ),
                "silver_evaluation": score_silver_response(
                    answer, validation, relevant
                ),
                "planned_prompt_tokens": int(
                    round(_median([run["planned_prompt_tokens"] for run in runs]))
                ),
                "prompt_budget_dropped_evidence": 0,
                "retrieval_elapsed_ms": result.elapsed_ms,
                "generation_request_wall_ms": generation_wall,
                "generation_model_elapsed_ms": model_metrics["elapsed_ms"],
                "end_to_end_model_elapsed_ms": (
                    result.elapsed_ms + model_metrics["elapsed_ms"]
                ),
                "end_to_end_inference_elapsed_ms": (
                    result.elapsed_ms
                    + model_metrics["input_preparation_ms"]
                    + model_metrics["elapsed_ms"]
                    + float(guard_audit.get("elapsed_ms", 0.0))
                ),
                "model_metrics": model_metrics,
                "source": (
                    "MODEL" if any(run["source"] == "MODEL" for run in runs) else "CACHE"
                ),
            })

    metrics = evaluate_results(queries, candidates, results)
    query_by_id = {query.query_id: query for query in queries}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in generations:
        grouped[row["method"]].append(row)
    metrics["generation"] = summarize_generation_rows(generations, query_by_id)
    metrics["generation"]["by_method"] = {}
    for method, rows in grouped.items():
        summary = summarize_generation_rows(rows, query_by_id)
        promoted = sum(int(row["cascade_promoted_candidate_count"]) for row in rows)
        relevant_promoted = 0
        for row in rows:
            relevant = set(query_by_id[row["query_id"]].relevant_evidence_ids)
            evidence = [
                by_id[item.evidence_id]
                for item in next(
                    result for result in results
                    if result.method == method and result.query_id == row["query_id"]
                ).ranked
            ]
            relevant_promoted += sum(
                bool(final and not first and item.evidence_id in relevant)
                for first, final, item in zip(
                    row["cascade_first_stage_majority"],
                    row["cascade_final_majority"],
                    evidence,
                )
            )
        summary["cascade_promoted_candidate_count"] = promoted
        summary["cascade_silver_relevant_promoted_count"] = relevant_promoted
        summary["cascade_silver_promotion_precision"] = (
            relevant_promoted / promoted if promoted else None
        )
        metrics["generation"]["by_method"][method] = summary
    metrics["generation"]["by_method_and_role"] = {
        method: {
            role: summarize_generation_rows(
                [row for row in rows if query_by_id[row["query_id"]].role == role],
                query_by_id,
            )
            for role in sorted({query_by_id[row["query_id"]].role for row in rows})
        }
        for method, rows in grouped.items()
    }
    metrics["generation"]["latency_scope"] = (
        "median of interleaved repeated warm stage-1 plus serial independent stage-2 calls; "
        "frozen retrieval latency added; model loading excluded"
    )
    metrics["run_manifest"] = {
        "protocol_id": config["protocol_id"],
        "protocol_version": config["version"],
        "generator_model": model_file_manifest(generator_path),
        "frozen_retrieval_results": str(frozen_path.relative_to(ROOT)),
        "frozen_retrieval_file_sha256": _sha256(frozen_path),
        "retrieval_replay": True,
        "query_count": len(queries),
        "candidate_count": len(candidates),
        "scenarios": scenarios,
        "generation_contract": contract,
        "cascade": config["cascade"],
        "interleaved_schedule": "rotate method order by query_index + repeat",
        "online_forbidden_fields": ["fault_class_ids", "relevant_evidence_ids"],
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
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
            seed=int(test.get("seed", 20260812)),
        )
    metrics["budget_effectiveness"] = effectiveness
    (output / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "retrieval_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
    with (output / "generation_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in generations:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    _plot_metrics(metrics, output)
    print(f"[RP2 v5.2] completed: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
