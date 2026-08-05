#!/usr/bin/env python3
"""Run full-graph BGE-M3 retrieval and evidence-grounded Qwen2.5-7B generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.budget_effectiveness import analyze_budget_effectiveness  # noqa: E402
from research_point_2.dataset import EvidenceCandidate, SilverQuery, _read_jsonl  # noqa: E402
from research_point_2.dense_index import DenseEvidenceIndex  # noqa: E402
from research_point_2.evaluation import evaluate_results  # noqa: E402
from research_point_2.generation import (  # noqa: E402
    apply_evidence_coverage_guard,
    apply_faithfulness_guard,
    expand_compact_evidence_mask,
    fit_prompt_budget,
    score_silver_response,
    summarize_generation_rows,
    system_prompt_for_strategy,
    validate_candidate_assessment_contract,
    validate_generated_answer,
)
from research_point_2.graph_rag_v2 import retrieve_dense_graph  # noqa: E402
from research_point_2.local_models import BgeM3Encoder, QwenLocalGenerator, model_file_manifest  # noqa: E402
from research_point_2.retrieval import (  # noqa: E402
    RankedEvidence,
    RetrievalBudget,
    RetrievalIndex,
    RetrievalResult,
)


def _candidate(row: dict) -> EvidenceCandidate:
    row = dict(row)
    row["fault_class_ids"] = tuple(row.get("fault_class_ids", []))
    return EvidenceCandidate(**row)


def _query(row: dict) -> SilverQuery:
    row = dict(row)
    row["relevant_evidence_ids"] = tuple(row.get("relevant_evidence_ids", []))
    row["candidate_evidence_ids"] = tuple(row.get("candidate_evidence_ids", []))
    return SilverQuery(**row)


def _closed_book(query: SilverQuery) -> RetrievalResult:
    return RetrievalResult(query.query_id, "closed_book", (), 0.0, 0, 0, 0, 0, 0, "none", False, False)


def _retrieval_result(row: dict) -> RetrievalResult:
    """Restore a frozen retrieval row without recomputing embeddings or graph search."""
    ranked = tuple(RankedEvidence(**item) for item in row.get("ranked", []))
    return RetrievalResult(
        query_id=str(row["query_id"]),
        method=str(row["method"]),
        ranked=ranked,
        elapsed_ms=float(row.get("elapsed_ms", 0.0)),
        scored_candidates=int(row.get("scored_candidates", 0)),
        selected_evidence=int(row.get("selected_evidence", len(ranked))),
        visited_evidence=int(row.get("visited_evidence", 0)),
        visited_nodes=int(row.get("visited_nodes", 0)),
        visited_edges=int(row.get("visited_edges", 0)),
        generation_mode=str(row.get("generation_mode", "frozen_replay")),
        timed_out=bool(row.get("timed_out", False)),
        early_stopped=bool(row.get("early_stopped", False)),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scenario_specs(config: dict, requested: list[str] | None, include_ablations: bool) -> list[dict]:
    if config.get("scenarios"):
        specs = [dict(row) for row in config["scenarios"]]
        if include_ablations:
            specs.extend(dict(row) for row in config.get("ablation_scenarios", []))
        if requested:
            allowed = set(requested)
            specs = [
                row for row in specs
                if row["id"] in allowed or row["retrieval_method"] in allowed
            ]
        if not specs:
            raise ValueError("No RP2 scenarios matched --methods")
        return specs
    methods = list(requested or config["methods"])
    if include_ablations:
        methods.extend(
            method for method in config.get("ablation_methods", []) if method not in methods
        )
    return [{"id": method, "retrieval_method": method} for method in methods]


def _plot_metrics(metrics: dict, output: Path) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    methods = list(metrics["methods"])
    recall = [metrics["methods"][method]["recall_at_budget_macro"] for method in methods]
    citation = [metrics.get("generation", {}).get("by_method", {}).get(method, {}).get("silver_response_utility_macro") or 0.0 for method in methods]
    latency = [metrics.get("generation", {}).get("by_method", {}).get(method, {}).get("end_to_end_inference_latency_ms_p95") or 0.0 for method in methods]
    x = np.arange(len(methods))
    figure, axis = plt.subplots(figsize=(11, 5), constrained_layout=True)
    axis.bar(x - 0.18, recall, 0.36, label="Retrieval recall")
    axis.bar(x + 0.18, citation, 0.36, label="Silver response utility")
    axis.set_ylim(0, 1.05)
    axis.set_xticks(x, methods, rotation=20, ha="right")
    axis.set_ylabel("Quality metric")
    axis.grid(axis="y", alpha=0.25)
    second = axis.twinx()
    second.plot(x, latency, color="#c44e52", marker="o", label="End-to-end p95")
    second.set_ylabel("End-to-end inference latency p95 (ms)")
    handles, labels = axis.get_legend_handles_labels()
    handles2, labels2 = second.get_legend_handles_labels()
    axis.legend(handles + handles2, labels + labels2, loc="upper left")
    axis.set_title("GraphRAG v2 quality-latency comparison (development Silver)")
    figure.savefig(output / "method_comparison.svg", metadata={"Date": None})
    figure.savefig(output / "method_comparison.png", dpi=180, metadata={"Date": None})
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/rp2_graphrag_v2_development.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-generation", action="store_true")
    parser.add_argument("--force-generation", action="store_true")
    parser.add_argument("--require-cuda", action="store_true")
    parser.add_argument("--include-ablations", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--methods", nargs="*")
    args = parser.parse_args()

    config = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    benchmark = ROOT / config["benchmark_dir"]
    embed_path = ROOT / config["embedding"]["model_path"]
    generator_path = ROOT / config["generator"]["model_path"]
    index_dir = ROOT / config["embedding"]["index_dir"]
    frozen_retrieval_path = (
        ROOT / config["frozen_retrieval_results"]
        if config.get("frozen_retrieval_results") else None
    )
    scenarios = _scenario_specs(config, args.methods, args.include_ablations)
    candidates = [_candidate(row) for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")]
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    if args.limit:
        queries = queries[: args.limit]
    if any(query.candidate_evidence_ids for query in queries):
        raise RuntimeError("RP2 v2 forbids positive-seeded candidate pools; use full-graph benchmark")
    print(
        f"[RP2] queries={len(queries)}, graph_candidates={len(candidates)}, "
        f"scenarios={[row['id'] for row in scenarios]}, "
        f"retrieval={'FROZEN_REPLAY' if frozen_retrieval_path else 'ONLINE'}",
        flush=True,
    )
    if args.dry_run:
        print(
            f"[RP2] dry-run: benchmark=True, "
            f"frozen_retrieval={bool(frozen_retrieval_path and frozen_retrieval_path.is_file())}, "
            f"index={index_dir.is_dir()}, "
            f"BGE-M3={embed_path.is_dir()}, Qwen={generator_path.is_dir()}",
            flush=True,
        )
        return 0
    if frozen_retrieval_path and not frozen_retrieval_path.is_file():
        raise FileNotFoundError(f"Frozen retrieval results missing: {frozen_retrieval_path}")
    if not frozen_retrieval_path and not index_dir.is_dir():
        raise FileNotFoundError(f"Dense index missing: {index_dir}; run build_rp2_dense_index.py")
    if not frozen_retrieval_path and not embed_path.is_dir():
        raise FileNotFoundError(f"BGE-M3 model missing: {embed_path}")
    if not args.skip_generation and not generator_path.is_dir():
        raise FileNotFoundError(f"Qwen model missing: {generator_path}")

    retrieval_cfg = config["retrieval"]
    require_cuda = bool(args.require_cuda or config.get("runtime", {}).get("require_cuda"))
    encoder = None
    dense_index = None
    graph_index = None
    frozen_retrieval: dict[tuple[str, str], RetrievalResult] = {}
    if frozen_retrieval_path:
        for row in _read_jsonl(frozen_retrieval_path):
            restored = _retrieval_result(row)
            key = (restored.method, restored.query_id)
            if key in frozen_retrieval:
                raise RuntimeError(f"Duplicate frozen retrieval key: {key}")
            frozen_retrieval[key] = restored
    else:
        encoder = BgeM3Encoder(
            embed_path,
            batch_size=int(config["embedding"]["batch_size"]),
            max_length=int(config["embedding"]["max_length"]),
            device=config["embedding"].get("device"),
            require_cuda=require_cuda,
        )
        dense_index = DenseEvidenceIndex.load(index_dir)
        graph_index = RetrievalIndex(candidates)
    by_id = {row.evidence_id: row for row in candidates}
    generator = None if args.skip_generation else QwenLocalGenerator(
        generator_path,
        device_map=config["generator"]["device_map"],
        dtype=config["generator"]["dtype"],
        require_cuda=require_cuda,
    )
    output = ROOT / config.get(
        "output_dir", "results/experiments/research_point_2/graphrag_v2_development"
    )
    cache_dir = ROOT / config["generator"]["cache_dir"]
    output.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    results: list[RetrievalResult] = []
    generations: list[dict] = []
    total = len(scenarios) * len(queries)
    done = 0
    run_started = time.perf_counter()
    generator_identity = None if args.skip_generation else model_file_manifest(generator_path)["structure_sha256"]
    generation_contract = {
        "max_prompt_tokens": int(config.get("generation_contract", {}).get("max_prompt_tokens", 4096)),
        "max_answer_points": int(config.get("generation_contract", {}).get("max_answer_points", 2)),
        "max_point_chars": int(config.get("generation_contract", {}).get("max_point_chars", 80)),
        "max_summary_chars": int(config.get("generation_contract", {}).get("max_summary_chars", 100)),
    }
    for scenario in scenarios:
        scenario_id = str(scenario["id"])
        retrieval_method = str(scenario["retrieval_method"])
        source_retrieval_method = str(scenario.get("source_retrieval_method", retrieval_method))
        generation_strategy = str(scenario.get("generation_strategy", "freeform_v1"))
        active_system_prompt = system_prompt_for_strategy(generation_strategy)
        system_prompt_sha256 = hashlib.sha256(active_system_prompt.encode("utf-8")).hexdigest()
        use_faithfulness_guard = bool(scenario.get("faithfulness_guard", False))
        budget = RetrievalBudget(
            max_scored_candidates=int(scenario.get("max_scored_candidates", retrieval_cfg["max_scored_candidates"])),
            max_selected_evidence=int(scenario.get("max_selected_evidence", retrieval_cfg["max_selected_evidence"])),
            max_per_source_family=int(scenario.get("max_per_source_family", retrieval_cfg["max_per_source_family"])),
            source_family_bonus=float(scenario.get("source_family_bonus", retrieval_cfg["source_family_bonus"])),
            redundancy_penalty=float(scenario.get("redundancy_penalty", retrieval_cfg["redundancy_penalty"])),
        )
        for query in queries:
            done += 1
            started = time.perf_counter()
            if frozen_retrieval_path:
                key = (source_retrieval_method, query.query_id)
                if key not in frozen_retrieval:
                    raise RuntimeError(f"Frozen retrieval row missing: {key}")
                result = frozen_retrieval[key]
            else:
                result = _closed_book(query) if retrieval_method == "closed_book" else retrieve_dense_graph(
                    query,
                    candidates,
                    graph_index,
                    dense_index,
                    encoder,
                    method=retrieval_method,
                    budget=budget,
                    dense_top_n=int(scenario.get("dense_top_n", retrieval_cfg["dense_top_n"])),
                    anchor_evidence_count=int(scenario.get("anchor_evidence_count", retrieval_cfg["anchor_evidence_count"])),
                    fixed_hops=int(scenario.get("fixed_hops", retrieval_cfg["fixed_hops"])),
                    ours_graph_hops=int(scenario.get("ours_graph_hops", retrieval_cfg.get("ours_graph_hops", 1))),
                    ours_graph_decay=float(scenario.get("ours_graph_decay", retrieval_cfg.get("ours_graph_decay", 0.70))),
                    graph_score_weight=float(scenario.get("graph_score_weight", retrieval_cfg.get("graph_score_weight", 0.12))),
                    fault_affinity_weight=float(scenario.get("fault_affinity_weight", retrieval_cfg.get("fault_affinity_weight", 0.0))),
                    fault_affinity_floor=float(scenario.get("fault_affinity_floor", retrieval_cfg.get("fault_affinity_floor", 0.0))),
                )
            result = replace(result, method=scenario_id)
            results.append(result)
            generation_source = "SKIPPED"
            if generator is not None:
                missing_evidence = [
                    row.evidence_id for row in result.ranked if row.evidence_id not in by_id
                ]
                if missing_evidence:
                    raise RuntimeError(
                        f"Frozen retrieval references unknown benchmark evidence: {missing_evidence}"
                    )
                evidence = [by_id[row.evidence_id] for row in result.ranked if row.evidence_id in by_id]
                prompt, evidence, prompt_budget_dropped, planned_prompt_tokens = fit_prompt_budget(
                    query,
                    evidence,
                    generator,
                    generation_contract,
                    strategy=generation_strategy,
                    system_prompt=active_system_prompt,
                )
                if prompt_budget_dropped:
                    kept_ids = {row.evidence_id for row in evidence}
                    result = replace(
                        result,
                        ranked=tuple(row for row in result.ranked if row.evidence_id in kept_ids),
                        selected_evidence=len(evidence),
                    )
                    results[-1] = result
                cache_key = hashlib.sha256(
                    json.dumps(
                        {
                            "scenario": scenario,
                            "query": asdict(query),
                            "prompt": prompt,
                            "protocol": config["version"],
                            "generator_structure_sha256": generator_identity,
                            "system_prompt_sha256": system_prompt_sha256,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest()
                cache_path = cache_dir / f"{cache_key}.json"
                generation_started = time.perf_counter()
                if generation_strategy == "evidence_mask_v3" and not evidence:
                    model_payload = {"direct": []}
                    generation_metrics = {
                        "prompt_tokens": 0,
                        "generated_tokens": 0,
                        "input_preparation_ms": 0.0,
                        "elapsed_ms": 0.0,
                        "tokens_per_second": 0.0,
                        "cuda_peak_memory_bytes": 0,
                        "cuda_allocated_memory_bytes": 0,
                        "model_output_valid_json": True,
                        "deterministic_empty_short_circuit": True,
                    }
                    generation_source = "DETERMINISTIC_EMPTY"
                elif cache_path.exists() and not args.force_generation:
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                    if "answer" in cached:
                        model_payload = cached["answer"]
                        generation_metrics = cached.get("generation_metrics", {})
                    else:
                        model_payload = cached
                        generation_metrics = {}
                    generation_source = "CACHE"
                else:
                    model_payload = generator.generate_json(
                        active_system_prompt,
                        prompt,
                        max_new_tokens=int(scenario.get("max_new_tokens", config["generator"]["max_new_tokens"])),
                    )
                    generation_metrics = dict(generator.last_metrics)
                    cache_path.write_text(
                        json.dumps(
                            {"answer": model_payload, "generation_metrics": generation_metrics},
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    generation_source = "MODEL"
                compact_mask_audit = None
                if generation_strategy == "evidence_mask_v3":
                    raw_answer, compact_mask_audit = expand_compact_evidence_mask(
                        model_payload, evidence
                    )
                else:
                    raw_answer = model_payload
                guard_audit = None
                if use_faithfulness_guard:
                    guard = (
                        apply_evidence_coverage_guard
                        if generation_strategy in {"evidence_coverage_v2", "evidence_mask_v3"}
                        else apply_faithfulness_guard
                    )
                    answer, guard_audit = guard(
                        raw_answer,
                        query,
                        evidence,
                        generation_contract,
                        minimum_fault_affinity=float(
                            scenario.get("minimum_visible_fault_affinity", 0.0)
                        ),
                    )
                else:
                    answer = raw_answer
                validation = validate_generated_answer(
                    answer,
                    {row.evidence_id for row in evidence},
                    max_answer_points=generation_contract["max_answer_points"],
                    max_point_chars=generation_contract["max_point_chars"],
                    max_summary_chars=generation_contract["max_summary_chars"],
                )
                if generation_strategy in {"evidence_coverage_v2", "evidence_mask_v3"}:
                    assessment_contract_valid = validate_candidate_assessment_contract(
                        raw_answer, {row.evidence_id for row in evidence}
                    )
                    validation["candidate_assessment_contract_valid"] = assessment_contract_valid
                    validation["contract_valid"] = bool(
                        validation["contract_valid"] and assessment_contract_valid
                    )
                cited = {
                    str(eid)
                    for point in answer.get("answer_points", []) if isinstance(point, dict)
                    for eid in point.get("evidence_ids", [])
                }
                relevant = set(query.relevant_evidence_ids)
                silver_evaluation = score_silver_response(answer, validation, relevant)
                request_wall_ms = (time.perf_counter() - generation_started) * 1000
                generations.append({
                    "query_id": query.query_id,
                    "method": scenario_id,
                    "retrieval_method": retrieval_method,
                    "source_retrieval_method": source_retrieval_method,
                    "scenario": scenario,
                    "answer": answer,
                    "raw_model_answer": raw_answer if use_faithfulness_guard else None,
                    "raw_model_payload": (
                        model_payload if generation_strategy == "evidence_mask_v3" else None
                    ),
                    "compact_mask_audit": compact_mask_audit,
                    "generation_strategy": generation_strategy,
                    "faithfulness_guard": guard_audit,
                    "validation": validation,
                    "relevant_citation_recall": len(cited & relevant) / len(relevant) if relevant else None,
                    "silver_evaluation": silver_evaluation,
                    "planned_prompt_tokens": planned_prompt_tokens,
                    "prompt_budget_dropped_evidence": prompt_budget_dropped,
                    "retrieval_elapsed_ms": result.elapsed_ms,
                    "generation_request_wall_ms": request_wall_ms,
                    "generation_model_elapsed_ms": generation_metrics.get("elapsed_ms"),
                    "end_to_end_model_elapsed_ms": (
                        result.elapsed_ms + float(generation_metrics.get("elapsed_ms", 0.0))
                        if generation_metrics.get("elapsed_ms") is not None else None
                    ),
                    "end_to_end_inference_elapsed_ms": (
                        result.elapsed_ms
                        + float(generation_metrics.get("input_preparation_ms", 0.0))
                        + float(generation_metrics.get("elapsed_ms", 0.0))
                        + float((guard_audit or {}).get("elapsed_ms", 0.0))
                        if generation_metrics.get("elapsed_ms") is not None else None
                    ),
                    "model_metrics": generation_metrics,
                    "source": generation_source,
                })
            elapsed = time.perf_counter() - started
            eta = ((time.perf_counter() - run_started) / done) * (total - done) / 60
            print(
                f"[RP2][{done}/{total}] {scenario_id}:{query.query_id} "
                f"evidence={len(result.ranked)}, generation={generation_source}, elapsed={elapsed:.1f}s, ETA={eta:.1f}m",
                flush=True,
            )

    metrics = evaluate_results(queries, candidates, results)
    if generations:
        generation_groups: dict[str, list[dict]] = defaultdict(list)
        for row in generations:
            generation_groups[row["method"]].append(row)
        query_by_id = {query.query_id: query for query in queries}
        by_method = {}
        by_method_role = {}
        for method, rows in generation_groups.items():
            by_method[method] = summarize_generation_rows(rows, query_by_id)
            role_groups: dict[str, list[dict]] = defaultdict(list)
            for row in rows:
                role_groups[query_by_id[row["query_id"]].role].append(row)
            by_method_role[method] = {
                role: summarize_generation_rows(role_rows, query_by_id)
                for role, role_rows in sorted(role_groups.items())
            }
        metrics["generation"] = summarize_generation_rows(generations, query_by_id)
        metrics["generation"]["by_method"] = by_method
        metrics["generation"]["by_method_and_role"] = by_method_role
        metrics["generation"]["latency_scope"] = (
            "model_metrics.elapsed_ms is reused for cached responses; request wall time is reported separately"
        )
    metrics["run_manifest"] = {
        "protocol_id": config["protocol_id"],
        "protocol_version": config["version"],
        "embedding_model": model_file_manifest(embed_path) if embed_path.is_dir() else None,
        "generator_model": None if args.skip_generation else model_file_manifest(generator_path),
        "full_graph_candidate_count": len(candidates),
        "query_count": len(queries),
        "scenarios": scenarios,
        "generation_contract": generation_contract,
        "force_generation": bool(args.force_generation),
        "retrieval_replay": bool(frozen_retrieval_path),
        "frozen_retrieval_results": (
            str(frozen_retrieval_path.relative_to(ROOT)) if frozen_retrieval_path else None
        ),
        "frozen_retrieval_file_sha256": (
            _sha256(frozen_retrieval_path) if frozen_retrieval_path else None
        ),
        "system_prompt_sha256_by_scenario": {
            str(row["id"]): hashlib.sha256(
                system_prompt_for_strategy(str(row.get("generation_strategy", "freeform_v1"))).encode("utf-8")
            ).hexdigest()
            for row in scenarios
        },
        "embedding_runtime": getattr(encoder, "runtime_manifest", {}),
        "embedding_device": getattr(encoder, "device", None),
        "generator_runtime": getattr(generator, "runtime_manifest", None),
        "label_policy": "Silver only; never Gold",
    }
    effectiveness_tests = config.get("effectiveness_tests", [])
    if generations and effectiveness_tests:
        available_scenarios = {str(row["method"]) for row in generations}
        effectiveness_reports = {}
        for test in effectiveness_tests:
            reference_id = str(test["reference_id"])
            proposed_ids = [
                str(value) for value in test["proposed_ids"]
                if str(value) in available_scenarios
            ]
            if reference_id not in available_scenarios or not proposed_ids:
                effectiveness_reports[str(test["id"])] = {
                    "status": "skipped_missing_scenarios",
                    "required_reference": reference_id,
                    "required_proposed": [str(value) for value in test["proposed_ids"]],
                    "available_scenarios": sorted(available_scenarios),
                }
                continue
            effectiveness_reports[str(test["id"])] = analyze_budget_effectiveness(
                generations,
                reference_id=reference_id,
                proposed_ids=proposed_ids,
                latency_noninferiority_margin=float(
                    test.get("latency_noninferiority_margin", 0.05)
                ),
                minimum_quality_gain=float(test.get("minimum_quality_gain", 0.0)),
                bootstrap_iterations=int(test.get("bootstrap_iterations", 2000)),
                seed=int(test.get("seed", 20260803)),
            )
        metrics["budget_effectiveness"] = effectiveness_reports
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "retrieval_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
    with (output / "generation_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in generations:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    _plot_metrics(metrics, output)
    print(f"[RP2] completed: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
