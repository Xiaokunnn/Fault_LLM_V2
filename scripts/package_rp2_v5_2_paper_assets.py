#!/usr/bin/env python3
"""Freeze RP2 v5.2 inputs/results and build publication-ready paper assets.

This script is deliberately read-only with respect to the source experiment
directories.  It derives tables, figures, and a SHA-256 freeze manifest in a
separate paper-package directory.  No model call, retrieval rerun, or label
rewrite is performed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RP2 = ROOT / "results/experiments/research_point_2"
V52 = RP2 / "graphrag_v5_2_recall_cascade"
JUDGE = RP2 / "rp2_v5_2_dual_prompt_semantic_judge/semantic_judge_summary.json"
ABLATION = RP2 / "graph_ablation_v1/metrics.json"
SENSITIVITY = RP2 / "graphrag_v2_sensitivity_v2/sensitivity_metrics.json"
EXTERNAL = RP2 / "graphrag_v3_external_source_heldout/metrics.json"
OUT = RP2 / "rp2_v5_2_paper_package"
FREEZE = ROOT / "configs/frozen/rp2_v5_2_protocol_freeze.json"

COLORS = {
    "dense": "#0077BB",
    "role": "#EE7733",
    "ours": "#009988",
    "latency": "#CC3311",
}

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

METHOD_LABELS = {
    "B1_dense_k4_cascade": "Dense K4",
    "B4_role_k3_cascade": "Role K3",
    "Ours_v5_2_k3_cascade": "Ours K3",
    "B1_dense_k4": "Dense K4",
    "B4_metapath_k3": "Role K3",
    "Ours_k3": "Ours K3",
}

ABLATION_LABELS = {
    "adaptive_prune": "Adaptive pruning",
    "fixed_hop": "Fixed-hop diffusion",
    "metapath_topk": "Role/metapath top-K",
    "ours": "Ours (complete)",
    "ours_no_index": "Ours w/o candidate index",
    "ours_no_redundancy": "Ours w/o redundancy control",
    "ours_no_role_gate": "Ours w/o role gate",
    "ours_no_source_family": "Ours w/o source-family cap",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.{digits}f}"


def markdown_table(fields: list[str], rows: Iterable[dict[str, Any]]) -> str:
    rows = list(rows)
    lines = [
        "| " + " | ".join(fields) + " |",
        "|" + "|".join("---" for _ in fields) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(lines)


def main_results() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metrics = load_json(V52 / "metrics.json")
    readiness = load_json(V52 / "paper_readiness_targets.json")
    judge = load_json(JUDGE)
    retrieval = metrics["methods"]
    generation = metrics["generation"]["by_method"]
    semantic = judge["methods"]
    rows: list[dict[str, Any]] = []
    for method in ["B1_dense_k4_cascade", "B4_role_k3_cascade", "Ours_v5_2_k3_cascade"]:
        r, g, s = retrieval[method], generation[method], semantic[method]
        readiness_row = next(x for x in readiness["methods"] if x["method"] == method)
        rows.append(
            {
                "Method": METHOD_LABELS[method],
                "Budget": readiness_row["budget"],
                "Recall@B": round(r["recall_at_budget_macro"], 6),
                "MRR": round(r["mrr"], 6),
                "NDCG@B": round(r["ndcg_at_budget_macro"], 6),
                "Silver_P": round(g["silver_citation_precision_macro"], 6),
                "Silver_F1": round(g["silver_citation_f1_macro_answerable"], 6),
                "Norm_F1": round(readiness_row["budget_normalized_silver_citation_f1"], 6),
                "Utility": round(g["silver_response_utility_macro"], 6),
                "Strict_point": round(s["dual_strict_point_support_rate"], 6),
                "Strict_answer": round(s["all_text_strictly_supported_answer_rate"], 6),
                "Answer_rate": round(g["answerable_answer_rate"], 6),
                "Abstain_rate": round(g["unanswerable_abstention_rate"], 6),
                "p95_ms": round(g["end_to_end_inference_latency_ms_p95"], 3),
                "Prompt_tokens": round(g["prompt_tokens_mean"], 3),
            }
        )
    return rows, metrics


def ablation_results() -> list[dict[str, Any]]:
    data = load_json(ABLATION)
    rows = []
    order = [
        "fixed_hop",
        "adaptive_prune",
        "metapath_topk",
        "ours_no_index",
        "ours_no_role_gate",
        "ours_no_source_family",
        "ours_no_redundancy",
        "ours",
    ]
    for method in order:
        x = data["methods"][method]
        rows.append(
            {
                "Method": ABLATION_LABELS[method],
                "Recall@4": round(x["recall_at_budget_macro"], 6),
                "MRR": round(x["mrr"], 6),
                "NDCG@4": round(x["ndcg_at_budget_macro"], 6),
                "Source_families": round(x["mean_source_family_coverage"], 6),
                "Exact_redundancy": round(x["mean_exact_claim_redundancy"], 6),
                "p95_retrieval_ms": round(x["latency_ms_p95"], 6),
                "Scored_candidates": round(x["mean_scored_candidates"], 6),
            }
        )
    return rows


def sensitivity_results() -> list[dict[str, Any]]:
    data = load_json(SENSITIVITY)
    return [
        {
            "Setting": row["setting_id"],
            "K": row["k"],
            "Family_cap": row["family_cap"],
            "Source_bonus": row["source_bonus"],
            "Redundancy_penalty": row["redundancy_penalty"],
            "Graph_hops": row["graph_hops"],
            "Graph_weight": row["graph_weight"],
            "Recall@B": round(row["recall_at_budget_macro"], 6),
            "NDCG@B": round(row["ndcg_at_budget_macro"], 6),
            "p95_retrieval_ms": round(row["latency_ms_p95"], 6),
        }
        for row in data["rows"]
    ]


def external_results() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = load_json(EXTERNAL)
    generation = data["generation"]["by_method"]
    rows = []
    for method in ["B1_dense_k4", "B4_metapath_k3", "Ours_k3"]:
        r, g = data["methods"][method], generation[method]
        rows.append(
            {
                "Method": METHOD_LABELS[method],
                "Answerable_queries": r["evaluated_answerable_queries"],
                "Recall@B": round(r["recall_at_budget_macro"], 6),
                "MRR": round(r["mrr"], 6),
                "NDCG@B": round(r["ndcg_at_budget_macro"], 6),
                "Silver_P": round(g["silver_citation_precision_macro"], 6),
                "Silver_F1": round(g["silver_citation_f1_macro_answerable"], 6),
                "Answer_rate": round(g["answerable_answer_rate"], 6),
                "Abstain_rate": round(g["unanswerable_abstention_rate"], 6),
                "p95_ms": round(g["end_to_end_inference_latency_ms_p95"], 3),
            }
        )
    return rows, data


def plot_sensitivity(rows: list[dict[str, Any]]) -> None:
    axes = [
        ("K", "K="),
        ("Family cap", "family_cap="),
        ("Source bonus", "source_bonus="),
        ("Redundancy penalty", "redundancy_penalty="),
        ("Graph hops", "graph_hops="),
        ("Graph weight", "graph_weight="),
    ]
    fig, panels = plt.subplots(2, 3, figsize=(12.2, 7.0), constrained_layout=True)
    latency_fig, latency_panels = plt.subplots(2, 3, figsize=(12.2, 7.0), constrained_layout=True)
    for panel, latency_panel, (title, prefix) in zip(
        panels.flat, latency_panels.flat, axes
    ):
        subset = [row for row in rows if row["Setting"].startswith(prefix)]
        if prefix == "K=":
            x = [row["K"] for row in subset]
        elif prefix == "family_cap=":
            x = [row["Family_cap"] for row in subset]
        elif prefix == "source_bonus=":
            x = [row["Source_bonus"] for row in subset]
        elif prefix == "redundancy_penalty=":
            x = [row["Redundancy_penalty"] for row in subset]
        elif prefix == "graph_hops=":
            x = [row["Graph_hops"] for row in subset]
        else:
            x = [row["Graph_weight"] for row in subset]
        panel.plot(x, [row["Recall@B"] for row in subset], "o-", color=COLORS["ours"], label="Recall@B")
        panel.plot(x, [row["NDCG@B"] for row in subset], "s--", color=COLORS["dense"], label="NDCG@B")
        panel.set_title(title)
        panel.set_xlabel("Parameter value")
        panel.set_ylabel("Retrieval quality")
        panel.set_ylim(0, 0.75)
        panel.grid(alpha=0.25)
        latency_panel.plot(
            x,
            [row["p95_retrieval_ms"] for row in subset],
            "^-",
            color=COLORS["latency"],
            label="p95 retrieval latency",
        )
        latency_panel.set_title(title)
        latency_panel.set_xlabel("Parameter value")
        latency_panel.set_ylabel("p95 retrieval latency (ms)")
        latency_panel.set_ylim(0, max(row["p95_retrieval_ms"] for row in subset) * 1.15)
        latency_panel.grid(alpha=0.25)
    panels.flat[0].legend(frameon=False, loc="lower right")
    fig.suptitle("Sensitivity of the proposed retrieval method", fontsize=14)
    latency_fig.suptitle("Retrieval-latency sensitivity", fontsize=14)
    for suffix in ("png", "pdf"):
        fig.savefig(OUT / f"sensitivity_quality.{suffix}", dpi=300, bbox_inches="tight")
        latency_fig.savefig(OUT / f"sensitivity_latency.{suffix}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    plt.close(latency_fig)


def plot_pareto(rows: list[dict[str, Any]]) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 5.2), constrained_layout=True)
    palette = [COLORS["dense"], COLORS["role"], COLORS["ours"]]
    for row, color in zip(rows, palette):
        ax.scatter(row["p95_ms"], row["Utility"], s=110, color=color, edgecolor="white", linewidth=1.2)
        ax.annotate(row["Method"], (row["p95_ms"], row["Utility"]), xytext=(7, 6), textcoords="offset points")
    ax.set_xlabel("End-to-end inference p95 latency (ms, lower is better)")
    ax.set_ylabel("Silver response utility (higher is better)")
    ax.set_title("Quality-latency trade-off under the local 7B generator")
    ax.set_xlim(0, max(row["p95_ms"] for row in rows) * 1.15)
    ax.set_ylim(0, max(row["Utility"] for row in rows) * 1.15)
    ax.grid(alpha=0.25)
    for suffix in ("png", "pdf"):
        fig.savefig(OUT / f"quality_latency_pareto.{suffix}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def freeze_paths() -> list[Path]:
    tracked = git_output("ls-files").splitlines()
    selected: list[Path] = []
    explicit_prefixes = (
        "src/research_point_2/",
        "data/kg/marine_pump/silver_evidencebench/rp2_full_graph_development_v2/",
        "results/experiments/research_point_2/graphrag_v5_2_recall_cascade/",
    )
    explicit_files = {
        "configs/rp2_graphrag_v5_2_recall_cascade.json",
        "configs/rp2_semantic_judge_qwen3_7_max_v5_cascade.json",
        "scripts/run_rp2_recall_cascade_v5_2.py",
        "scripts/run_rp2_recall_cascade_v5_2_server.sh",
        "scripts/run_rp2_dual_prompt_semantic_judge.py",
        "scripts/run_rp2_semantic_judge_v2_secure.sh",
        "scripts/summarize_rp2_v4_targets.py",
        "results/experiments/research_point_2/rp2_v5_2_dual_prompt_semantic_judge/semantic_judge_summary.json",
        "results/experiments/research_point_2/graph_ablation_v1/metrics.json",
        "results/experiments/research_point_2/graphrag_v2_sensitivity_v2/sensitivity_metrics.json",
        "configs/frozen/rp2_v3_frozen_protocol.json",
        "configs/frozen/rp2_v3_external_infrastructure_amendment_v1.json",
        "configs/rp2_graphrag_v3_external_source_heldout.json",
        "results/experiments/research_point_2/graphrag_v3_external_source_heldout/metrics.json",
        "results/experiments/research_point_2/graphrag_v3_external_source_heldout/generation_results.jsonl",
        "results/experiments/research_point_2/graphrag_v3_external_source_heldout/retrieval_results.jsonl",
    }
    for relative in tracked:
        if relative in explicit_files or relative.startswith(explicit_prefixes):
            path = ROOT / relative
            if path.is_file():
                selected.append(path)
    return sorted(set(selected))


def build_freeze_manifest() -> dict[str, Any]:
    base_commit = git_output("rev-parse", "HEAD")
    artifacts = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in freeze_paths()
    ]
    return {
        "freeze_id": "marine_pump_rp2_v5_2_paper_freeze",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": base_commit,
        "protocol_id": "marine_pump_rp2_graphrag_v5_2_recall_cascade",
        "status": "frozen_for_paper_writing_no_further_development_tuning",
        "label_policy": "Silver only; never Gold",
        "human_expert_reviewed": False,
        "development_scope": {
            "queries": 40,
            "answerable_queries": 34,
            "unanswerable_queries": 6,
            "candidate_evidence": 208,
            "heldout_documents_used_for_tuning": False,
        },
        "external_evaluation_scope": {
            "documents": ["MP010", "MP011", "MP012", "MP013"],
            "answerable_queries": 7,
            "interpretation": "descriptive generalization only; no strong significance claim and no feedback to tuning",
        },
        "paper_claim_boundary": {
            "allowed": [
                "significant Silver utility and latency improvement over Dense K4 on the development CQ set",
                "quality point estimate comparable to Role K3 with lower p95 latency",
                "descriptive external-source behavior without tuning feedback",
            ],
            "forbidden": [
                "Gold or expert-verified correctness",
                "significant superiority over Role K3 in answer quality",
                "strong statistical generalization from seven answerable external queries",
                "all internal readiness gates passed",
            ],
        },
        "integrity": {
            "algorithm_or_prompt_changes_after_freeze": "forbidden for reported v5.2 results",
            "result_file_rewriting": "forbidden",
            "derived_tables_and_figures": "must be reproducible from hashed artifacts",
        },
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }


def report(
    main_rows: list[dict[str, Any]],
    ablation_rows: list[dict[str, Any]],
    external_rows: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> str:
    main_view = [
        {
            "Method": row["Method"],
            "Recall@B": fmt(row["Recall@B"]),
            "MRR": fmt(row["MRR"]),
            "NDCG@B": fmt(row["NDCG@B"]),
            "Silver P": fmt(row["Silver_P"]),
            "Silver F1": fmt(row["Silver_F1"]),
            "Norm F1": fmt(row["Norm_F1"]),
            "Utility": fmt(row["Utility"]),
            "Strict point": fmt(row["Strict_point"]),
            "p95 ms": fmt(row["p95_ms"], 1),
        }
        for row in main_rows
    ]
    ablation_view = [
        {
            "Method": row["Method"],
            "Recall@4": fmt(row["Recall@4"]),
            "MRR": fmt(row["MRR"]),
            "NDCG@4": fmt(row["NDCG@4"]),
            "Families": fmt(row["Source_families"]),
            "p95 ms": fmt(row["p95_retrieval_ms"]),
        }
        for row in ablation_rows
    ]
    external_view = [
        {
            "Method": row["Method"],
            "Answerable": row["Answerable_queries"],
            "Recall@B": fmt(row["Recall@B"]),
            "NDCG@B": fmt(row["NDCG@B"]),
            "Silver F1": fmt(row["Silver_F1"]),
            "p95 ms": fmt(row["p95_ms"], 1),
        }
        for row in external_rows
    ]
    dense = metrics["budget_effectiveness"]["cascade_ours_vs_dense_k4"]["comparisons"][0]
    role = metrics["budget_effectiveness"]["cascade_same_budget_vs_role_k3"]["comparisons"][0]
    return f"""# RP2 v5.2 冻结实验包与论文结果说明

