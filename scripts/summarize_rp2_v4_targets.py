#!/usr/bin/env python3
"""Summarize configured RP2 paper-readiness gates without relabeling data."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _oracle_f1(relevant_count: int, budget: int) -> float:
    selected = min(relevant_count, budget)
    if selected <= 0:
        return 0.0
    recall = selected / relevant_count
    return 2.0 * recall / (1.0 + recall)


def _fmt(value: object) -> str:
    return "pending" if value is None else f"{float(value):.3f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/rp2_graphrag_v4_faithfulness.json")
    parser.add_argument(
        "--judge",
        default=None,
    )
    args = parser.parse_args()
    config = _json(ROOT / args.config)
    output = ROOT / config["output_dir"]
    metrics_path = output / "metrics.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"Missing v4 metrics: {metrics_path}")
    metrics = _json(metrics_path)
    judge_path = ROOT / (
        args.judge
        or config.get(
            "paper_readiness_judge_summary",
            "results/experiments/research_point_2/rp2_v4_dual_prompt_semantic_judge/semantic_judge_summary.json",
        )
    )
    judge = _json(judge_path) if judge_path.is_file() else {}
    benchmark = ROOT / config["benchmark_dir"] / "queries.jsonl"
    queries = [json.loads(line) for line in benchmark.open(encoding="utf-8") if line.strip()]
    relevant_counts = [len(row.get("relevant_evidence_ids", [])) for row in queries]
    relevant_counts = [value for value in relevant_counts if value > 0]
    generation = metrics.get("generation", {}).get("by_method", {})
    scenarios = {str(row["id"]): row for row in config["scenarios"]}
    targets = config["paper_readiness_targets"]
    rows = []
    for method, scenario in scenarios.items():
        values = generation.get(method, {})
        budget = int(scenario["max_selected_evidence"])
        oracle = statistics.fmean(_oracle_f1(count, budget) for count in relevant_counts)
        citation_f1 = values.get("silver_citation_f1_macro_answerable")
        normalized_f1 = float(citation_f1) / oracle if citation_f1 is not None and oracle else None
        semantic = judge.get("methods", {}).get(method, {})
        latency = values.get("end_to_end_inference_latency_ms_p95")
        rows.append({
            "method": method,
            "budget": budget,
            "silver_citation_precision_macro": values.get("silver_citation_precision_macro"),
            "silver_citation_f1_macro_answerable": citation_f1,
            "budget_oracle_f1_macro": oracle,
            "budget_normalized_silver_citation_f1": normalized_f1,
            "dual_strict_point_support_rate": semantic.get("dual_strict_point_support_rate"),
            "all_atomic_claims_strictly_supported_answer_rate": semantic.get(
                "all_atomic_claims_strictly_supported_answer_rate"
            ),
            "all_text_strictly_supported_answer_rate": semantic.get(
                "all_text_strictly_supported_answer_rate"
            ),
            "answerable_answer_rate": values.get("answerable_answer_rate"),
            "unanswerable_abstention_rate": values.get("unanswerable_abstention_rate"),
            "strict_contract_rate": values.get("strict_contract_rate"),
            "candidate_assessment_contract_rate": values.get(
                "candidate_assessment_contract_rate"
            ),
            "citations_per_answered_query_mean": values.get(
                "citations_per_answered_query_mean"
            ),
            "multi_citation_answer_rate": values.get("multi_citation_answer_rate"),
            "end_to_end_inference_latency_ms_p95": latency,
        })
    by_method = {row["method"]: row for row in rows}
    selected_method = str(config.get("paper_readiness_selected_method", "Ours_v4_k3"))
    latency_reference = str(
        config.get("paper_readiness_latency_reference", "B1_dense_k4_guard")
    )
    proposed = by_method.get(selected_method, {})
    reference = by_method.get(latency_reference, {})
    latency_ratio = (
        float(proposed["end_to_end_inference_latency_ms_p95"])
        / float(reference["end_to_end_inference_latency_ms_p95"])
        if proposed.get("end_to_end_inference_latency_ms_p95")
        and reference.get("end_to_end_inference_latency_ms_p95")
        else None
    )
    proposed["p95_latency_ratio_vs_dense_k4"] = latency_ratio
    gate_map = {
        "silver_citation_precision_macro": ">=",
        "budget_normalized_silver_citation_f1": ">=",
        "dual_strict_point_support_rate": ">=",
        "all_atomic_claims_strictly_supported_answer_rate": ">=",
        "all_text_strictly_supported_answer_rate": ">=",
        "answerable_answer_rate": ">=",
        "unanswerable_abstention_rate": ">=",
        "strict_contract_rate": ">=",
        "p95_latency_ratio_vs_dense_k4_max": "<=",
    }
    gate_results = {}
    for name, operator in gate_map.items():
        value_key = "p95_latency_ratio_vs_dense_k4" if name.endswith("_max") else name
        value = proposed.get(value_key)
        target = float(targets[name])
        gate_results[name] = {
            "value": value,
            "target": target,
            "operator": operator,
            "passed": None if value is None else (float(value) >= target if operator == ">=" else float(value) <= target),
        }
    report = {
        "protocol_id": config["protocol_id"],
        "selected_method": selected_method,
        "latency_reference_method": latency_reference,
        "methods": rows,
        "paper_readiness_gates": gate_results,
        "all_available_gates_passed": (
            all(row["passed"] for row in gate_results.values() if row["passed"] is not None)
            and all(row["passed"] is not None for row in gate_results.values())
        ),
        "metric_policy": {
            "budget_normalized_f1": "macro Silver citation F1 divided by the per-query ideal F1 achievable under the same evidence budget",
            "semantic_support": "dual prompts of one qwen3.7-max model; Silver semantic audit, not human expert verification",
            "no_posthoc_relabeling": True,
            "unanswerable_and_contract_gates_prevent_abstention_gaming": True,
        },
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    (output / "paper_readiness_targets.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        f"# RP2 论文就绪门槛：{config['protocol_id']}",
        "",
        "所有证据与语义标签均为 Silver，未经领域专家审核。",
        "",
        "| 方法 | P | F1 | 预算归一F1 | 平均引用 | 多引用率 | 逐候选契约 | 严格点支持 | 全原子主张支持 | 可回答回答率 | 不可回答拒答率 | p95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['method']} | {_fmt(row['silver_citation_precision_macro'])} | "
            f"{_fmt(row['silver_citation_f1_macro_answerable'])} | "
            f"{_fmt(row['budget_normalized_silver_citation_f1'])} | "
            f"{_fmt(row['citations_per_answered_query_mean'])} | "
            f"{_fmt(row['multi_citation_answer_rate'])} | "
            f"{_fmt(row['candidate_assessment_contract_rate'])} | "
            f"{_fmt(row['dual_strict_point_support_rate'])} | "
            f"{_fmt(row['all_atomic_claims_strictly_supported_answer_rate'])} | "
            f"{_fmt(row['answerable_answer_rate'])} | {_fmt(row['unanswerable_abstention_rate'])} | "
            f"{_fmt(row['end_to_end_inference_latency_ms_p95'])} |"
        )
    lines.extend(["", f"## {selected_method} 门槛", ""])
    for name, gate in gate_results.items():
        state = "PENDING" if gate["passed"] is None else ("PASS" if gate["passed"] else "FAIL")
        lines.append(
            f"- {name}: {_fmt(gate['value'])} {gate['operator']} {gate['target']:.3f} — {state}"
        )
    (output / "paper_readiness_targets.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[RP2 targets] completed: {output / 'paper_readiness_targets.md'}")
    print(f"[RP2 targets] selected={selected_method}, all gates passed={report['all_available_gates_passed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
