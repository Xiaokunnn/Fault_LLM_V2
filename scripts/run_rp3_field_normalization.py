#!/usr/bin/env python3
"""Run a paired three-seed requested-field normalization experiment, build only."""
from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research_point_3.artifacts import canonical_json_bytes, canonical_jsonl_bytes, file_sha256, stable_sha256, _write_immutable
from src.research_point_3.ablations import seed_statistics
from src.research_point_3.field_audit import grouped_field_metrics
from scripts.run_rp3_head_ablations import diagnose_checkpoint


def treatment_config(control):
    if any(k.startswith("development") for k in control):
        raise ValueError("the paired control must have no development input")
    if control["training"]["loss_weights"] != {"ranking": 1.0, "support": 1.0, "field_state": .6,
                                                "cardinality": .6, "route": 0.0, "intervention": 0.0, "calibration": 0.0}:
        raise ValueError("requires frozen A3 objective for a single-factor comparison")
    value = copy.deepcopy(control)
    value["experiment_id"] = f"rp3_requested_balanced_v1_seed_{control['training']['seed']}"
    value["training"]["field_loss_normalization"] = "requested_balanced"
    value["training"]["record_field_diagnostics"] = True
    # Check all non-treatment settings before any learning takes place.
    old, new = copy.deepcopy(control), copy.deepcopy(value)
    old.pop("experiment_id"); new.pop("experiment_id")
    new["training"].pop("field_loss_normalization"); new["training"].pop("record_field_diagnostics")
    if old != new:
        raise ValueError("an undeclared treatment setting changed")
    return value


def checked_control(directory, seed):
    config = json.loads((directory / "config.json").read_text())
    manifest_path = directory / "bootstrap/training_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if stable_sha256({k: v for k, v in manifest.items() if k != "logical_sha256"}) != manifest["logical_sha256"]:
        raise ValueError("control manifest identity mismatch")
    if config["training"]["seed"] != seed or manifest["training_config"]["seed"] != seed:
        raise ValueError("control seed mismatch")
    # The serialized loss-weight config and normalizer must describe the saved run.
    if config["training"] != manifest["training_config"]:
        raise ValueError("control training config differs from saved manifest")
    checkpoint = directory / "bootstrap" / manifest["checkpoint_file"]
    history = directory / "bootstrap" / manifest["history_file"]
    if file_sha256(checkpoint) != manifest["checkpoint_sha256"] or file_sha256(history) != manifest["history_sha256"]:
        raise ValueError("control checkpoint/history binding mismatch")
    diagnostics = json.loads((directory / "diagnostics.json").read_text())
    predictions = directory / "predictions.jsonl"
    if file_sha256(predictions) != diagnostics["predictions_sha256"] or diagnostics["checkpoint_sha256"] != file_sha256(checkpoint):
        raise ValueError("control diagnostic/checkpoint binding mismatch")
    if diagnostics["config_sha256"] != file_sha256(directory / "config.json") or diagnostics["decoder"] != "full_local":
        raise ValueError("control decoder/config identity mismatch")
    if manifest["development_set"]["attached"]:
        raise ValueError("development input attached to control")
    rows = [json.loads(line) for line in predictions.read_text().splitlines()]
    return config, manifest, rows, {str(p): file_sha256(p) for p in
        (directory / "config.json", manifest_path, checkpoint, history, directory / "diagnostics.json", predictions)}