本目录只包含由冻结结果确定性生成的论文表格和图。所有事实标签均为 Silver，未经过领域专家人工审核，不得表述为 Gold 或专家确认正确率。

## 1. 冻结边界

- 开发评价：40个受控能力查询，其中34个可回答、6个不可回答。
- 最终协议：紧凑第一阶段判别 + 第一阶段0候选的独立召回复核，三方法采用同一复核器。
- 时延协议：三次轮换交错执行，逐查询取中位数后统计方法p95。
- 冻结后不再根据开发集修改提示词、阈值、图检索参数或评价规则。
- 标签政策：Silver only; never Gold。

## 2. 主实验

{markdown_table(list(main_view[0]), main_view)}

Ours K3相对Dense K4的Silver回答效用差为{dense['silver_utility_delta']:.3f}，配对Bootstrap 95% CI为[{dense['silver_utility_delta_bootstrap_95ci'][0]:.3f}, {dense['silver_utility_delta_bootstrap_95ci'][1]:.3f}]；p95端到端时延减少{-dense['end_to_end_p95_latency_delta_ms']:.1f} ms。该比较支持相对Dense的质量提升与时延优势。

Ours K3相对Role K3的效用点估计提高{role['silver_utility_delta']:.3f}，但95% CI为[{role['silver_utility_delta_bootstrap_95ci'][0]:.3f}, {role['silver_utility_delta_bootstrap_95ci'][1]:.3f}]，跨越0。因此论文只能表述为“质量点估计相当、时延更低”，不能声称回答质量显著优于Role K3。

