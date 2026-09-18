#!/usr/bin/env python3
"""Create comparable B0/M0 tables from immutable internal diagnostic reports."""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, file_sha256, _write_immutable


def compare(inputs, output_dir):
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError("comparison output must be a new directory")
    reports = {}
    original_id_sets = {}
    for label, path in inputs.items():
        path = Path(path)
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("schema") != "rp3_build_diagnostics_v1" or report.get("boundary", {}).get("deployable") is not False:
            raise ValueError("expected nondeployable diagnostic reports")
        predictions = path.parent / "predictions.jsonl"
        if file_sha256(predictions) != report["predictions_sha256"]:
            raise ValueError("diagnostic prediction hash mismatch")
        rows = [json.loads(line) for line in predictions.read_text(encoding="utf-8").splitlines()]
        original_id_sets[label] = {(r["trace_id"], r["split"], tuple(r["teacher_selected_ids"])) for r in rows if r["perturbation_id"] == "original"}
        reports[label] = report
    for key in ("protocol_sha256", "teacher_system_identity_sha256", "memory_bundle_sha256"):
        if len({r[key] for r in reports.values()}) != 1:
            raise ValueError(f"comparison must use the same {key}")
    originals = list(original_id_sets.values())
    if any(value != originals[0] for value in originals[1:]):
        raise ValueError("original query/split/teacher-label sets differ across arms")
    table, policies = [], []
    for arm, report in reports.items():
        for precision, groups in report["metrics"].items():
            for subset, m in groups.items():
                table.append({"arm": arm, "precision": precision, "subset": subset, "rows": m["rows"],
                    "scenario_count": m["scenario_aggregation"]["independent_scenario_count"],
                    "exact_set_including_empty": m["set_exact_including_empty"], "nonempty_exact_success": m["nonempty_exact_success"],
                    "pointer_f1": m["pointer_macro"]["f1"], "rank_ndcg": m["rank_ndcg_at_budget_nonempty_teacher"],
                    "support_f1": m["support"]["f1"], "support_ap": m["support"]["auprc_average_precision"], "support_ece": m["support"]["ece"],
                    "requested_raw_cardinality_accuracy": m["fields"]["raw_requested_slot"]["cardinality_accuracy"],
                    "controller_p50_ms": m["controller_only_latency_ms"]["p50"], "controller_p95_ms": m["controller_only_latency_ms"]["p95"],
                    "model_bytes": report["model_bytes"][precision]})
                for policy, values in m["routing"].items():
                    policies.append({"arm": arm, "precision": precision, "subset": subset, "policy": policy,
                        **{k: values[k] for k in ("local_answer_coverage", "local_teacher_disagreement", "fallback_rate", "abstain_rate",
                             "replayed_teacher_calls", "teacher_call_avoidance_fraction", "replayed_final_answer_coverage", "mean_declared_utility_cost", "mean_route_regret")}})
    calibration = {}
    for label, source in inputs.items():
        # Summarize existing immutable calibration reports; never fit thresholds.
        search = Path(source).parent.parent / "onnx/calibration_search_report.json"
        if search.is_file():
            c = json.loads(search.read_text(encoding="utf-8"))
            if c["quantized_model_sha256"] != reports[label]["model_sha256"]["int8"]:
                raise ValueError("stored calibration belongs to a different model")
            calibration[label] = {"path": str(search), "sha256": file_sha256(search),
                                  **{k: c[k] for k in ("status", "constraints", "raw_route_argmax_counts", "blocked", "chosen", "grid")}}
    result = {"schema": "rp3_diagnostic_comparison_v1", "status": "internal_not_deployable", "quality_rows": table,
              "routing_rows": policies, "stored_mp008_calibration": calibration,
              "sources": {label: {"path": str(path), "sha256": file_sha256(path)} for label, path in inputs.items()},
              "comparison_boundary": "original subsets are paired; all/derived have different populations; no independent external or multiseed claim",
              "teacher_cost_boundary": "frozen teacher outcomes replayed, dimensionless utility 1/8/12/50, not measured teacher latency or energy"}
    def write_csv(name, rows):
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
        _write_immutable(out / name, stream.getvalue().encode("utf-8"))
    def fmt(value):
        return "NA" if value is None else f"{value:.4f}"
    lines = ["# B0/M0 内部诊断比较", "", "仅原始查询子集可直接配对比较。未校准、不可部署；不改变 evaluate 门槛。", "",
             "| 实验臂 | 精度 | 原始子集 | 非空集合成功 | 含空集精确一致 | Pointer F1 | Support F1 | 所需角色基数准确率 | ORT p50/p95 ms |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in table:
        if row["subset"].endswith("_original"):
            lines.append(f"| {row['arm']} | {row['precision']} | {row['subset']} | {row['nonempty_exact_success']}/{row['rows']} | {row['exact_set_including_empty']}/{row['rows']} | {fmt(row['pointer_f1'])} | {fmt(row['support_f1'])} | {fmt(row['requested_raw_cardinality_accuracy'])} | {fmt(row['controller_p50_ms'])}/{fmt(row['controller_p95_ms'])} |")
    lines += ["", "## 原始 validation 路由对照（INT8，离线重放）", "",
              "| 臂 | 策略 | 本地覆盖 | 回答条件不一致 | 回退率 | 弃答率 | 平均效用成本 | Regret |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in policies:
        if row["subset"] == "validation_original" and row["precision"] == "int8":
            lines.append(f"| {row['arm']} | {row['policy']} | {fmt(row['local_answer_coverage'])} | {fmt(row['local_teacher_disagreement'])} | {fmt(row['fallback_rate'])} | {fmt(row['abstain_rate'])} | {fmt(row['mean_declared_utility_cost'])} | {fmt(row['mean_route_regret'])} |")
    lines += ["", "NA 表示没有接受回答，风险未定义；不能解释为零风险。教师调用节省须与覆盖率同时解释。",
              "R1 只重放冻结教师结果，实际7B调用为0；T0自身一致仅为参照，不是教师正确率。",
              "所有计时为服务器CPU单线程ORT控制器；排除特征编码、证据读取、渲染、壳、网络和7B。",
              "场景组重采样区间见各臂summary.json，validation仅2组，不能代替三个训练种子或外部评价。",
              "MP008仅汇总已有失败校准报告，不重新运行校准、不选择阈值；完整风险—覆盖网格在comparison.json。"]
    _write_immutable(out / "comparison.json", canonical_json_bytes(result))
    write_csv("quality.csv", table)
    write_csv("routing.csv", policies)
    _write_immutable(out / "comparison.md", ("\n".join(lines) + "\n").encode("utf-8"))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", required=True)
    p.add_argument("--augmented", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()
    compare({"B0": args.baseline, "M0": args.augmented}, args.output_dir)
    print(args.output_dir)


if __name__ == "__main__":
    main()
