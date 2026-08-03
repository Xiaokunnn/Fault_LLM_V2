#!/usr/bin/env python3
"""Freeze RP2 v3 only after complete latency replay and dual-prompt Silver audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="configs/frozen/rp2_v3_frozen_protocol.json")
    args = parser.parse_args()
    paths = {
        "config": ROOT / "configs/rp2_graphrag_v3_budget_effectiveness.json",
        "development_metrics": ROOT / "results/experiments/research_point_2/graphrag_v3_budget_effectiveness/metrics.json",
        "development_retrieval": ROOT / "results/experiments/research_point_2/graphrag_v3_budget_effectiveness/retrieval_results.jsonl",
        "development_generation": ROOT / "results/experiments/research_point_2/graphrag_v3_budget_effectiveness/generation_results.jsonl",
        "latency_summary": ROOT / "results/experiments/research_point_2/rp2_v3_interleaved_latency/latency_summary.json",
        "latency_raw": ROOT / "results/experiments/research_point_2/rp2_v3_interleaved_latency/latency_replay.jsonl",
        "semantic_judge_summary": ROOT / "results/experiments/research_point_2/rp2_v3_dual_prompt_semantic_judge/semantic_judge_summary.json",
        "retrieval_code": ROOT / "src/research_point_2/graph_rag_v2.py",
        "generation_code": ROOT / "src/research_point_2/generation.py",
        "evaluation_code": ROOT / "src/research_point_2/budget_effectiveness.py",
        "runner_code": ROOT / "scripts/run_rp2_graphrag_v2.py",
        "external_config_template": ROOT / "configs/rp2_graphrag_v3_external_source_heldout.json",
        "external_extraction_config": ROOT / "configs/triple_extraction_qwen3_7_max_heldout_external_v3.json",
        "external_prepare_code": ROOT / "scripts/prepare_shared_heldout_evaluation.py",
    }
    missing = [str(path.relative_to(ROOT)) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Cannot freeze RP2 v3; missing required artifacts: {missing}")
    latency = _json(paths["latency_summary"])
    judge = _json(paths["semantic_judge_summary"])
    development = _json(paths["development_metrics"])
    if latency.get("formal_full_query_run") is not True or latency.get("query_count") != 40:
        raise RuntimeError("Latency replay is not a complete 40-query formal run")
    for method in ("B1_dense_k4", "B4_metapath_k3", "Ours_k3"):
        metrics = latency.get("methods", {}).get(method, {})
        if not metrics.get("completed") or metrics.get("samples", 0) < 200:
            raise RuntimeError(f"Latency replay incomplete for {method}: {metrics}")
    if judge.get("formal_full_answer_run") is not True or judge.get("answer_records") != 120:
        raise RuntimeError("Semantic Judge is not the complete 120-answer formal audit")
    if set(judge.get("selected_methods", [])) != {
        "B1_dense_k4", "B4_metapath_k3", "Ours_k3"
    }:
        raise RuntimeError("Semantic Judge methods do not match frozen finalists")
    if int(judge.get("judged_items", 0)) <= 0:
        raise RuntimeError("Semantic Judge contains no assessed answer text")
    for method in ("B1_dense_k4", "B4_metapath_k3", "Ours_k3"):
        if int(judge.get("methods", {}).get(method, {}).get("total_answers", 0)) != 40:
            raise RuntimeError(f"Semantic Judge incomplete for {method}")
    external_outputs = [
        ROOT / "data/interim/heldout_external/shared_silver_v3",
        ROOT / "results/experiments/research_point_2/graphrag_v3_external_source_heldout",
    ]
    if any(path.exists() for path in external_outputs):
        raise RuntimeError(
            "External v3 outputs already exist. Refusing to create a retroactive freeze manifest."
        )
    config = _json(paths["config"])
    scenarios = {row["id"]: row for row in config["scenarios"]}
    manifest = {
        "protocol_id": "marine_pump_rp2_budget_effectiveness_v3_frozen",
        "version": "1.0.0",
        "status": "frozen_before_external_source_heldout_v3",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head_before_freeze_commit": _git_head(),
        "selected_operating_point": "Ours_k3",
        "frozen_scenarios": {
            key: scenarios[key]
            for key in ("B1_dense_k4", "B4_metapath_k3", "Ours_k3")
        },
        "frozen_generation_contract": config["generation_contract"],
        "frozen_retrieval_defaults": config["retrieval"],
        "effectiveness_tests": config["effectiveness_tests"],
        "development_gate_results": development.get("budget_effectiveness", {}),
        "latency_replay_summary": latency,
        "semantic_judge_method_summary": judge.get("methods", {}),
        "embedding_model": development["run_manifest"]["embedding_model"],
        "generator_model": development["run_manifest"]["generator_model"],
        "artifact_sha256": {
            name: {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _sha256(path),
            }
            for name, path in paths.items()
        },
        "external_policy": {
            "documents": ["MP010", "MP011", "MP012", "MP013"],
            "description": "source-held-out external Silver evaluation; not a strict untouched blind test for the full v3 history",
            "must_not_tune": True,
            "must_not_enter_primary_graph": True,
            "external_results_must_be_reported_once_without_parameter_changes": True,
        },
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[RP2 freeze] created: {output}")
    print("Commit this manifest and all latency/Judge artifacts before external evaluation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