![质量—时延Pareto图](quality_latency_pareto.png)

## 3. 检索消融

{markdown_table(list(ablation_view[0]), ablation_view)}

消融实验属于检索层评价，采用早期冻结的K=4协议，不与v5.2生成层数值混合计算。其作用是解释候选索引、角色门控、来源族约束和冗余控制分别影响召回、排序、来源多样性与检索时延。

## 4. 敏感性分析

敏感性实验覆盖K、来源族上限、来源奖励、冗余惩罚、图跳数和图权重六个参数。曲线同时报告Recall@B、NDCG@B和检索p95时延，用于展示参数变化的趋势，不用于在冻结后重新选择参数。

![敏感性质量曲线](sensitivity_quality.png)

![敏感性时延曲线](sensitivity_latency.png)

## 5. 外部来源描述性验证

{markdown_table(list(external_view[0]), external_view)}

MP010—MP013在开发协议冻结后才进入外部评价，不回流提示词、阈值或检索参数。外部集合只有7个可回答查询，因此上述数值仅用于描述无回流条件下的泛化行为，不用于强显著性推断。

## 6. 论文可用结论与限制

可用结论：在相同本地7B生成器下，Ours K3相对Dense K4取得更高的Silver回答效用和更低的端到端p95时延；相对Role K3保持相近的回答质量点估计，同时降低时延。双提示语义Judge用于Silver忠实性审计，不等同于专家事实核验。

