#!/usr/bin/env python3
"""Run full-graph BGE-M3 retrieval and evidence-grounded Qwen2.5-7B generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.dataset import EvidenceCandidate, SilverQuery, _read_jsonl  # noqa: E402
from research_point_2.dense_index import DenseEvidenceIndex  # noqa: E402
from research_point_2.evaluation import evaluate_results  # noqa: E402
from research_point_2.generation import (  # noqa: E402
    SYSTEM_PROMPT,
    build_generation_prompt,
    summarize_generation_rows,
    validate_generated_answer,
)
from research_point_2.graph_rag_v2 import retrieve_dense_graph  # noqa: E402
from research_point_2.local_models import BgeM3Encoder, QwenLocalGenerator, model_file_manifest  # noqa: E402
from research_point_2.retrieval import RetrievalBudget, RetrievalIndex, RetrievalResult  # noqa: E402


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


def _mean(rows: list[float]) -> float:
    return statistics.fmean(rows) if rows else 0.0


def _plot_metrics(metrics: dict, output: Path) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    methods = list(metrics["methods"])
    recall = [metrics["methods"][method]["recall_at_budget_macro"] for method in methods]
    citation = [metrics.get("generation", {}).get("by_method", {}).get(method, {}).get("citation_id_validity_rate") or 0.0 for method in methods]
    latency = [metrics.get("generation", {}).get("by_method", {}).get(method, {}).get("end_to_end_model_latency_ms_mean") or 0.0 for method in methods]
    x = np.arange(len(methods))
    figure, axis = plt.subplots(figsize=(11, 5), constrained_layout=True)
    axis.bar(x - 0.18, recall, 0.36, label="Retrieval recall")
    axis.bar(x + 0.18, citation, 0.36, label="Citation-ID validity")
    axis.set_ylim(0, 1.05)
    axis.set_xticks(x, methods, rotation=20, ha="right")
    axis.set_ylabel("Quality metric")
    axis.grid(axis="y", alpha=0.25)
    second = axis.twinx()
    second.plot(x, latency, color="#c44e52", marker="o", label="Generation latency")
    second.set_ylabel("Model end-to-end latency (ms)")
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
    methods = list(args.methods or config["methods"])
    if args.include_ablations:
        methods.extend(
            method for method in config.get("ablation_methods", []) if method not in methods
        )
    candidates = [_candidate(row) for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")]
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    if args.limit:
        queries = queries[: args.limit]
    if any(query.candidate_evidence_ids for query in queries):
        raise RuntimeError("RP2 v2 forbids positive-seeded candidate pools; use full-graph benchmark")
    print(f"[RP2 v2] queries={len(queries)}, graph_candidates={len(candidates)}, methods={methods}", flush=True)
    if args.dry_run:
        print(
            f"[RP2 v2] dry-run: benchmark=True, index={index_dir.is_dir()}, "
            f"BGE-M3={embed_path.is_dir()}, Qwen={generator_path.is_dir()}",
            flush=True,
        )
        return 0
    if not index_dir.is_dir():
        raise FileNotFoundError(f"Dense index missing: {index_dir}; run build_rp2_dense_index.py")
    if not embed_path.is_dir():
        raise FileNotFoundError(f"BGE-M3 model missing: {embed_path}")
    if not args.skip_generation and not generator_path.is_dir():
        raise FileNotFoundError(f"Qwen model missing: {generator_path}")

    retrieval_cfg = config["retrieval"]
    require_cuda = bool(args.require_cuda or config.get("runtime", {}).get("require_cuda"))
    budget = RetrievalBudget(
        max_scored_candidates=int(retrieval_cfg["max_scored_candidates"]),
        max_selected_evidence=int(retrieval_cfg["max_selected_evidence"]),
        max_per_source_family=int(retrieval_cfg["max_per_source_family"]),
        source_family_bonus=float(retrieval_cfg["source_family_bonus"]),
        redundancy_penalty=float(retrieval_cfg["redundancy_penalty"]),
    )
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
    total = len(methods) * len(queries)
    done = 0
    run_started = time.perf_counter()
    generator_identity = None if args.skip_generation else model_file_manifest(generator_path)["structure_sha256"]
    system_prompt_sha256 = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    for method in methods:
        for query in queries:
            done += 1
            started = time.perf_counter()
            result = _closed_book(query) if method == "closed_book" else retrieve_dense_graph(
                query,
                candidates,
                graph_index,
                dense_index,
                encoder,
                method=method,
                budget=budget,
                dense_top_n=int(retrieval_cfg["dense_top_n"]),
                anchor_evidence_count=int(retrieval_cfg["anchor_evidence_count"]),
                fixed_hops=int(retrieval_cfg["fixed_hops"]),
                ours_graph_hops=int(retrieval_cfg.get("ours_graph_hops", 1)),
                ours_graph_decay=float(retrieval_cfg.get("ours_graph_decay", 0.70)),
                graph_score_weight=float(retrieval_cfg.get("graph_score_weight", 0.12)),
            )
            results.append(result)
            generation_source = "SKIPPED"
            if generator is not None:
                evidence = [by_id[row.evidence_id] for row in result.ranked if row.evidence_id in by_id]
                prompt = build_generation_prompt(query, evidence)
                cache_key = hashlib.sha256(
                    json.dumps(
                        {
                            "method": method,
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
                if cache_path.exists() and not args.force_generation:
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                    if "answer" in cached:
                        answer = cached["answer"]
                        generation_metrics = cached.get("generation_metrics", {})
                    else:
                        answer = cached
                        generation_metrics = {}
                    generation_source = "CACHE"
                else:
                    answer = generator.generate_json(
                        SYSTEM_PROMPT,
                        prompt,
                        max_new_tokens=int(config["generator"]["max_new_tokens"]),
                    )
                    generation_metrics = dict(generator.last_metrics)
                    cache_path.write_text(
                        json.dumps(
                            {"answer": answer, "generation_metrics": generation_metrics},
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    generation_source = "MODEL"
                validation = validate_generated_answer(answer, {row.evidence_id for row in evidence})
                cited = {
                    str(eid)
                    for point in answer.get("answer_points", []) if isinstance(point, dict)
                    for eid in point.get("evidence_ids", [])
                }
                relevant = set(query.relevant_evidence_ids)
                request_wall_ms = (time.perf_counter() - generation_started) * 1000
                generations.append({
                    "query_id": query.query_id,
                    "method": method,
                    "answer": answer,
                    "validation": validation,
                    "relevant_citation_recall": len(cited & relevant) / len(relevant) if relevant else None,
                    "retrieval_elapsed_ms": result.elapsed_ms,
                    "generation_request_wall_ms": request_wall_ms,
                    "generation_model_elapsed_ms": generation_metrics.get("elapsed_ms"),
                    "end_to_end_model_elapsed_ms": (
                        result.elapsed_ms + float(generation_metrics.get("elapsed_ms", 0.0))
                        if generation_metrics.get("elapsed_ms") is not None else None
                    ),
                    "model_metrics": generation_metrics,
                    "source": generation_source,
                })
            elapsed = time.perf_counter() - started
            eta = ((time.perf_counter() - run_started) / done) * (total - done) / 60
            print(
                f"[RP2 v2][{done}/{total}] {method}:{query.query_id} "
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
        for method, rows in generation_groups.items():
            by_method[method] = summarize_generation_rows(rows, query_by_id)
        metrics["generation"] = summarize_generation_rows(generations, query_by_id)
        metrics["generation"]["by_method"] = by_method
        metrics["generation"]["latency_scope"] = (
            "model_metrics.elapsed_ms is reused for cached responses; request wall time is reported separately"
        )
    metrics["run_manifest"] = {
        "protocol_id": config["protocol_id"],
        "protocol_version": config["version"],
        "embedding_model": model_file_manifest(embed_path),
        "generator_model": None if args.skip_generation else model_file_manifest(generator_path),
        "full_graph_candidate_count": len(candidates),
        "query_count": len(queries),
        "force_generation": bool(args.force_generation),
        "system_prompt_sha256": system_prompt_sha256,
        "embedding_runtime": getattr(encoder, "runtime_manifest", {}),
        "embedding_device": getattr(encoder, "device", None),
        "generator_runtime": getattr(generator, "runtime_manifest", None),
        "label_policy": "Silver only; never Gold",
    }
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "retrieval_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
    with (output / "generation_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in generations:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    _plot_metrics(metrics, output)
    print(f"[RP2 v2] completed: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
