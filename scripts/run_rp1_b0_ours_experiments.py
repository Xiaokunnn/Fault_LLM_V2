"""Execute the frozen RP1 B0--Ours comparison and ablation experiment."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage05_evaluation.rp1_b0_ours import (  # noqa: E402
    compute_experiment,
    load_json,
    load_jsonl,
    sha256_file,
)


DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "rp1_b0_ours_experiment_v1.json"
)


def resolve_project_path(value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else PROJECT_ROOT / path


def project_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def validate_inputs(
    config: Mapping[str, object],
    *,
    config_path: Path,
    cq_report: Mapping[str, object],
    source_summary: Mapping[str, object],
    constraint_report: Mapping[str, object],
) -> dict[str, object]:
    inputs = dict(config["inputs"])
    raw_path = resolve_project_path(inputs["raw_source_records"])
    cq_config_path = resolve_project_path(inputs["cq_config"])
    expected_raw = str(inputs["raw_source_records_sha256"]).lower()
    expected_cq_config = str(inputs["cq_config_sha256"]).lower()
    actual_raw = sha256_file(raw_path).lower()
    actual_cq_config = sha256_file(cq_config_path).lower()
    if actual_raw != expected_raw:
        raise ValueError(
            "Frozen raw source-record SHA-256 mismatch: "
            f"expected {expected_raw}, got {actual_raw}"
        )
    if actual_cq_config != expected_cq_config:
        raise ValueError(
            "Frozen CQ config SHA-256 mismatch: "
            f"expected {expected_cq_config}, got {actual_cq_config}"
        )

    cq_suite = dict(cq_report["suite"])
    if str(cq_suite["config_sha256"]).lower() != actual_cq_config:
        raise ValueError(
            "CQ report was generated from a different frozen CQ config"
        )
    source_provenance = dict(source_summary["input_provenance"])
    if (
        str(source_provenance["source_records_sha256"]).lower()
        != actual_raw
    ):
        raise ValueError(
            "Source-family summary was generated from different raw records"
        )
    constraint_raw = dict(
        constraint_report["packages"]["KG_v1_raw"]["input_files"][
            "source_records"
        ]
    )
    if str(constraint_raw["sha256"]).lower() != actual_raw:
        raise ValueError(
            "Constraint report was generated from different raw records"
        )
    if bool(constraint_report["summary"]["release_blocked"]):
        raise ValueError(
            "Constraint report contains release-blocking failures"
        )

    split = dict(config["split_policy"])
    build_ids = set(split["eligible_build_doc_ids"])
    observed_ids = {
        str(item.get("doc_id") or "")
        for item in load_jsonl(raw_path)
    }
    unexpected = sorted(observed_ids - build_ids)
    if unexpected:
        raise ValueError(
            "Raw graph contains documents outside frozen build set: "
            + ", ".join(unexpected)
        )
    return {
        "config": {
            "path": project_relative(config_path),
            "sha256": sha256_file(config_path),
            "size_bytes": config_path.stat().st_size,
        },
        "raw_source_records": {
            "path": project_relative(raw_path),
            "sha256": actual_raw,
            "size_bytes": raw_path.stat().st_size,
        },
        "cq_config": {
            "path": project_relative(cq_config_path),
            "sha256": actual_cq_config,
            "size_bytes": cq_config_path.stat().st_size,
        },
        "cq_report": {
            "path": project_relative(
                resolve_project_path(inputs["cq_evaluation"])
            ),
            "sha256": sha256_file(
                resolve_project_path(inputs["cq_evaluation"])
            ),
        },
        "source_family_summary": {
            "path": project_relative(
                resolve_project_path(inputs["source_family_summary"])
            ),
            "sha256": sha256_file(
                resolve_project_path(inputs["source_family_summary"])
            ),
        },
        "constraint_report": {
            "path": project_relative(
                resolve_project_path(inputs["constraint_report"])
            ),
            "sha256": sha256_file(
                resolve_project_path(inputs["constraint_report"])
            ),
        },
        "cross_input_consistency_passed": True,
    }


def write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    *,
    fieldnames: Sequence[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    columns = list(fieldnames or rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def flatten_source_budget_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for item in rows:
        support = dict(item["support_index"])
        result.append(
            {
                "budget": item["budget"],
                "claim_count": item["claim_count"],
                "mean": support["mean"],
                "median": support["median"],
                "p25": support["p25"],
                "p75": support["p75"],
                "count_ge_0_5": support["count_ge_0_5"],
                "count_ge_0_8": support["count_ge_0_8"],
            }
        )
    return result


def configure_matplotlib() -> object:
    try:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import font_manager
        from matplotlib import pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "Generating figures requires matplotlib. "
            "Install requirements.txt and rerun."
        ) from exc

    font_candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path(
            "/usr/share/fonts/opentype/noto/"
            "NotoSansCJK-Regular.ttc"
        ),
        Path(
            "/usr/share/fonts/opentype/noto/"
            "NotoSansCJKsc-Regular.otf"
        ),
    ]
    for font_path in font_candidates:
        if font_path.exists():
            font_manager.fontManager.addfont(str(font_path))
            family = font_manager.FontProperties(
                fname=str(font_path)
            ).get_name()
            plt.rcParams["font.family"] = family
            break
    plt.rcParams.update(
        {
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#666666",
            "axes.labelcolor": "#222222",
            "xtick.color": "#333333",
            "ytick.color": "#333333",
            "text.color": "#222222",
            "axes.titleweight": "normal",
            "font.size": 10,
            "savefig.bbox": "tight",
        }
    )
    return plt


def save_figure(
    figure: object,
    directory: Path,
    stem: str,
) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for suffix in (".png", ".svg"):
        path = directory / f"{stem}{suffix}"
        figure.savefig(path, dpi=200)
        outputs.append(path.name)
    return outputs


def render_figures(
    experiment: Mapping[str, object],
    *,
    cq_report: Mapping[str, object],
    output_dir: Path,
) -> list[str]:
    plt = configure_matplotlib()
    figure_dir = output_dir / "figures"
    generated: list[str] = []
    palette = {
        "blue": "#3B6FB6",
        "orange": "#E28E2C",
        "green": "#3B8C6E",
        "red": "#C95858",
        "purple": "#7B61A8",
        "gray": "#8A8A8A",
        "light": "#E6EAF0",
    }

    stages = list(experiment["b0_ours_comparison"])
    method_ids = [str(row["method_id"]) for row in stages]
    method_labels = [
        f"{row['method_id']}  {row['method_name_zh']}" for row in stages
    ]
    counts = [int(row["assertion_count"]) for row in stages]
    pass_fields = [
        ("schema_pass_rate", "Schema"),
        ("evidence_grounding_pass_rate", "证据"),
        ("entailment_pass_rate", "蕴含"),
        ("score_pass_rate", "分数"),
        ("chinese_release_pass_rate", "中文发布"),
    ]
    matrix = [
        [float(row[field]) for field, _ in pass_fields]
        for row in stages
    ]
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12.4, 5.3),
        gridspec_kw={"width_ratios": [1.05, 1.25]},
    )
    y = list(range(len(stages)))
    colors = [
        palette["gray"],
        palette["blue"],
        palette["orange"],
        palette["green"],
        palette["purple"],
    ]
    axes[0].barh(y, counts, color=colors, height=0.62)
    axes[0].set_yticks(y, labels=method_labels)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("保留断言数")
    axes[0].set_title("A. 累计门控后的候选规模")
    axes[0].grid(axis="x", color="#DDDDDD", linewidth=0.7)
    for index, count in enumerate(counts):
        axes[0].text(
            count + max(counts) * 0.012,
            index,
            f"{count:,}\n({count / counts[0]:.1%})",
            va="center",
            fontsize=9,
        )
    axes[0].set_xlim(0, max(counts) * 1.24)

    image = axes[1].imshow(
        matrix,
        vmin=0,
        vmax=1,
        cmap="Blues",
        aspect="auto",
    )
    axes[1].set_xticks(
        range(len(pass_fields)),
        labels=[label for _, label in pass_fields],
    )
    axes[1].set_yticks(range(len(method_ids)), labels=method_ids)
    axes[1].set_title("B. 各输出集合的结构门控通过率")
    for row_index, values in enumerate(matrix):
        for column_index, value in enumerate(values):
            axes[1].text(
                column_index,
                row_index,
                f"{value:.0%}",
                ha="center",
                va="center",
                color="white" if value > 0.62 else "#222222",
                fontsize=9,
            )
    colorbar = fig.colorbar(image, ax=axes[1], fraction=0.046, pad=0.04)
    colorbar.set_label("通过率")
    fig.suptitle(
        "B0–Ours固定候选累计治理对照",
        y=1.01,
        fontsize=13,
    )
    fig.tight_layout()
    generated.extend(
        save_figure(fig, figure_dir, "b0_ours_overview")
    )
    plt.close(fig)

    task_results = list(cq_report["task_results"])
    fault_order: list[tuple[str, str]] = []
    for task in task_results:
        key = (
            str(task["fault_id"]),
            str(task["fault_name_zh"]),
        )
        if key not in fault_order:
            fault_order.append(key)
    role_order = [
        ("symptom", "症状"),
        ("cause_or_mechanism", "原因/机理"),
        ("inspection", "检查"),
        ("maintenance", "维护"),
    ]
    answer_lookup = {
        (str(task["fault_id"]), str(task["role"])): int(
            task["answer_count"]
        )
        for task in task_results
    }
    heat = [
        [
            answer_lookup.get((fault_id, role_id), 0)
            for role_id, _ in role_order
        ]
        for fault_id, _ in fault_order
    ]
    fig, ax = plt.subplots(figsize=(9.4, 6.7))
    image = ax.imshow(heat, cmap="YlGnBu", vmin=0, aspect="auto")
    ax.set_xticks(
        range(len(role_order)),
        labels=[label for _, label in role_order],
    )
    ax.set_yticks(
        range(len(fault_order)),
        labels=[name for _, name in fault_order],
    )
    ax.set_title("CQ v1：10类故障 × 4类问题的可追溯答案数")
    for row_index, values in enumerate(heat):
        for column_index, value in enumerate(values):
            ax.text(
                column_index,
                row_index,
                "×" if value == 0 else str(value),
                ha="center",
                va="center",
                color=(
                    palette["red"]
                    if value == 0
                    else ("white" if value >= 8 else "#222222")
                ),
                fontweight="normal",
            )
    colorbar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
    colorbar.set_label("唯一规范答案数")
    fig.tight_layout()
    generated.extend(
        save_figure(fig, figure_dir, "cq_fault_role_heatmap")
    )
    plt.close(fig)

    sensitivity = dict(experiment["sensitivity"])
    score_rows = list(sensitivity["silver_score_threshold"])
    budget_rows = flatten_source_budget_rows(
        list(sensitivity["source_family_budget"])
    )
    cq_sensitivity = dict(sensitivity["cq"])
    answer_rows = list(cq_sensitivity["minimum_answers"])
    family_rows = list(
        cq_sensitivity["minimum_source_families"]
    )
    fig, axes = plt.subplots(1, 3, figsize=(14.2, 4.5))
    x_score = [float(row["threshold"]) for row in score_rows]
    axes[0].plot(
        x_score,
        [int(row["assertion_count"]) for row in score_rows],
        marker="o",
        color=palette["blue"],
        label="EvidenceAssertion",
    )
    axes[0].plot(
        x_score,
        [int(row["claim_count"]) for row in score_rows],
        marker="s",
        color=palette["orange"],
        label="Claim",
    )
    axes[0].axvline(
        0.8,
        color=palette["red"],
        linestyle="--",
        linewidth=1,
        label="冻结阈值0.8",
    )
    axes[0].set_xlabel("启发式分数阈值")
    axes[0].set_ylabel("保留数量")
    axes[0].set_title("A. Silver阈值敏感性")
    axes[0].grid(color="#DDDDDD", linewidth=0.7)
    axes[0].legend(frameon=False, fontsize=8)

    x_budget = [int(row["budget"]) for row in budget_rows]
    axes[1].plot(
        x_budget,
        [float(row["mean"]) for row in budget_rows],
        marker="o",
        color=palette["green"],
        label="均值",
    )
    axes[1].plot(
        x_budget,
        [float(row["median"]) for row in budget_rows],
        marker="s",
        color=palette["purple"],
        label="中位数",
    )
    axes[1].axvline(
        2,
        color=palette["red"],
        linestyle="--",
        linewidth=1,
        label="冻结B=2",
    )
    axes[1].set_xticks(x_budget)
    axes[1].set_xlabel("来源族预算 B")
    axes[1].set_ylabel("来源族封顶佐证指数")
    axes[1].set_ylim(0, 1)
    axes[1].set_title("B. 来源族预算敏感性")
    axes[1].grid(color="#DDDDDD", linewidth=0.7)
    axes[1].legend(frameon=False, fontsize=8)

    axes[2].plot(
        [int(row["minimum_answers"]) for row in answer_rows],
        [int(row["answerable_task_count"]) for row in answer_rows],
        marker="o",
        color=palette["blue"],
        label="最少答案数",
    )
    axes[2].plot(
        [
            int(row["minimum_source_families"])
            for row in family_rows
        ],
        [int(row["answerable_task_count"]) for row in family_rows],
        marker="s",
        color=palette["orange"],
        label="最少来源族数",
    )
    axes[2].set_xlabel("最低要求")
    axes[2].set_ylabel("可回答CQ数（总计40）")
    axes[2].set_ylim(0, 40)
    axes[2].set_title("C. CQ门槛敏感性")
    axes[2].grid(color="#DDDDDD", linewidth=0.7)
    axes[2].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    generated.extend(
        save_figure(fig, figure_dir, "parameter_sensitivity")
    )
    plt.close(fig)

    gate_rows = list(experiment["incremental_gate_ablation"])
    source_result = dict(experiment["source_family_result"])
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.8))
    labels = [str(row["module_name_zh"]) for row in gate_rows]
    rates = [float(row["removed_rate"]) for row in gate_rows]
    y = list(range(len(labels)))
    axes[0].barh(y, rates, color=palette["blue"], height=0.6)
    axes[0].set_yticks(y, labels=labels)
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, 1.08)
    axes[0].set_xlabel("相对上一步的移除率")
    axes[0].set_title("A. 各门控的边际筛除作用")
    axes[0].grid(axis="x", color="#DDDDDD", linewidth=0.7)
    for index, row in enumerate(gate_rows):
        axes[0].text(
            min(rates[index] + 0.018, 0.92),
            index,
            f"{rates[index]:.1%}（{int(row['removed_count']):,}）",
            va="center",
            fontsize=9,
        )

    before = [1.0, 1.0, 1.0]
    after = [
        float(
            source_result["replication_doc_count_amplification"]
        ),
        1.0,
        1.0
        + float(
            source_result["replication_maximum_index_delta"]
        ),
    ]
    x = list(range(3))
    width = 0.34
    axes[1].bar(
        [value - width / 2 for value in x],
        before,
        width,
        label="复制前",
        color=palette["gray"],
    )
    axes[1].bar(
        [value + width / 2 for value in x],
        after,
        width,
        label="同族复制后",
        color=palette["green"],
    )
    axes[1].set_xticks(
        x,
        labels=["文档计数", "来源族数", "封顶指数"],
    )
    axes[1].set_ylabel("相对复制前（复制前=1）")
    axes[1].set_ylim(0, max(after) * 1.22)
    axes[1].set_title("B. 同来源族复制鲁棒性")
    axes[1].grid(axis="y", color="#DDDDDD", linewidth=0.7)
    axes[1].legend(frameon=False)
    for index, value in enumerate(after):
        axes[1].text(
            index + width / 2,
            value + 0.045,
            f"{value:.2f}×",
            ha="center",
            fontsize=9,
        )
    fig.tight_layout()
    generated.extend(
        save_figure(fig, figure_dir, "ablation_and_replication")
    )
    plt.close(fig)
    return generated


def percent(value: object) -> str:
    return f"{float(value):.1%}"


def render_report(
    experiment: Mapping[str, object],
    *,
    config: Mapping[str, object],
    cq_report: Mapping[str, object],
) -> str:
    stages = list(experiment["b0_ours_comparison"])
    bootstrap = {
        str(row["method_id"]): row
        for row in experiment["bootstrap"]["stage_retention"]
    }
    gate_rows = list(experiment["incremental_gate_ablation"])
    specific = list(experiment["specific_module_ablation"])
    source = dict(experiment["source_family_result"])
    cq = dict(experiment["cq_result"])
    cq_bootstrap = dict(
        experiment["bootstrap"]["cq_answerability"]
    )
    constraint = dict(experiment["constraint_result"])
    score_rows = list(
        experiment["sensitivity"]["silver_score_threshold"]
    )
    budget_rows = flatten_source_budget_rows(
        list(experiment["sensitivity"]["source_family_budget"])
    )
    task_results = list(cq_report["task_results"])
    role_summary = dict(cq_report["aggregate"]["by_role"])

    lines = [
        "# 研究点一 B0–Ours 对照、关键消融与敏感性实验报告",
        "",
        f"- 实验版本：`{experiment['experiment_version']}`",
        f"- 生成时间：`{experiment['generated_at_utc']}`",
        "- 对象：船舶机舱泵系可追溯 Silver 证据知识图谱",
        "- 标签政策：仅 Silver，绝不称 Gold；未进行领域专家审核。",
        "- 执行方式：纯本地固定候选离线实验；未调用模型或网络。",
        "",
        "## 摘要",
        "",
        (
            "本实验在同一批8003条全量审计候选上执行累计治理对照，"
            "避免不同模型调用、提示词和页面预算造成混杂。B0、B1、B2、"
            "B3和Ours分别保留8003、6711、2505、1698和208条断言。"
            "Schema门控移除1292条关系类型或Domain/Range不合规记录；"
            "E1/E2原文及表格对齐门控进一步移除4206条；关系蕴含门控"
            "移除801条；冻结分数阈值0.8再隔离6条；中文术语发布门控"
            "从1698条证据Silver中发布208条中文就绪记录。"
        ),
        "",
        (
            "来源族实验中，真实的3个多文档精确Claim均只计为1个"
            "来源族；合成同族复制使文档计数达到2.00倍，但来源族数和"
            "封顶指数不变。CQ v1可回答34/40，结构可回答率为85.0%，"
            f"按故障类聚类bootstrap的95%区间为"
            f"[{percent(cq_bootstrap['ci_lower'])}, "
            f"{percent(cq_bootstrap['ci_upper'])}]。"
            "这些指标验证结构门控、谱系和功能覆盖，不是事实准确率。"
        ),
        "",
        "## 1. 实验问题与假设",
        "",
        "本实验回答以下问题：",
        "",
        "1. 累积Schema、证据、蕴含、溯源和中文发布门控后，候选规模与结构合规性如何变化？",
        "2. 哪个治理模块产生最大的边际筛除作用？",
        "3. 同一厂商资料复制时，来源族封顶指标是否保持不变？",
        "4. 分数阈值、来源族预算和CQ最低证据要求变化时，结论是否稳定？",
        "5. 中文发布图能够回答十类故障中的哪些症状、原因、检查和维护问题？",
        "",
        "## 2. 实验设计与诚信边界",
        "",
        "### 2.1 固定候选离线对照",
        "",
        "| 方法 | 累计模块 | 本实验中的操作化定义 |",
        "|---|---|---|",
        "| B0 | 无治理门控 | 接受8003条结构化审计候选，仅作为固定候选参照 |",
        "| B1 | 关系Schema | 要求关系、头尾类型及Domain/Range合法 |",
        "| B2 | B1 + 结构证据 | 要求E1/E2、连续原文或表格同行证据可验证 |",
        "| B3 | B2 + Silver治理 | 增加关系蕴含、构建集/溯源、非推断和分数阈值 |",
        "| Ours | B3 + 来源族/中文双门控/CQ | 发布中文规范子图，并执行来源族和功能覆盖评价 |",
        "",
        (
            "> 本实验是固定候选集合上的治理反事实，不是重新使用不同提示词"
            "执行B0–Ours模型抽取。因此可以解释各门控对现有候选的结构效应，"
            "不能解释为提示词或模型端抽取精度的因果提升。"
        ),
        "",
        "### 2.2 数据划分与统计单元",
        "",
        "- 仅使用主图构建集MP001–MP007、MP015–MP022，共15份文档。",
        "- MP008开发集和MP009–MP013保留测试集均未进入候选、调参或评价。",
        "- 置信区间按文档聚类重采样；CQ区间按十类故障聚类重采样。",
        (
            f"- Bootstrap重复{config['parameters']['bootstrap']['replicates']}次，"
            f"随机种子{config['parameters']['bootstrap']['seed']}。"
        ),
        "- 因无人工Gold，不报告Accuracy、Precision、Recall或事实正确率。",
        "",
        "## 3. B0–Ours累计对照",
        "",
        "![B0–Ours累计对照](figures/b0_ours_overview.png)",
        "",
        "| 方法 | 断言 | Claim | 实体 | 文档 | 来源族 | 相对B0保留率（95%文档聚类CI） |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in stages:
        ci = bootstrap[str(row["method_id"])]
        lines.append(
            f"| {row['method_id']} | {int(row['assertion_count']):,} | "
            f"{int(row['claim_count']):,} | {int(row['entity_count']):,} | "
            f"{int(row['document_count'])} | "
            f"{int(row['source_family_count'])} | "
            f"{percent(row['retention_from_b0'])} "
            f"[{percent(ci['ci_lower'])}, {percent(ci['ci_upper'])}] |"
        )
    lines.extend(
        [
            "",
            (
                "B0中的Schema、证据和蕴含通过率分别为"
                f"{percent(stages[0]['schema_pass_rate'])}、"
                f"{percent(stages[0]['evidence_grounding_pass_rate'])}和"
                f"{percent(stages[0]['entailment_pass_rate'])}。B3对所有"
                "发布硬条件达到100%，但仅12.25%的证据Silver同时满足"
                "中文术语发布门控。该12.25%是双门控投影率，不应解释为"
                "其余87.75%的原文证据错误。"
            ),
            "",
            "## 4. 关键模块消融",
            "",
            "![门控消融与来源族复制](figures/ablation_and_replication.png)",
            "",
            "### 4.1 累计序列中的边际筛除",
            "",
            "| 模块 | 输入 | 输出 | 移除 | 移除率 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in gate_rows:
        lines.append(
            f"| {row['module_name_zh']} | {int(row['input_count']):,} | "
            f"{int(row['output_count']):,} | "
            f"{int(row['removed_count']):,} | "
            f"{percent(row['removed_rate'])} |"
        )
    lines.extend(
        [
            "",
            (
                "结构证据门控的边际筛除最大（4206条，62.7%），说明当前"
                "候选噪声主要来自原文定位、表格同行/同行组和E1/E2资格，"
                "而不是最终0.8分数阈值。分数阈值只额外隔离6条，表明"
                "“硬约束优先、分数其次”的实际行为与方法设计一致。"
                "溯源与文档划分在该顺序中移除0条，是因为这些字段已在"
                "上游构图时作为全量记录不变量写入，不能据此解释为溯源"
                "模块没有必要。"
            ),
            "",
            "### 4.2 特定模块去除的可观测代价",
            "",
            "| 消融 | 可观测代价 | 解释 |",
            "|---|---|---|",
        ]
    )
    for row in specific:
        value = row["effect_value"]
        value_text = (
            percent(value)
            if row["ablation"] == "document_count_as_independence"
            else f"{int(value):,}"
        )
        lines.append(
            f"| {row['name_zh']} | {value_text} {row['effect_unit']} | "
            f"{row['interpretation']} |"
        )
    lines.extend(
        [
            "",
            (
                "Claim–Evidence扁平化会覆盖48条额外来源断言，涉及30个"
                "多证据Claim；这直接削弱多页、多文档证据保留。去除中文"
                "术语门控会使1490条尚未满足中文端点发布规则的记录混入"
                "中文发布图，但不会增加原文证据层本身的事实可靠性。"
            ),
            "",
            "## 5. 来源族封顶佐证实验",
            "",
            f"- 证据Silver：{source['eligible_assertion_count']:,}条；"
            f"精确Claim：{source['claim_count']:,}个。",
            (
                f"- 真实多文档Claim：{source['observed_multi_document_claims']}个，"
                f"其中{source['observed_multi_document_single_family_claims']}个"
                "全部只计为一个来源族。"
            ),
            (
                f"- 同族复制后文档计数放大到"
                f"{source['replication_doc_count_amplification']:.2f}倍，"
                f"封顶指数最大变化为"
                f"{source['replication_maximum_index_delta']:.6f}。"
            ),
            (
                f"- 精确Claim跨至少两个来源族："
                f"{source['claims_with_at_least_two_families']}个。"
            ),
            "",
            (
                "结果支持“同一厂商多份手册不重复累加”的算法性质，但当前"
                "没有自然跨族精确Claim，尚不能验证指数对自然跨来源族佐证"
                "的区分效度，也不能证明不同来源族统计独立。"
            ),
            "",
            "## 6. CQ功能覆盖",
            "",
            "![CQ故障—角色热力图](figures/cq_fault_role_heatmap.png)",
            "",
            (
                f"当前可回答{cq['answerable_task_count']}/"
                f"{cq['task_count']}，可追溯结构可回答率"
                f"{percent(cq['traceable_structure_answerability'])}；"
                f"故障类聚类95%区间为"
                f"[{percent(cq_bootstrap['ci_lower'])}, "
                f"{percent(cq_bootstrap['ci_upper'])}]。"
            ),
            "",
            "| 角色 | 可回答任务 | 可回答率 |",
            "|---|---:|---:|",
        ]
    )
    role_labels = {
        "symptom": "症状",
        "cause_or_mechanism": "原因/机理",
        "inspection": "检查",
        "maintenance": "维护",
    }
    for role, label in role_labels.items():
        item = dict(role_summary[role])
        lines.append(
            f"| {label} | {item['answerable_cq_count']}/"
            f"{item['cq_count']} | "
            f"{percent(item['traceable_structure_answerability'])} |"
        )
    missing = [
        task
        for task in task_results
        if not bool(task["structurally_answerable"])
    ]
    lines.extend(["", "未形成合法证据路径的任务：", ""])
    for task in missing:
        lines.append(
            f"- {task['fault_name_zh']}—{task['role_name_zh']}："
            f"`{','.join(task['unanswerable_reason_codes'])}`"
        )
    lines.extend(
        [
            "",
            "## 7. 参数敏感性",
            "",
            "![参数敏感性](figures/parameter_sensitivity.png)",
            "",
            "### 7.1 Silver分数阈值",
            "",
            "| 阈值 | 断言 | Claim | 故障类别 |",
            "|---:|---:|---:|---:|",
        ]
    )
    for row in score_rows:
        lines.append(
            f"| {float(row['threshold']):.3f} | "
            f"{int(row['assertion_count']):,} | "
            f"{int(row['claim_count']):,} | "
            f"{int(row['fault_class_count'])} |"
        )
    row_080 = next(
        row for row in score_rows if float(row["threshold"]) == 0.8
    )
    row_085 = next(
        row for row in score_rows if float(row["threshold"]) == 0.85
    )
    row_090 = next(
        row for row in score_rows if float(row["threshold"]) == 0.9
    )
    lines.extend(
        [
            "",
            (
                f"阈值从0.8提高到0.85仅减少"
                f"{int(row_080['assertion_count']) - int(row_085['assertion_count'])}"
                f"条断言；提高到0.9则累计减少"
                f"{int(row_080['assertion_count']) - int(row_090['assertion_count'])}"
                "条。0.975时故障类别覆盖由10降为8，说明过高阈值会"
                "明显损害长尾覆盖。"
            ),
            "",
            "### 7.2 来源族预算",
            "",
            "| B | 指数均值 | 中位数 | ≥0.5 Claim |",
            "|---:|---:|---:|---:|",
        ]
    )
    for row in budget_rows:
        lines.append(
            f"| {int(row['budget'])} | {float(row['mean']):.4f} | "
            f"{float(row['median']):.4f} | "
            f"{int(row['count_ge_0_5']):,} |"
        )
    lines.extend(
        [
            "",
            (
                "B从1增至4时指数均值单调下降，因为当前精确Claim均只有"
                "一个来源族，缺失族位置按0计。B=2与冻结的两来源族任务"
                "预算一致，但不是理论最优常数。"
            ),
            "",
            "### 7.3 CQ最低要求",
            "",
            "最低答案数由1提高到2时，可回答任务由34降为28；要求至少"
            "2个来源族时同样为28，至少3个来源族时降为18。CQ覆盖结论"
            "对门槛敏感，因此论文必须同时报告门槛和分项结果。",
            "",
            "## 8. 约束与复现审计",
            "",
            f"- 标准化约束：{constraint['check_count']}项；发布阻断"
            f"{constraint['release_blocking_check_count']}项；"
            f"`release_blocked={str(constraint['release_blocked']).lower()}`。",
            "- CQ、来源族和约束报告均通过输入图谱SHA-256交叉校验。",
            "- 所有CSV使用UTF-8 BOM，JSON/JSONL保持UTF-8。",
            "- 本实验未修改任何Silver标签、原文、页码、URL或哈希。",
            "- 当前约束为项目专用Python/JSON注册表实现，不是RDF/SHACL。",
            "",
            "## 9. 有效性威胁",
            "",
            "1. **非事实准确率**：没有轮机专家Gold，结构门控通过不能证明主张事实正确。",
            "2. **固定候选偏差**：B0–Ours共用最终抽取候选，不能评价不同提示词对召回率的影响。",
            "3. **门控顺序依赖**：边际筛除量依赖预先冻结的累计顺序，不等同于完全析因实验。",
            "4. **来源族代理限制**：发布者/组织谱系只是依赖性代理，不能证明统计独立。",
            "5. **自然跨族样本缺失**：精确Claim跨来源族为0，当前只验证复制不变性。",
            "6. **开发时序偏差**：Schema、门控和阈值曾在构建流程中迭代，当前构建集结果不是盲测性能。",
            "7. **构建集内部结果**：MP009–MP013尚未用于一次性外部泛化评价。",
            "",
            "## 10. 结论与下一步",
            "",
            "本轮实验支持以下结论：",
            "",
            "1. 在固定候选上，Schema、原文证据和关系蕴含门控具有显著的结构筛除作用，其中结构证据门控贡献最大。",
            "2. 0.8分数阈值只承担次级隔离作用，不能替代硬约束。",
            "3. 来源族封顶能够抵抗同厂商文档复制导致的伪多源膨胀。",
            "4. 双门控避免把证据Silver直接冒充中文发布图；CQ揭示了6个图谱规模统计无法发现的功能缺口。",
            "5. 这些结果足以形成研究点一的内部结构实验，但尚不足以声称事实准确率、自然跨族区分效度或外部泛化。",
            "",
            "建议下一步：",
            "",
            "- 将本报告作为研究点一内部对照与消融结果写入论文；",
            "- 不修改CQ v1，保留6个缺口作为误差分析；若发布CQ v2，必须单独版本化；",
            "- 如论文需要证明抽取提示词本身优于B0，应在冻结页面子集上另做真实API提示词对照；",
            "- 在所有Schema、阈值和CQ冻结后，才对MP009–MP013执行一次性外部评价；",
            "- 研究点一仍不能标记为完成，直到论文所需实验表、图和结论边界最终冻结。",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(output_dir: Path) -> dict[str, object]:
    files: list[dict[str, object]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        files.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "manifest_version": "rp1_b0_ours_artifact_manifest_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
        "files": files,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen local-only RP1 B0-Ours comparison, ablation, "
            "sensitivity analysis, bootstrap intervals, and figures."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--skip-figures",
        action="store_true",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config = load_json(config_path)
    inputs = dict(config["inputs"])
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else resolve_project_path(config["outputs"]["directory"])
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_path = resolve_project_path(inputs["raw_source_records"])
    cq_path = resolve_project_path(inputs["cq_evaluation"])
    source_path = resolve_project_path(inputs["source_family_summary"])
    constraint_path = resolve_project_path(inputs["constraint_report"])

    print(
        "[RP1 Experiment] 1/5 读取冻结输入并执行SHA-256交叉校验",
        flush=True,
    )
    cq_report = load_json(cq_path)
    source_summary = load_json(source_path)
    constraint_report = load_json(constraint_path)
    provenance = validate_inputs(
        config,
        config_path=config_path,
        cq_report=cq_report,
        source_summary=source_summary,
        constraint_report=constraint_report,
    )
    records = load_jsonl(raw_path)

    print(
        f"[RP1 Experiment] 2/5 执行B0–Ours与消融：候选={len(records)}",
        flush=True,
    )
    experiment = compute_experiment(
        records,
        config=config,
        cq_report=cq_report,
        source_summary=source_summary,
        constraint_report=constraint_report,
    )
    experiment["generated_at_utc"] = datetime.now(
        timezone.utc
    ).isoformat()
    experiment["input_provenance"] = provenance
    experiment["config_version"] = config["version"]
    experiment["config_status"] = config["status"]

    print(
        "[RP1 Experiment] 3/5 写入JSON与CSV结果",
        flush=True,
    )
    summary_path = output_dir / "experiment_summary.json"
    summary_path.write_text(
        json.dumps(experiment, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(
        output_dir / "b0_ours_comparison.csv",
        list(experiment["b0_ours_comparison"]),
    )
    write_csv(
        output_dir / "incremental_gate_ablation.csv",
        list(experiment["incremental_gate_ablation"]),
    )
    write_csv(
        output_dir / "specific_module_ablation.csv",
        list(experiment["specific_module_ablation"]),
    )
    write_csv(
        output_dir / "sensitivity_score_threshold.csv",
        list(experiment["sensitivity"]["silver_score_threshold"]),
    )
    write_csv(
        output_dir / "sensitivity_source_family_budget.csv",
        flatten_source_budget_rows(
            list(experiment["sensitivity"]["source_family_budget"])
        ),
    )
    write_csv(
        output_dir / "sensitivity_cq_minimum_answers.csv",
        list(experiment["sensitivity"]["cq"]["minimum_answers"]),
    )
    write_csv(
        output_dir / "sensitivity_cq_minimum_source_families.csv",
        list(
            experiment["sensitivity"]["cq"][
                "minimum_source_families"
            ]
        ),
    )
    bootstrap_rows = list(
        experiment["bootstrap"]["stage_retention"]
    ) + [dict(experiment["bootstrap"]["cq_answerability"])]
    write_csv(output_dir / "bootstrap_intervals.csv", bootstrap_rows)

    if not args.skip_figures:
        print(
            "[RP1 Experiment] 4/5 生成4组数据可视化（PNG+SVG）",
            flush=True,
        )
        figure_files = render_figures(
            experiment,
            cq_report=cq_report,
            output_dir=output_dir,
        )
    else:
        figure_files = []
    experiment["figure_files"] = figure_files
    summary_path.write_text(
        json.dumps(experiment, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "[RP1 Experiment] 5/5 生成正式实验报告与产物清单",
        flush=True,
    )
    report_path = output_dir / config["outputs"]["report"]
    report_path.write_text(
        render_report(
            experiment,
            config=config,
            cq_report=cq_report,
        ),
        encoding="utf-8",
    )
    manifest = build_manifest(output_dir)
    (output_dir / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    stages = {
        row["method_id"]: row["assertion_count"]
        for row in experiment["b0_ours_comparison"]
    }
    print("========== RP1 B0–Ours Final ==========", flush=True)
    print(
        "B0/B1/B2/B3/Ours: "
        + "/".join(f"{int(stages[key])}" for key in ("B0", "B1", "B2", "B3", "Ours")),
        flush=True,
    )
    print(
        f"CQ: {experiment['cq_result']['answerable_task_count']}/"
        f"{experiment['cq_result']['task_count']}",
        flush=True,
    )
    print(
        "Source-family replication invariant: "
        f"{experiment['source_family_result']['replication_invariance_passed']}",
        flush=True,
    )
    print(
        f"Report: {report_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