必须披露的限制：Silver标签、40个开发CQ、外部可回答查询仅7个、Ours与Role K3质量差异未达到统计显著、内部预算归一化F1目标未完全达到。
"""


def main() -> int:
    required = [V52 / "metrics.json", V52 / "paper_readiness_targets.json", JUDGE, ABLATION, SENSITIVITY, EXTERNAL]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing frozen inputs: {missing}")
    OUT.mkdir(parents=True, exist_ok=True)
    FREEZE.parent.mkdir(parents=True, exist_ok=True)
    for legacy_name in (
        "sensitivity_curves.png",
        "sensitivity_curves.svg",
        "quality_latency_pareto.svg",
        "sensitivity_quality.svg",
        "sensitivity_latency.svg",
    ):
        legacy = OUT / legacy_name
        if legacy.is_file():
            legacy.unlink()

    main_rows, metrics = main_results()
    ablation_rows = ablation_results()
    sensitivity_rows = sensitivity_results()
    external_rows, _ = external_results()

    write_csv(OUT / "table_main_results.csv", main_rows, list(main_rows[0]))
    write_csv(OUT / "table_ablation.csv", ablation_rows, list(ablation_rows[0]))
    write_csv(OUT / "table_sensitivity.csv", sensitivity_rows, list(sensitivity_rows[0]))
    write_csv(OUT / "table_external_descriptive.csv", external_rows, list(external_rows[0]))
    plot_sensitivity(sensitivity_rows)
    plot_pareto(main_rows)
    (OUT / "EXPERIMENT_REPORT.md").write_text(
        report(main_rows, ablation_rows, external_rows, metrics), encoding="utf-8"
    )
    freeze = build_freeze_manifest()
    FREEZE.write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[RP2 paper package] output={OUT.relative_to(ROOT)}")
    print(f"[RP2 paper package] frozen artifacts={freeze['artifact_count']}")
    print(f"[RP2 paper package] source commit={freeze['source_commit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