def internal_decision(reports, seeds):
    scalar = ("pointer_f1", "requested_raw_cardinality_accuracy")
    means = {}
    for arm in ("all_fields", "requested_balanced"):
        metrics = [reports[f"{arm}/{seed}"]["metrics"]["validation_original"]["scenario_macro"] for seed in seeds]
        means[arm] = {key: sum(m[key] for m in metrics) / len(seeds) for key in scalar}
        means[arm]["nonempty_target_raw_zero"] = sum(m["nonempty_target_raw_zero"]["mean"] for m in metrics) / len(seeds)
    old, new = means["all_fields"], means["requested_balanced"]
    safeguards = []
    for seed in seeds:
        a = reports[f"all_fields/{seed}"]["metrics"]["validation_all"]
        b = reports[f"requested_balanced/{seed}"]["metrics"]["validation_all"]
        safeguards.append({"seed": seed,
            "teacher_empty_no_increase": b["teacher_empty_false_fill"]["rate"] <= a["teacher_empty_false_fill"]["rate"],
            "no_available_false_fill_zero": b["no_available_false_fill"]["numerator"] == 0,
            "output_contract_passed": b["proposal_contract_violations"] == 0})
    checks = {"pointer_f1_increased": new["pointer_f1"] > old["pointer_f1"],
              "nonempty_raw_zero_decreased": new["nonempty_target_raw_zero"] < old["nonempty_target_raw_zero"],
              "requested_cardinality_not_lower": new["requested_raw_cardinality_accuracy"] >= old["requested_raw_cardinality_accuracy"],
              "all_seed_false_fill_safeguards": all(all(v for k, v in s.items() if k != "seed") for s in safeguards)}
    return {"status": "improved_under_prespecified_internal_rule" if all(checks.values()) else "improvement_not_established_under_prespecified_rule",
            "checks": checks, "original_validation_scenario_macro_seed_means": means, "safeguards": safeguards,
            "boundary": "internal two-scenario validation, not expert accuracy, not deployment authorization"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--protocol", default="configs/research_point_3/field_normalization_v1.json")
    args = p.parse_args()
    os.chdir(ROOT)
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    if protocol["schema"] != "rp3_field_normalization_protocol_v1" or protocol["seeds"] != [7042027, 7042028, 7042029]:
        raise ValueError("unexpected protocol or paired seeds")
    if protocol["development_attached"] or protocol["external_evaluation_allowed"] or protocol["deployment_allowed"]:
        raise ValueError("build-only nondeployment protocol required")
    if (protocol["control_mode"], protocol["treatment_mode"], protocol["requested_group_weight"], protocol["nonrequested_group_weight"]) != ("all_fields", "requested_balanced", .5, .5):
        raise ValueError("undeclared normalization weights")
    root = Path(protocol["output_root"])
    if root.exists():
        raise FileExistsError("existing experiment must be preserved; do not rerun")
    controls = {seed: checked_control(Path(protocol["control_root"]) / f"seed_{seed}" / "A3", seed) for seed in protocol["seeds"]}
    diagnostic_protocol = json.loads(Path(protocol["diagnostic_protocol"]).read_text())
    import torch
    if any(item[1]["runtime"]["torch"] != torch.__version__ for item in controls.values()):
        raise ValueError("runtime differs from paired controls")
    root.mkdir(parents=True)
    for seed, (config, manifest, rows, bindings) in controls.items():
        control_dir = root / f"seed_{seed}/all_fields"
        _write_immutable(control_dir / "config.json", canonical_json_bytes(config))
        _write_immutable(control_dir / "control_reference.json", canonical_json_bytes({"reused_without_training": True, "files": bindings}))
        _write_immutable(root / f"seed_{seed}/requested_balanced/config.json", canonical_json_bytes(treatment_config(config)))
    sources = [protocol_path, Path(protocol["diagnostic_protocol"]), Path("docs/RP3_FIELD_NORMALIZATION_V1_PROTOCOL.md"),
               Path(protocol["audit_root"]) / "audit.json", Path(__file__), Path("scripts/audit_rp3_field_supervision.py"),
               Path("scripts/train_rp3_lec.py"), Path("scripts/run_rp3_head_ablations.py"),
               *Path("src/research_point_3").glob("*.py"), *root.glob("seed_*/*/config.json")]
    snapshot = {"protocol": protocol, "files": {str(p): file_sha256(p) for p in sources},
                "control_files": {str(seed): item[3] for seed, item in controls.items()},
                "environment": {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "torch": torch.__version__}}
    _write_immutable(root / "protocol_snapshot.json", canonical_json_bytes(snapshot))
    with zipfile.ZipFile(root / "source_snapshot.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sources:
            archive.write(path, path.resolve().relative_to(ROOT))
    reports = {}
    env = {**os.environ, "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    for seed, (config, manifest, control_rows, bindings) in controls.items():
        directory = root / f"seed_{seed}/requested_balanced"
        command = [sys.executable, "-u", "scripts/train_rp3_lec.py", "--config", str(directory / "config.json"), "--output-dir", str(directory / "bootstrap")]
        print(f"[field normalization] seed={seed}; reuse C0, train C1", flush=True)
        with (directory / "execution.log").open("x") as log:
            process = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        if process.returncode:
            _write_immutable(directory / "failure.json", canonical_json_bytes({"returncode": process.returncode, "command": command}))
            raise RuntimeError(f"training failed; preserve {directory}")
        new_rows, diagnostic = diagnose_checkpoint(directory / "config.json", directory / "bootstrap", "full_local", diagnostic_protocol)
        if diagnostic["input_fingerprint"] != manifest["input_fingerprint"]:
            raise ValueError("treatment training inputs differ from control")
        expected = {r["trace_id"]: (r["split"], r["scenario_id"], r["teacher_selected_ids"], r["available_ids"], r["target_cardinalities"]) for r in control_rows}
        observed = {r["trace_id"]: (r["split"], r["scenario_id"], r["teacher_selected_ids"], r["available_ids"], r["target_cardinalities"]) for r in new_rows}
        if expected != observed:
            raise ValueError("paired row/label/split/availability mismatch")
        for arm, rows, best_epoch in (("all_fields", control_rows, manifest["best_epoch"]), ("requested_balanced", new_rows, diagnostic["best_epoch"])):
            out = root / f"seed_{seed}" / arm
            _write_immutable(out / "predictions.jsonl", canonical_jsonl_bytes(rows))
            report = {"arm": arm, "seed": seed, "best_epoch": best_epoch,
                      "metrics": grouped_field_metrics(rows), "predictions_sha256": file_sha256(out / "predictions.jsonl"),
                      "input_fingerprint": manifest["input_fingerprint"], "reused_control": arm == "all_fields",
                      "development_read": False, "external_read": False, "deployment_allowed": False}
            if arm == "requested_balanced":
                report["diagnostics"] = diagnostic
            _write_immutable(out / "task_metrics.json", canonical_json_bytes(report))
            reports[f"{arm}/{seed}"] = report
        # The copy used for reporting must never conceal modification of a control.
        for name, digest in bindings.items():
            if file_sha256(name) != digest:
                raise RuntimeError("a frozen control artifact changed")
    scalar_metrics = ("pointer_f1", "pointer_precision", "pointer_recall", "requested_raw_cardinality_accuracy", "requested_decoded_cardinality_accuracy")
    rate_metrics = ("nonempty_target_raw_zero", "nonempty_target_decoded_empty", "teacher_empty_false_fill", "no_available_false_fill")
    aggregates = []
    for subset in next(iter(reports.values()))["metrics"]:
        for arm in ("all_fields", "requested_balanced"):
            ms = [reports[f"{arm}/{seed}"]["metrics"][subset] for seed in protocol["seeds"]]
            aggregates.append({"arm": arm, "subset": subset, "rows_per_seed": ms[0]["rows"],
                "scenario_macro_seed_statistics": {key: seed_statistics([m["scenario_macro"][key] for m in ms]) for key in scalar_metrics},
                "scenario_macro_rate_seed_statistics": {key: (seed_statistics([m["scenario_macro"][key]["mean"] for m in ms])
                     if all(m["scenario_macro"][key]["mean"] is not None for m in ms) else None) for key in rate_metrics}})
    decision = internal_decision(reports, protocol["seeds"])
    result = {"schema": "rp3_field_normalization_results_v1", "protocol": protocol, "seed_reports": reports,
              "aggregate": aggregates, "decision": decision, "deployment_allowed": False}
    _write_immutable(root / "summary.json", canonical_json_bytes(result))
    stream = io.StringIO(); writer = csv.writer(stream)
    writer.writerow(["arm", "seed", "best_epoch", "subset", "rows", "scenarios", "raw_zero_n", "nonempty_n", "raw_zero_rate",
                     "decoded_empty_rate", "raw_cardinality_accuracy", "decoded_cardinality_accuracy", "pointer_f1",
                     "teacher_empty_false_fill_n", "teacher_empty_n", "teacher_empty_false_fill_rate", "no_available_false_fill_n", "no_available_n"])
    for report in reports.values():
        for subset, m in report["metrics"].items():
            z, e, n = m["nonempty_target_raw_zero"], m["teacher_empty_false_fill"], m["no_available_false_fill"]
            writer.writerow([report["arm"], report["seed"], report["best_epoch"], subset, m["rows"], m["scenario_count"], z["numerator"], z["denominator"], z["rate"],
                m["nonempty_target_decoded_empty"]["rate"], m["requested_raw_cardinality_accuracy"], m["requested_decoded_cardinality_accuracy"], m["pointer_f1"],
                e["numerator"], e["denominator"], e["rate"], n["numerator"], n["denominator"]])
    _write_immutable(root / "summary.csv", stream.getvalue().encode())
    lines = ["# 请求字段归一化：三种子配对构建集结果", "", f"预声明判断：`{decision['status']}`。仅内部诊断，不可部署。", "",
             "## 原始validation（每种子8条、2个场景）", "",
             "| 臂 | 种子 | 最佳epoch | 非空目标raw零预测 | 请求基数准确率 | Pointer F1 | 教师空集误填 | 零可用证据误填 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for report in reports.values():
        m = report["metrics"]["validation_original"]
        z, e, n = m["nonempty_target_raw_zero"], m["teacher_empty_false_fill"], m["no_available_false_fill"]
        lines.append(f"| {report['arm']} | {report['seed']} | {report['best_epoch']} | {z['numerator']}/{z['denominator']} | {m['requested_raw_cardinality_accuracy']:.4f} | {m['pointer_f1']:.4f} | {e['numerator']}/{e['denominator']} | {n['numerator']}/{n['denominator']} |")
    lines += ["", "## 预声明判断条件", ""]
    for name, passed in decision["checks"].items():
        lines.append(f"- {name}: {passed}")
    lines += ["", "全字段控制复用既有A3，无重训；新臂只改请求/非请求两组的CE归一化（各0.5），审计开关不参与更新或早停。",
              "0/0为无样本，不等于零风险。完整original/derived/all、train/validation、逐场景、三种子均值/SD/描述性区间见JSON/CSV。",
              "既有控制只保存epoch1最佳模型，不能据新臂逐epoch日志反推控制后续epoch的任务表现；新臂仍仅按预声明总validation loss选checkpoint。"]
    _write_immutable(root / "summary.md", ("\n".join(lines) + "\n").encode())
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
