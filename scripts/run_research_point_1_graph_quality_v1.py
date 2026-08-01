"""Run and aggregate the three research-point-1 graph-quality modules.

This local-only runner performs no model or network calls.  It executes the
frozen CQ suite, source-family-capped corroboration analysis, and project-
specific graph constraints, then writes one reproducible closure summary.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT / "results" / "experiments" / "research_point_1"
)
SUMMARY_VERSION = "marine_pump_rp1_graph_quality_v1"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
GRAPH_LAYER_FILES = {
    "entities": "entities.jsonl",
    "claims": "claims.jsonl",
    "evidence_assertions": "evidence_assertions.jsonl",
    "claim_evidence_links": "claim_evidence_links.jsonl",
    "source_records": "source_records.jsonl",
}
INPUT_REPORT_NAMES = (
    "cq_v1",
    "source_family_support_v1",
    "constraint_report_v1",
)


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _validated_sha(value: object, *, label: str) -> str:
    text = str(value or "")
    if not SHA256_RE.fullmatch(text):
        raise ValueError(f"Missing or invalid SHA-256 for {label}: {text!r}")
    return text.lower()


def _input_report_manifest(
    input_reports: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    missing = sorted(set(INPUT_REPORT_NAMES) - set(input_reports))
    extra = sorted(set(input_reports) - set(INPUT_REPORT_NAMES))
    if missing or extra:
        raise ValueError(
            "Input report manifest must contain exactly the three reports; "
            f"missing={missing}, extra={extra}"
        )
    result: dict[str, dict[str, object]] = {}
    for name in INPUT_REPORT_NAMES:
        item = input_reports[name]
        path = str(item.get("path") or "")
        if not path:
            raise ValueError(f"Input report path is missing for {name}")
        result[name] = {
            "path": path,
            "sha256": _validated_sha(
                item.get("sha256"),
                label=f"input report {name}",
            ),
            "size_bytes": int(item.get("size_bytes") or 0),
        }
    return result


def _source_report_raw_sha(
    support_report: Mapping[str, object],
) -> str:
    provenance = support_report.get("input_provenance")
    if isinstance(provenance, Mapping):
        value = provenance.get("source_records_sha256")
        if value:
            return _validated_sha(
                value,
                label=(
                    "source-family report "
                    "input_provenance.source_records_sha256"
                ),
            )

    # Compatibility with provisional reports produced before the canonical
    # input_provenance object was introduced.
    for field in (
        "input_source_records_sha256",
        "input_file_sha256",
        "input_sha256",
    ):
        value = support_report.get(field)
        if value:
            return _validated_sha(
                value,
                label=f"source-family report {field}",
            )
    raise ValueError(
        "Source-family report does not record the KG_v1_raw "
        "source_records SHA-256. Rerun its analyzer before aggregation."
    )


def validate_cross_report_graph_hashes(
    cq_report: Mapping[str, object],
    support_report: Mapping[str, object],
    constraint_report: Mapping[str, object],
) -> dict[str, object]:
    """Fail closed when the three reports were not built from one graph."""

    cq_evaluation = cq_report.get("evaluation")
    if not isinstance(cq_evaluation, Mapping):
        raise ValueError("CQ report is missing evaluation metadata")
    if cq_evaluation.get("graph_version") != "KG_v1_validated":
        raise ValueError(
            "CQ report must evaluate KG_v1_validated, got "
            f"{cq_evaluation.get('graph_version')!r}"
        )
    cq_input = cq_report.get("input_graph")
    if not isinstance(cq_input, Mapping):
        raise ValueError("CQ report is missing input_graph metadata")
    cq_files = cq_input.get("file_sha256")
    if not isinstance(cq_files, Mapping):
        raise ValueError("CQ report is missing input_graph.file_sha256")

    packages = constraint_report.get("packages")
    if not isinstance(packages, Mapping):
        raise ValueError("Constraint report is missing package metadata")
    validated_package = packages.get("KG_v1_validated")
    raw_package = packages.get("KG_v1_raw")
    if not isinstance(validated_package, Mapping) or not isinstance(
        raw_package, Mapping
    ):
        raise ValueError(
            "Constraint report must contain KG_v1_raw and KG_v1_validated"
        )
    validated_files = validated_package.get("input_files")
    raw_files = raw_package.get("input_files")
    if not isinstance(validated_files, Mapping) or not isinstance(
        raw_files, Mapping
    ):
        raise ValueError(
            "Constraint report package input_files metadata is missing"
        )

    validated_hashes: dict[str, str] = {}
    mismatches: list[str] = []
    for layer, filename in GRAPH_LAYER_FILES.items():
        cq_sha = _validated_sha(
            cq_files.get(filename),
            label=f"CQ KG_v1_validated {filename}",
        )
        constraint_item = validated_files.get(layer)
        if not isinstance(constraint_item, Mapping):
            raise ValueError(
                "Constraint report is missing KG_v1_validated "
                f"input_files.{layer}"
            )
        constraint_sha = _validated_sha(
            constraint_item.get("sha256"),
            label=f"constraint KG_v1_validated {layer}",
        )
        if cq_sha != constraint_sha:
            mismatches.append(
                f"KG_v1_validated/{filename}: "
                f"CQ={cq_sha}, constraint={constraint_sha}"
            )
        validated_hashes[filename] = cq_sha

    raw_source_item = raw_files.get("source_records")
    if not isinstance(raw_source_item, Mapping):
        raise ValueError(
            "Constraint report is missing "
            "KG_v1_raw input_files.source_records"
        )
    constraint_raw_sha = _validated_sha(
        raw_source_item.get("sha256"),
        label="constraint KG_v1_raw source_records",
    )
    support_raw_sha = _source_report_raw_sha(support_report)
    if support_raw_sha != constraint_raw_sha:
        mismatches.append(
            "KG_v1_raw/source_records.jsonl: "
            f"source-family={support_raw_sha}, "
            f"constraint={constraint_raw_sha}"
        )
    if mismatches:
        raise ValueError(
            "Cross-report graph SHA-256 mismatch; refusing to aggregate "
            "reports from different graph states:\n- "
            + "\n- ".join(mismatches)
        )
    return {
        "passed": True,
        "policy": (
            "CQ KG_v1_validated five-layer hashes must equal constraint "
            "KG_v1_validated; source-family KG_v1_raw source_records hash "
            "must equal constraint KG_v1_raw."
        ),
        "kg_v1_validated_layer_sha256": validated_hashes,
        "kg_v1_raw_source_records_sha256": constraint_raw_sha,
    }


def build_closure_summary(
    cq_report: Mapping[str, object],
    support_report: Mapping[str, object],
    constraint_report: Mapping[str, object],
    *,
    input_reports: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    report_manifest = _input_report_manifest(input_reports)
    graph_input_consistency = validate_cross_report_graph_hashes(
        cq_report,
        support_report,
        constraint_report,
    )
    aggregate = dict(cq_report["aggregate"])
    cq_overall = dict(aggregate["overall"])
    claim_summary = dict(support_report["claim_summary"])
    support_index = dict(claim_summary["support_index"])
    replication = dict(
        support_report["replication_invariance_experiment"]
    )
    multi_document_audit = dict(
        support_report["multi_document_same_family_audit"]
    )
    constraints = dict(constraint_report["summary"])
    tasks = list(cq_report["task_results"])
    unanswered = [
        {
            "cq_id": item["cq_id"],
            "fault_id": item["fault_id"],
            "fault_name_zh": item["fault_name_zh"],
            "role": item["role"],
            "role_name_zh": item["role_name_zh"],
            "reason_codes": list(
                item.get("unanswerable_reason_codes") or []
            ),
        }
        for item in tasks
        if not bool(item["structurally_answerable"])
    ]
    natural_cross_family = int(
        claim_summary["claims_with_at_least_two_families"]
    )
    limitations: list[str] = []
    if unanswered:
        limitations.append(
            f"冻结的CQ v1中有{len(unanswered)}个任务在"
            "KG_v1_validated中不存在可追溯合法答案路径。"
        )
    if natural_cross_family == 0:
        limitations.append(
            "没有精确Claim ID获得两个来源族的自然佐证；当前来源族实验"
            "只验证了同族复制不变性。"
        )
    if int(constraints["failed_checks"]) > 0:
        limitations.append(
            "约束报告含非阻断失败或警告，需结合Markdown明细解释。"
        )
    limitations.append(
        "基线、消融和自然跨来源族区分实验尚未完成。"
    )

    release_constraints_passed = not bool(
        constraints["release_blocked"]
    )
    replication_passed = bool(replication["invariance_passed"])
    observed_same_family_audit_passed = bool(
        multi_document_audit[
            "all_observed_multiple_document_claims_are_single_family"
        ]
    ) and int(
        multi_document_audit["multiple_document_claim_count"]
    ) > 0
    full_cq_coverage = not unanswered
    natural_cross_family_observed = natural_cross_family > 0
    ablation_experiments_completed = False
    pipeline_ready = (
        release_constraints_passed
        and replication_passed
        and observed_same_family_audit_passed
    )
    method_evidence_complete = (
        pipeline_ready
        and full_cq_coverage
        and natural_cross_family_observed
        and ablation_experiments_completed
    )
    return {
        "summary_version": SUMMARY_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "ship_engine_room_pump_system_research_point_1",
        "execution_semantics": (
            "local_only_no_model_or_network_calls"
        ),
        "input_reports": report_manifest,
        "cross_report_graph_input_consistency": graph_input_consistency,
        "cq_v1": {
            "task_count": int(cq_overall["cq_count"]),
            "answerable_task_count": int(
                cq_overall["answerable_cq_count"]
            ),
            "traceable_structure_answerability": float(
                cq_overall["traceable_structure_answerability"]
            ),
            "unanswerable_task_count": len(unanswered),
            "unanswerable_tasks": unanswered,
            "metric_is_accuracy": False,
        },
        "source_family_corroboration_v1": {
            "eligible_silver_assertions": int(
                claim_summary["eligible_assertion_count"]
            ),
            "claim_count": int(claim_summary["claim_count"]),
            "claims_with_at_least_two_families": natural_cross_family,
            "budget": int(support_report["budget"]),
            "mean_index": float(support_index["mean"]),
            "median_index": float(support_index["median"]),
            "same_family_replication_invariance_passed": (
                replication_passed
            ),
            "maximum_replication_index_delta": float(
                replication["maximum_absolute_index_delta"]
            ),
            "observed_multiple_document_claim_count": int(
                multi_document_audit[
                    "multiple_document_claim_count"
                ]
            ),
            "observed_multiple_document_single_family_claim_count": int(
                multi_document_audit[
                    "multiple_document_single_family_claim_count"
                ]
            ),
            "observed_same_family_collapse_audit_passed": (
                observed_same_family_audit_passed
            ),
            "changes_existing_silver_labels": False,
            "metric_is_probability_or_independence_proof": False,
        },
        "constraint_report_v1": {
            "check_count": int(constraints["checks"]),
            "failed_check_count": int(constraints["failed_checks"]),
            "release_blocking_check_count": int(
                constraints["release_blocking_checks"]
            ),
            "release_blocked": bool(constraints["release_blocked"]),
            "validator_kind": constraint_report["validator_kind"],
            "is_shacl_or_rdf_validation": False,
        },
        "readiness": {
            "three_input_reports_aggregated": True,
            "release_constraints_passed": release_constraints_passed,
            "same_family_replication_property_verified": (
                replication_passed
            ),
            "observed_same_family_multi_document_property_verified": (
                observed_same_family_audit_passed
            ),
            "full_40_cq_structural_coverage": full_cq_coverage,
            "natural_cross_family_claim_corroboration_observed": (
                natural_cross_family_observed
            ),
            "ablation_experiments_completed": (
                ablation_experiments_completed
            ),
            "pipeline_ready_to_start_experiments": pipeline_ready,
            "method_evidence_complete": method_evidence_complete,
            "research_point_1_complete": False,
            "recommended_next_stage": (
                "baseline_and_ablation_experiments_with_observed_"
                "cq_and_claim_alignment_gaps_reported"
            ),
        },
        "limitations": limitations,
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }


def render_markdown(summary: Mapping[str, object]) -> str:
    cq = dict(summary["cq_v1"])
    support = dict(summary["source_family_corroboration_v1"])
    constraints = dict(summary["constraint_report_v1"])
    readiness = dict(summary["readiness"])
    lines = [
        "# 研究点一图谱方法收口报告 v1",
        "",
        f"- 版本：`{summary['summary_version']}`",
        "- 执行范围：纯本地；未调用模型或网络。",
        "- 标签政策：仅 Silver，绝不称 Gold；未进行领域专家审核。",
        "",
        "## 核心结果",
        "",
        "| 模块 | 结果 |",
        "|---|---|",
        (
            f"| CQ v1 | {cq['answerable_task_count']}/"
            f"{cq['task_count']}，可追溯结构可回答率 "
            f"{float(cq['traceable_structure_answerability']):.1%}；"
            "该指标不是准确率 |"
        ),
        (
            "| 来源族封顶佐证 | "
            f"{support['eligible_silver_assertions']}条Silver、"
            f"{support['claim_count']}个Claim、"
            f"自然跨至少2族Claim={support['claims_with_at_least_two_families']}、"
            f"真实多文档同族审计="
            f"{support['observed_multiple_document_single_family_claim_count']}/"
            f"{support['observed_multiple_document_claim_count']}、"
            f"同族复制不变性="
            f"{'通过' if support['same_family_replication_invariance_passed'] else '未通过'} |"
        ),
        (
            f"| 标准化约束 | {constraints['check_count']}项检查，"
            f"{constraints['release_blocking_check_count']}项发布阻断，"
            f"`release_blocked={str(constraints['release_blocked']).lower()}`；"
            "不是SHACL/RDF验证 |"
        ),
        "",
        "## CQ空缺",
        "",
    ]
    unanswered = list(cq["unanswerable_tasks"])
    if unanswered:
        for item in unanswered:
            reasons = ", ".join(item["reason_codes"]) or "unspecified"
            lines.append(
                f"- {item['fault_name_zh']}—{item['role_name_zh']} "
                f"(`{item['cq_id']}`)：{reasons}"
            )
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
        "## 结论边界",
            "",
        ]
    )
    for limitation in summary["limitations"]:
        lines.append(f"- {limitation}")
    lines.extend(
        [
            "",
            (
                "当前流水线已具备开始对照与消融实验的条件；"
                "这不表示方法证据完整或研究点一已经完成。"
                if readiness["pipeline_ready_to_start_experiments"]
                else "当前流水线尚不具备开始正式实验的条件。"
            ),
            (
                "- 方法证据完整："
                f"{'是' if readiness['method_evidence_complete'] else '否'}"
            ),
            (
                "- 研究点一完成："
                f"{'是' if readiness['research_point_1_complete'] else '否'}"
            ),
            "CQ空缺和精确Claim跨来源族对齐缺口必须作为结果报告，"
            "不得通过自动降门槛或改写Silver标签隐藏。",
            "",
        ]
    )
    return "\n".join(lines)


def run_step(label: str, command: list[str]) -> None:
    print(f"========== {label} ==========", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode:
        raise RuntimeError(
            f"{label} failed with exit code {completed.returncode}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run CQ v1, source-family corroboration, and executable graph "
            "constraints, then aggregate their results."
        )
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    parser.add_argument(
        "--skip-execution",
        action="store_true",
        help="Aggregate existing module reports without rerunning them.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = args.output_root.resolve()
    cq_dir = output_root / "cq_v1"
    support_dir = output_root / "source_family_support_v1"
    constraint_dir = output_root / "constraint_report_v1"
    if not args.skip_execution:
        run_step(
            "1/3 CQ v1",
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "evaluate_cq_v1.py"),
                "--output-dir",
                str(cq_dir),
            ],
        )
        run_step(
            "2/3 Source-family corroboration",
            [
                sys.executable,
                str(
                    PROJECT_ROOT
                    / "scripts"
                    / "analyze_source_family_support_v1.py"
                ),
                "--output-dir",
                str(support_dir),
            ],
        )
        run_step(
            "3/3 Executable graph constraints",
            [
                sys.executable,
                str(
                    PROJECT_ROOT
                    / "scripts"
                    / "generate_graph_constraint_report_v1.py"
                ),
                "--output-dir",
                str(constraint_dir),
                "--fail-on-blocked",
            ],
        )

    report_paths = {
        "cq_v1": cq_dir / "cq_v1_evaluation.json",
        "source_family_support_v1": (
            support_dir / "source_family_support_summary.json"
        ),
        "constraint_report_v1": (
            constraint_dir / "graph_constraint_report.json"
        ),
    }
    input_reports = {
        name: {
            "path": _portable_path(path),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for name, path in report_paths.items()
    }
    summary = build_closure_summary(
        read_json(report_paths["cq_v1"]),
        read_json(report_paths["source_family_support_v1"]),
        read_json(report_paths["constraint_report_v1"]),
        input_reports=input_reports,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "rp1_graph_quality_summary_v1.json"
    md_path = output_root / "rp1_graph_quality_summary_v1.md"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(summary), encoding="utf-8")
    readiness = dict(summary["readiness"])
    print("========== Final ==========", flush=True)
    print(
        "CQ: "
        f"{summary['cq_v1']['answerable_task_count']}/"
        f"{summary['cq_v1']['task_count']}",
        flush=True,
    )
    print(
        "Release blocked: "
        f"{summary['constraint_report_v1']['release_blocked']}",
        flush=True,
    )
    print(
        "Pipeline ready to start experiments: "
        f"{readiness['pipeline_ready_to_start_experiments']}",
        flush=True,
    )
    print(
        "Method evidence complete: "
        f"{readiness['method_evidence_complete']}",
        flush=True,
    )
    print(
        "Research point 1 complete: "
        f"{readiness['research_point_1_complete']}",
        flush=True,
    )
    print(f"Summary: {json_path}", flush=True)


if __name__ == "__main__":
    main()
