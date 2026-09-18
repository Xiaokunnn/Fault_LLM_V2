#!/usr/bin/env python3
"""Execute the prespecified build-only, three-seed A1-A4 protocol once."""
from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research_point_3.artifacts import canonical_json_bytes, canonical_jsonl_bytes, file_sha256, _write_immutable
from src.research_point_3.ablations import ablation_row, ablation_summary, seed_statistics
from src.research_point_3.experiment_io import prepare, onnx_feed
from src.research_point_3.training import load_controller_checkpoint


def materialize_config(base, protocol, arm, seed):
    values = copy.deepcopy(base)
    for key in list(values):
        if key.startswith("development_") or key == "development":
            values.pop(key)
    values["experiment_id"] = f"rp3_head_ablation_v1_{arm}_seed_{seed}"
    values["training"]["seed"] = seed
    values["training"]["loss_weights"] = protocol["arms"][arm]["loss_weights"]
    values["ablation"] = {"protocol": "rp3_head_ablation_protocol_v1", "arm": arm,
                           "decoder": protocol["arms"][arm]["decoder"], "development_attached": False}
    return values


def diagnose_checkpoint(config, directory, decoder, diagnostic_protocol):
    import torch
    torch.set_num_threads(1)
    prepared = prepare(config, attach_development=False)
    manifest = json.loads((directory / "training_manifest.json").read_text())
    checkpoint = directory / manifest["checkpoint_file"]
    if file_sha256(checkpoint) != manifest["checkpoint_sha256"]:
        raise ValueError("ablation checkpoint hash mismatch")
    model, _ = load_controller_checkpoint(checkpoint, expected_input_fingerprint=prepared.input_fingerprint)
    model.eval()
    rows = []
    for dataset in (prepared.train_dataset, prepared.validation_dataset):
        for i, trace in enumerate(dataset.traces):
            with torch.no_grad():
                output = model(**{k: torch.from_numpy(v) for k, v in onnx_feed(dataset, i).items()})
            logits = [getattr(output, name).numpy() for name in ("rank_logits", "support_logits", "field_state_logits", "cardinality_logits", "route_logits")]
            rows.append(ablation_row(trace, dataset.records, logits, diagnostic_protocol, decoder))
    metrics = {}
    for split in ("train", "validation"):
        for kind in ("all", "original", "derived"):
            selected = [r for r in rows if r["split"] == split and
                        (kind == "all" or (r["perturbation_id"] == "original") == (kind == "original"))]
            if selected:
                metrics[split + "_" + kind] = ablation_summary(selected, diagnostic_protocol, decoder)
    return rows, {"status": "internal_fp32_checkpoint_diagnostics_not_deployable", "metrics": metrics,
                  "checkpoint_sha256": file_sha256(checkpoint), "input_fingerprint": prepared.input_fingerprint,
                  "config_sha256": file_sha256(config), "decoder": decoder,
                  "best_epoch": manifest["best_epoch"], "development_read": False, "external_read": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", default="configs/research_point_3/head_ablation_v1.json")
    args = parser.parse_args()
    os.chdir(ROOT)
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    if protocol["schema"] != "rp3_head_ablation_protocol_v1" or protocol["development_attached"] or protocol["deployment_allowed"]:
        raise ValueError("invalid build-only ablation protocol")
    if len(protocol["seeds"]) != 3 or len(set(protocol["seeds"])) != 3:
        raise ValueError("three distinct prespecified seeds required")
    root = Path(protocol["output_root"])
    if root.exists():
        raise FileExistsError("ablation output exists; preserve records, do not rerun the protocol")
    root.mkdir(parents=True)
    base = json.loads(Path(protocol["base_config"]).read_text())
    diagnostic_protocol = json.loads(Path(protocol["diagnostic_protocol"]).read_text())
    source_paths = [protocol_path, Path(protocol["base_config"]), Path(protocol["diagnostic_protocol"]),
                    Path("docs/RP3_HEAD_ABLATION_V1_PROTOCOL.md"), Path(__file__),
                    Path("scripts/train_rp3_lec.py"), Path("scripts/fit_rp3_route_head.py"),
                    *Path("src/research_point_3").glob("*.py")]
    _write_immutable(root / "protocol_snapshot.json", canonical_json_bytes({"protocol": protocol,
        "files": {str(p): file_sha256(p) for p in source_paths}, "subprocess_environment": {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}}))
    # All nine training configurations are materialized before the first training run.
    for seed in protocol["seeds"]:
        for arm in ("A1", "A2", "A3"):
            config_path = root / f"seed_{seed}" / arm / "config.json"
            _write_immutable(config_path, canonical_json_bytes(materialize_config(base, protocol, arm, seed)))
    summaries = {}
    environment = {**os.environ, "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    for seed in protocol["seeds"]:
        for arm in ("A1", "A2", "A3", "A4"):
            directory = root / f"seed_{seed}" / arm
            config_arm = "A3" if arm == "A4" else arm
            config_path = root / f"seed_{seed}" / config_arm / "config.json"
            directory.mkdir(exist_ok=True)
            if arm == "A4":
                model_dir = directory / "routed"
                command = [sys.executable, "-u", "scripts/fit_rp3_route_head.py", "--config", str(config_path),
                           "--training-dir", str(directory.parent / "A3/bootstrap"), "--output-dir", str(model_dir)]
            else:
                model_dir = directory / "bootstrap"
                command = [sys.executable, "-u", "scripts/train_rp3_lec.py", "--config", str(config_path), "--output-dir", str(model_dir)]
            print(f"[head ablation] seed={seed} arm={arm}", flush=True)
            with (directory / "execution.log").open("x") as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=environment)
            if result.returncode:
                _write_immutable(directory / "failure.json", canonical_json_bytes({"command": command, "exit_code": result.returncode}))
                raise RuntimeError(f"failed {arm}/{seed}; logs retained in {directory}")
            rows, summary = diagnose_checkpoint(config_path, model_dir, protocol["arms"][arm]["decoder"], diagnostic_protocol)
            _write_immutable(directory / "predictions.jsonl", canonical_jsonl_bytes(rows))
            summary["predictions_sha256"] = file_sha256(directory / "predictions.jsonl")
            _write_immutable(directory / "diagnostics.json", canonical_json_bytes(summary))
            summaries[f"{arm}/{seed}"] = summary
    # The route-only arm must preserve all non-route student selections exactly.
    for seed in protocol["seeds"]:
        parent = root / f"seed_{seed}"
        selected = []
        for arm in ("A3", "A4"):
            selected.append({r["trace_id"]: r["selected_ids"] for r in map(json.loads, (parent / arm / "predictions.jsonl").read_text().splitlines())})
        if selected[0] != selected[1]:
            raise RuntimeError("route-only fitting changed non-route selection")
    aggregate = []
    for arm in ("A1", "A2", "A3", "A4"):
        for subset in ("train_original", "validation_original", "train_all", "validation_all"):
            ms = [summaries[f"{arm}/{seed}"]["metrics"][subset] for seed in protocol["seeds"]]
            stats = {name: seed_statistics([m["scenario_aggregation"]["metrics"][name]["scenario_macro_mean"] for m in ms])
                     for name in ("exact_set_rate", "nonempty_exact_success_rate", "pointer_f1")}
            aggregate.append({"arm": arm, "subset": subset, "scenario_count": ms[0]["scenario_aggregation"]["independent_scenario_count"],
                "seed_nonempty_success_counts": [m["nonempty_exact_success"] for m in ms], "rows_per_seed": ms[0]["rows"],
                "scenario_macro_seed_statistics": stats,
                "seed_policy_utility_cost": [m["routing"]["ablation_policy"]["mean_declared_utility_cost"] for m in ms],
                "seed_policy_regret": [m["routing"]["ablation_policy"]["mean_route_regret"] for m in ms],
                "failed_training_seeds": 0,
                "seeds_with_no_nonempty_exact_success": sum(m["nonempty_exact_success"] == 0 for m in ms)})
    _write_immutable(root / "summary.json", canonical_json_bytes({"schema": "rp3_head_ablation_results_v1",
        "status": "internal_multiseed_ablation_not_deployable", "protocol": protocol, "results": aggregate,
        "seed_reports": summaries, "a3_a4_selections_identical": True,
        "uncertainty_boundary": "three seeds on the same build data; descriptive t intervals, not independent generalization"}))
    stream = io.StringIO(); writer = csv.writer(stream)
    writer.writerow(["arm", "subset", "scenarios", "seed", "nonempty_success", "rows", "scenario_macro_pointer_f1", "utility_cost", "regret"])
    for entry in aggregate:
        for i, seed in enumerate(protocol["seeds"]):
            m = summaries[f"{entry['arm']}/{seed}"]["metrics"][entry["subset"]]
            writer.writerow([entry["arm"], entry["subset"], entry["scenario_count"], seed, entry["seed_nonempty_success_counts"][i], entry["rows_per_seed"],
                m["scenario_aggregation"]["metrics"]["pointer_f1"]["scenario_macro_mean"], entry["seed_policy_utility_cost"][i], entry["seed_policy_regret"][i]])
    _write_immutable(root / "summary.csv", stream.getvalue().encode())
    lines = ["# 三种子逐头消融：内部构建集诊断", "", "未校准、不可部署；A1没有二值支持契约。仅描述三种训练种子的变化，不是独立外部精度。", "",
             "| 臂 | 子集 | 场景数 | 三种子非空成功数 | 每种子行数 | 场景宏平均Pointer F1：均值±样本SD | 95%描述性t区间 |",
             "|---|---|---:|---|---:|---:|---|"]
    for entry in aggregate:
        s = entry["scenario_macro_seed_statistics"]["pointer_f1"]
        lines.append(f"| {entry['arm']} | {entry['subset']} | {entry['scenario_count']} | {entry['seed_nonempty_success_counts']} | {entry['rows_per_seed']} | {s['mean']:.4f} ± {s['sample_std']:.4f} | {s['descriptive_t95_df2']} |")
    lines += ["", "全部种子及逐场景/逐行结果已保存。A3/A4全部指针选择逐条一致，Route只影响执行策略。",
              "不把派生行数作为独立样本；validation仅2个故障场景。区间不裁剪，不能解释为统计安全保证。"]
    _write_immutable(root / "summary.md", ("\n".join(lines) + "\n").encode())
    print(f"Completed head ablations: {root}", flush=True)


if __name__ == "__main__":
    main()
