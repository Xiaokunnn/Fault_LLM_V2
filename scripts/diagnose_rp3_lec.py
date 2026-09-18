#!/usr/bin/env python3
"""Inspect frozen FP32/INT8 outputs on build splits without deployment approval.

This command does not read MP008 examples, fit thresholds, train, call a teacher,
or write calibration/evaluation artifacts. MP008 search reports remain separate.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import onnxruntime as ort

from src.research_point_3.artifacts import canonical_json_bytes, canonical_jsonl_bytes, file_sha256, stable_sha256, _write_immutable
from src.research_point_3.diagnostics import prediction_row, summarize
from src.research_point_3.experiment_io import prepare, onnx_feed


def checked_manifest(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if stable_sha256({k: v for k, v in value.items() if k != "logical_sha256"}) != value.get("logical_sha256"):
        raise ValueError(f"manifest hash mismatch: {path}")
    return value


def validate_bindings(export_dir, prepared):
    root = Path(export_dir)
    export = checked_manifest(root / "onnx_export_manifest.json")
    quant = checked_manifest(root / "quantization_manifest.json")
    if export["input_fingerprint"] != prepared.input_fingerprint:
        raise ValueError("diagnostic config does not match exported training inputs")
    if export["runtime_binding"]["memory"]["logical_sha256"] != prepared.memory_manifest["logical_sha256"]:
        raise ValueError("diagnostic memory binding mismatch")
    if export["runtime_binding"]["teacher_graph"] != prepared.memory_manifest["teacher_graph"]:
        raise ValueError("diagnostic teacher graph binding mismatch")
    paths = {"fp32": root / export["onnx_file"], "int8": root / "controller.int8.onnx"}
    if file_sha256(paths["fp32"]) != export["onnx_sha256"] or export["onnx_sha256"] != quant["fp32_sha256"]:
        raise ValueError("FP32 artifact binding mismatch")
    if file_sha256(paths["int8"]) != quant["int8_sha256"]:
        raise ValueError("INT8 artifact binding mismatch")
    return export, quant, paths


def validate_protocol(config):
    if config.get("schema") != "rp3_build_diagnostics_protocol_v1" or config.get("purpose") != "internal_build_diagnostics_not_deployment":
        raise ValueError("unknown diagnostics protocol")
    for key in ("support_threshold", "route_confidence_threshold", "simple_confidence_threshold", "simple_normalized_entropy_threshold"):
        if not 0 <= config[key] <= 1:
            raise ValueError(f"invalid {key}")
    for key in ("repeats", "ort_threads", "ece_bins", "bootstrap_replicates"):
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError(f"invalid {key}")
    if type(config["warmup"]) is not int or config["warmup"] < 0:
        raise ValueError("invalid warmup")
    if set(config["costs"]) != {"local", "teacher", "review", "error"} or any(
        not np.isfinite(x) or x < 0 for x in config["costs"].values()
    ):
        raise ValueError("invalid declared utility profile")
    if config.get("development_inputs") != "excluded" or config.get("external_inputs") != "excluded":
        raise ValueError("diagnostics accepts build inputs only")


def report_csv(summary):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["precision", "subset", "rows", "scenarios", "exact_including_empty", "nonempty_exact_success", "pointer_f1", "support_f1", "support_ap", "support_ece", "requested_cardinality_accuracy", "controller_p50_ms", "controller_p95_ms"])
    for precision, subsets in summary["metrics"].items():
        for subset, m in subsets.items():
            writer.writerow([precision, subset, m["rows"], m["scenario_aggregation"]["independent_scenario_count"], m["set_exact_including_empty"], m["nonempty_exact_success"], m["pointer_macro"]["f1"], m["support"]["f1"], m["support"]["auprc_average_precision"], m["support"]["ece"], m["fields"]["raw_requested_slot"]["cardinality_accuracy"], m["controller_only_latency_ms"]["p50"], m["controller_only_latency_ms"]["p95"]])
    return stream.getvalue()


def report_markdown(summary):
    lines = ["# RP3 构建集内部诊断", "", "未校准、不可部署；指标相对冻结教师。validation 参与过模型选择。", "",
             "| 精度 | 子集 | 行数 | 场景数 | 非空集合成功 | Pointer F1 | Support F1 | 所需角色基数准确率 |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for precision, subsets in summary["metrics"].items():
        for subset, m in subsets.items():
            f1 = m["support"]["f1"]
            lines.append(f"| {precision} | {subset} | {m['rows']} | {m['scenario_aggregation']['independent_scenario_count']} | {m['nonempty_exact_success']}/{m['rows']} | {m['pointer_macro']['f1']:.4f} | {f1 if f1 is not None else 'NA'} | {m['fields']['raw_requested_slot']['cardinality_accuracy']:.4f} |")
    lines += ["", "完整字段、置信度曲线、路由策略、场景重采样区间及量化差异见 summary.json；逐行证据见 predictions.jsonl。",
              "support 排除不可用/填充/not_assessed；AP 按同分组计算；全空集一致单列，不等于非空成功。",
              "ORT 时延为服务器 CPU 单线程控制器测量，排除编码、记忆、渲染、壳及教师。教师调用为冻结结果离线重放，实际调用为零。"]
    return "\n".join(lines) + "\n"


def run(config_path, export_dir, output_dir, protocol_path):
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError("diagnostics output must be a new directory; preserve previous reports")
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    validate_protocol(protocol)
    prepared = prepare(config_path, attach_development=False)
    export, quant, paths = validate_bindings(export_dir, prepared)
    options = ort.SessionOptions()
    options.intra_op_num_threads = protocol["ort_threads"]
    options.inter_op_num_threads = 1
    rows = []
    logits_by_precision = {}
    for precision, model in paths.items():
        session = ort.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"])
        raw = {}
        for dataset in (prepared.train_dataset, prepared.validation_dataset):
            for i, trace in enumerate(dataset.traces):
                feed = onnx_feed(dataset, i)
                for _ in range(protocol["warmup"]):
                    session.run(None, feed)
                timings = []
                for _ in range(protocol["repeats"]):
                    start = time.perf_counter_ns()
                    logits = session.run(None, feed)
                    timings.append((time.perf_counter_ns() - start) / 1e6)
                row = prediction_row(trace, dataset.records, logits, protocol)
                row.update(precision=precision, controller_timings_ms=timings)
                rows.append(row)
                raw[trace.trace_id] = (logits, feed["availability_mask"][0])
        logits_by_precision[precision] = raw
    metrics = {}
    for precision in paths:
        groups = {}
        for split in ("train", "validation"):
            for kind in ("all", "original", "derived"):
                chosen = [r for r in rows if r["precision"] == precision and r["split"] == split
                          and (kind == "all" or (r["perturbation_id"] == "original") == (kind == "original"))]
                if chosen:
                    groups[split + "_" + kind] = summarize(chosen, protocol)
        metrics[precision] = groups
    differences = [[] for _ in range(5)]
    for key, (fp32, mask) in logits_by_precision["fp32"].items():
        int8, _ = logits_by_precision["int8"][key]
        for i, (a, b) in enumerate(zip(fp32, int8)):
            # Unavailable/padded logits are mask sentinels, not accuracy samples.
            delta = np.abs(a.astype(np.float64) - b.astype(np.float64))
            differences[i].extend((delta[0, mask] if i < 2 else delta.ravel()).tolist())
    pairs = {r["trace_id"]: r for r in rows if r["precision"] == "fp32"}
    int8_rows = [r for r in rows if r["precision"] == "int8"]
    provenance = {str(p): file_sha256(p) for p in (Path(config_path), Path(protocol_path), Path(export_dir) / "onnx_export_manifest.json", Path(export_dir) / "quantization_manifest.json", Path(__file__), ROOT / "src/research_point_3/diagnostics.py", ROOT / "src/research_point_3/onnx_runtime.py", ROOT / "src/research_point_3/experiment_io.py")}
    memory_dir = ROOT / json.loads(Path(config_path).read_text())["memory_bundle_dir"]
    summary = {"schema": "rp3_build_diagnostics_v1", "status": "internal_diagnostics_uncalibrated_not_deployable",
               "protocol": protocol, "protocol_sha256": file_sha256(protocol_path), "provenance": provenance,
               "input_fingerprint": prepared.input_fingerprint,
               "teacher_system_identity_sha256": prepared.trace_manifest["teacher_system_identity_sha256"],
               "trace_bundle_sha256": prepared.trace_manifest["logical_sha256"],
               "memory_bundle_sha256": prepared.memory_manifest["logical_sha256"],
               "metrics": metrics, "model_sha256": {k: file_sha256(v) for k, v in paths.items()},
               "model_bytes": {k: v.stat().st_size for k, v in paths.items()},
               "evidence_memory_bundle_bytes": sum(p.stat().st_size for p in memory_dir.iterdir() if p.is_file()),
               "parameter_report": export["parameter_report"],
               "quantization_comparison": {"maximum_absolute_error_per_output": [max(xs) if xs else None for xs in differences],
                   "mean_absolute_error_per_output": [float(np.mean(xs)) if xs else None for xs in differences],
                   "selection_set_changes": sum(set(r["selected_ids"]) != set(pairs[r["trace_id"]]["selected_ids"]) for r in int8_rows),
                   "raw_route_changes": sum(r["raw_route_action"] != pairs[r["trace_id"]]["raw_route_action"] for r in int8_rows),
                   "compared_build_rows": len(int8_rows), "qdq_nodes": quant["qdq_nodes"]},
               "runtime": {"platform": platform.platform(), "processor": platform.processor(), "onnxruntime": ort.__version__, "providers": ["CPUExecutionProvider"], "ort_threads": protocol["ort_threads"]},
               "boundary": {"development_examples_read": False, "external_examples_read": False, "training_performed": False,
                   "thresholds_fitted": False, "deployable": False, "expert_diagnostic_accuracy": False, "target_edge_hardware_measured": False,
                   "latency_scope": "ORT controller only, server CPU; excludes encoding, memory, rendering, shell and teacher",
                   "pointer_closure_scope": "candidate/memory IDs, availability, role, uniqueness and budget; full rendered citation closure is not measured",
                   "support_scope": "available assessed candidates only; masked and not_assessed excluded",
                   "risk_coverage_scope": "eligible nonempty local proposals; grouped confidence ties; truncated reachable-coverage AURC"}}
    _write_immutable(out / "predictions.jsonl", canonical_jsonl_bytes(rows))
    summary["predictions_sha256"] = file_sha256(out / "predictions.jsonl")
    _write_immutable(out / "summary.json", canonical_json_bytes(summary))
    _write_immutable(out / "summary.csv", report_csv(summary).encode("utf-8"))
    _write_immutable(out / "summary.md", report_markdown(summary).encode("utf-8"))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--export-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--protocol", default=str(ROOT / "configs/research_point_3/diagnostics_v1.json"))
    args = parser.parse_args()
    result = run(args.config, args.export_dir, args.output_dir, args.protocol)
    print(json.dumps({"status": result["status"], "output_dir": args.output_dir, "quantization_comparison": result["quantization_comparison"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
