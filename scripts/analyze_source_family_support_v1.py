"""Generate claim-level source-family-capped corroboration artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage04_graph_build import (  # noqa: E402
    DEFAULT_BUDGET,
    SOURCE_FAMILY_SUPPORT_VERSION,
    analyze_source_family_support,
    file_sha256,
)


DEFAULT_INPUT = (
    PROJECT_ROOT
    / "data"
    / "kg"
    / "marine_pump"
    / "triples"
    / "KG_v1_raw"
    / "source_records.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "results"
    / "experiments"
    / "research_point_1"
    / "source_family_support_v1"
)


def read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_number} is not valid JSON"
                ) from exc
            if not isinstance(value, dict):
                raise ValueError(
                    f"{path}:{line_number} must contain a JSON object"
                )
            yield value


def write_jsonl(path: Path, records: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _fmt(value: object, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "0"


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_markdown_report(
    summary: dict[str, object],
    *,
    input_path: str,
    claim_output_name: str,
) -> str:
    audit = dict(summary["eligibility_audit"])
    claim = dict(summary["claim_summary"])
    provenance = dict(summary["input_provenance"])
    same_family_audit = dict(summary["multi_document_same_family_audit"])
    support = dict(claim["support_index"])
    replication = dict(summary["replication_invariance_experiment"])
    sensitivity = list(summary["budget_sensitivity"])
    families = list(summary["source_family_distribution"])
    natural_cross_family_claims = int(
        claim["claims_with_at_least_two_families"]
    )

    lines = [
        "# 来源族封顶佐证指数实验报告 v1",
        "",
        f"- 分析版本：`{summary['analysis_version']}`",
        f"- 输入：`{input_path}`",
        f"- 输入SHA-256：`{provenance['source_records_sha256']}`",
        f"- Claim级明细：`{claim_output_name}`",
        f"- 默认来源族预算：B={summary['budget']}",
        "- 标签策略：仅 Silver，绝不称为 Gold；未进行人工专家审核。",
        "- 指标用途：Claim级佐证排序与来源多样性分析，不是事实正确概率，也不证明来源统计独立。",
        "- 标签影响：本分析不追溯修改现有1698条证据 Silver 决策。",
        "",
        "## 1. 指标定义",
        "",
        "对 Claim c，在每个来源族 f 内只保留最高启发式排序分：",
        "",
        "$$s_f(c)=\\max_{a_i\\in\\mathcal A_f(c)}q_i.$$",
        "",
        "将来源族分数降序排列后，按预算 B 求均值，缺失族位置补0：",
        "",
        "$$S_{\\mathrm{fam}}^{(B)}(c)="
        "\\frac{1}{B}\\sum_{j=1}^{\\min(B,|\\mathcal F_c|)}s_{(j)}(c).$$",
        "",
        "其中 $q_i=\\alpha_i w_E(l_i)w_R(\\eta_i)$。"
        "q仅为未校准的启发式排序分。",
        "",
        "## 2. 输入过滤审计",
        "",
        "| 项目 | 数量 |",
        "|---|---:|",
        f"| KG_v1_raw审计记录 | {audit['input_record_count']} |",
        f"| 合格构建集E1/E2 Silver断言 | {audit['eligible_assertion_count']} |",
        f"| 过滤记录 | {audit['excluded_record_count']} |",
        "",
        "过滤条件包括：构建集、Silver、E1/E2、非推断、"
        "关系类型与蕴含有效、证据可定位、来源族存在且q达到门槛；"
        "即使document_split字段写为build_train，doc_id也必须属于冻结白名单"
        "MP001–MP007、MP015–MP022。",
        "",
        "## 3. 默认B结果",
        "",
        "| 指标 | 结果 |",
        "|---|---:|",
        f"| Claim数 | {claim['claim_count']} |",
        f"| 证据断言数 | {claim['eligible_assertion_count']} |",
        f"| 至少2个来源族的Claim | {claim['claims_with_at_least_two_families']} |",
        f"| 至少2份文档的Claim | {claim['claims_with_multiple_documents']} |",
        f"| 平均来源族数 | {_fmt(claim['mean_family_count'])} |",
        f"| 平均文档数 | {_fmt(claim['mean_doc_count'])} |",
        f"| 指数均值 | {_fmt(support['mean'])} |",
        f"| 指数中位数 | {_fmt(support['median'])} |",
        f"| 指数范围 | {_fmt(support['minimum'])}–{_fmt(support['maximum'])} |",
        f"| 指数≥0.5的Claim | {support['count_ge_0_5']} |",
        f"| 指数≥0.8的Claim | {support['count_ge_0_8']} |",
        "",
        "## 4. B敏感性",
        "",
        "| B | Claim数 | 均值 | 中位数 | P25 | P75 | ≥0.5 | ≥0.8 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in sensitivity:
        stats = dict(item["support_index"])
        lines.append(
            f"| {item['budget']} | {item['claim_count']} | "
            f"{_fmt(stats['mean'])} | {_fmt(stats['median'])} | "
            f"{_fmt(stats['p25'])} | {_fmt(stats['p75'])} | "
            f"{stats['count_ge_0_5']} | {stats['count_ge_0_8']} |"
        )

    lines.extend(
        [
            "",
            "B越大，单一来源族Claim的缺失位置越多，指数会按定义下降。"
            "因此B是任务预算而非理论常数；默认B=2与冻结覆盖门槛一致。",
            "",
            "## 5. 同来源族复制注入不变性",
            "",
            "### 5.1 真实多文档同族审计",
            "",
            "| 项目 | 结果 |",
            "|---|---:|",
            f"| 真实多文档Claim | "
            f"{same_family_audit['multiple_document_claim_count']} |",
            f"| 其中单一来源族Claim | "
            f"{same_family_audit['multiple_document_single_family_claim_count']} |",
            f"| 其中跨来源族Claim | "
            f"{same_family_audit['multiple_document_multiple_family_claim_count']} |",
            f"| 全部真实多文档Claim均为单一来源族 | "
            f"{'是' if same_family_audit['all_observed_multiple_document_claims_are_single_family'] else '否'} |",
            "",
            "| Claim ID | 文档 | 来源族 | B=2指数 |",
            "|---|---|---|---:|",
        ]
    )
    for item in same_family_audit["claims"]:
        lines.append(
            f"| {item['claim_id']} | "
            f"{', '.join(item['doc_ids'])} | "
            f"{', '.join(item['source_family_ids'])} | "
            f"{_fmt(item['source_family_support_index'])} |"
        )

    lines.extend(
        [
            "",
            "真实审计只按冻结Claim ID聚合，不自动合并近义Claim。"
            "因此，多份同厂商文档不会被计为多个来源族；"
            "该结论也不能替代故障类别级的跨来源覆盖统计。",
            "",
            "### 5.2 合成复制注入",
            "",
            "| 项目 | 结果 |",
            "|---|---:|",
            f"| 测试Claim | {replication['claims_tested']} |",
            f"| 注入前断言数 | {replication['eligible_assertions_before']} |",
            f"| 注入后断言数 | {replication['eligible_assertions_after']} |",
            f"| Claim文档计数总和（前） | {replication['sum_claim_doc_counts_before']} |",
            f"| Claim文档计数总和（后） | {replication['sum_claim_doc_counts_after']} |",
            f"| 文档计数增长的Claim | {replication['claims_with_increased_doc_count']} |",
            f"| 来源族数改变的Claim | {replication['claims_with_changed_family_count']} |",
            f"| 佐证指数改变的Claim | {replication['claims_with_changed_support_index']} |",
            f"| 最大绝对指数变化 | {replication['maximum_absolute_index_delta']} |",
            f"| 不变性测试 | {'通过' if replication['invariance_passed'] else '未通过'} |",
            "",
            "复制记录使用新的合成文档ID，但保留原来源族和q。"
            "该实验只检验算法对明确同族复制的封顶性质，不证明不同来源族相互独立。",
            "",
            "## 6. 来源族分布",
            "",
            "| 来源族 | Silver断言 | 文档 | Claim |",
            "|---|---:|---:|---:|",
        ]
    )
    for item in families:
        lines.append(
            f"| {item['source_family_id']} | "
            f"{item['eligible_assertion_count']} | "
            f"{item['document_count']} | {item['claim_count']} |"
        )
    lines.extend(
        [
            "",
            "## 7. 结论边界",
            "",
            "1. 该指数验证的是“同族不重复累加”的算法性质，"
            "不是事实准确率或来源独立性的统计证明。",
            "2. 指数只附加到Claim级分析结果，不改变任何原始证据、"
            "页码、URL、哈希、中文术语状态或Silver标签。",
            "3. 低指数通常表示缺少跨来源族佐证，不能据此自动判定Claim为错误。",
            "4. B和q权重如需用于后续检索排序，应只在开发协议中冻结，"
            "不得利用保留测试集调参。",
            (
                "5. 本次精确Claim身份下观测到的跨至少2个来源族Claim为"
                f"{natural_cross_family_claims}条。"
                + (
                    "因此当前结果只充分验证同族复制不变性，尚不能宣称"
                    "已经用自然跨族Claim验证区分效度；这也不等于十类故障"
                    "的类别级跨来源覆盖为零。后续如需自然跨族对照，应在"
                    "冻结规则下增加可审计的语义Claim对齐，不能为提高指数"
                    "而自动合并近义Claim。"
                    if natural_cross_family_claims == 0
                    else "这些自然跨族Claim可用于后续区分效度分析。"
                )
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _parse_budgets(value: str) -> list[int]:
    try:
        budgets = sorted(
            {int(part.strip()) for part in value.split(",") if part.strip()}
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "budgets must be comma-separated positive integers"
        ) from exc
    if not budgets or budgets[0] < 1:
        raise argparse.ArgumentTypeError(
            "budgets must be comma-separated positive integers"
        )
    return budgets


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze Claim-level source-family-capped corroboration without "
            "changing existing Silver labels."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument(
        "--sensitivity-budgets",
        type=_parse_budgets,
        default=[1, 2, 3, 4],
    )
    parser.add_argument("--minimum-score", type=float, default=0.8)
    parser.add_argument("--replication-copies", type=int, default=1)
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"KG_v1_raw source records not found: {args.input}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    input_display = _portable_path(args.input)
    output_display = _portable_path(args.output_dir)
    input_size_before = args.input.stat().st_size
    input_sha256_before = file_sha256(args.input)
    print(
        "[Source Family] 开始：读取KG_v1_raw，"
        f"B={args.budget}，输入={args.input}",
        flush=True,
    )
    claim_rows, summary = analyze_source_family_support(
        read_jsonl(args.input),
        budget=args.budget,
        sensitivity_budgets=args.sensitivity_budgets,
        minimum_score=args.minimum_score,
        replication_copies=args.replication_copies,
    )
    input_size_after = args.input.stat().st_size
    input_sha256_after = file_sha256(args.input)
    if (
        input_size_before != input_size_after
        or input_sha256_before != input_sha256_after
    ):
        raise RuntimeError(
            "source_records.jsonl changed during analysis; results were not "
            "written. Rerun against a frozen input."
        )
    summary["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    summary["input"] = input_display
    summary["input_provenance"] = {
        "path": input_display,
        "source_records_sha256": input_sha256_after,
        "size_bytes": input_size_after,
    }
    summary["output_directory"] = output_display

    claim_path = args.output_dir / "claim_source_family_support.jsonl"
    summary_path = args.output_dir / "source_family_support_summary.json"
    report_path = args.output_dir / "source_family_support_report.md"
    invariance_path = (
        args.output_dir / "same_family_replication_invariance.json"
    )
    write_jsonl(claim_path, claim_rows)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    invariance_path.write_text(
        json.dumps(
            summary["replication_invariance_experiment"],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report_path.write_text(
        build_markdown_report(
            summary,
            input_path=input_display,
            claim_output_name=claim_path.name,
        ),
        encoding="utf-8",
    )

    claim_summary = dict(summary["claim_summary"])
    experiment = dict(summary["replication_invariance_experiment"])
    support = dict(claim_summary["support_index"])
    print(
        "[Source Family] 完成："
        f"Silver断言={claim_summary['eligible_assertion_count']}，"
        f"Claim={claim_summary['claim_count']}，"
        f"跨至少2族Claim={claim_summary['claims_with_at_least_two_families']}，"
        f"S_fam均值={float(support['mean']):.4f}",
        flush=True,
    )
    print(
        "[Source Family] 同族复制注入："
        f"{'通过' if experiment['invariance_passed'] else '未通过'}；"
        f"最大指数变化={experiment['maximum_absolute_index_delta']}",
        flush=True,
    )
    print(
        f"[Source Family] 输出：{args.output_dir}",
        flush=True,
    )
    print(
        f"[Source Family] 版本={SOURCE_FAMILY_SUPPORT_VERSION}；"
        "本指标不修改既有Silver标签，也不表示概率或独立性证明。",
        flush=True,
    )


if __name__ == "__main__":
    main()
