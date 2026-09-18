#!/usr/bin/env python3
"""Audit build-only field labels, existing loss histories and saved checkpoints."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, file_sha256, _write_immutable
from src.research_point_3.contracts import CARD_SLOT_ROLES
from src.research_point_3.experiment_io import prepare, onnx_feed
from src.research_point_3.training import load_controller_checkpoint


def label_counts(traces):
    counts = {key: Counter() for key in ("requested", "nonrequested", "all")}
    states = {key: Counter() for key in counts}
    for trace in traces:
        requested = CARD_SLOT_ROLES.index(trace.query.requested_role)
        for index, slot in enumerate(trace.diagnosis_card.slots):
            group = "requested" if index == requested else "nonrequested"
            for key in (group, "all"):
                counts[key][len(slot.items)] += 1
                states[key][slot.state.value] += 1
    return {key: {"slots": sum(values.values()), "cardinality_counts": dict(values),
                  "zero_count": values[0], "zero_fraction": values[0] / sum(values.values()),
                  "state_counts": dict(states[key])} for key, values in counts.items()}


def history_audit(directory):
    manifest = json.loads((directory / "training_manifest.json").read_text())
    history_path = directory / manifest["history_file"]
    if file_sha256(history_path) != manifest["history_sha256"]:
        raise ValueError("training history hash mismatch")
    history = [json.loads(line) for line in history_path.read_text().splitlines()]
    weights = manifest["training_config"]["loss_weights"]
    rows = []
    for item in history:
        weighted = {split: {key: weights[key] * item[split]["intervention_augmented_supervision" if key == "intervention" else key]
                            for key in weights} for split in ("train", "validation")}
        for split in weighted:
            if abs(sum(weighted[split].values()) - item[split]["total"]) > 1e-5:
                raise ValueError("weighted components do not reconstruct saved loss")
        rows.append({"epoch": item["epoch"], "weighted": weighted, "saved": item})
    first, last = rows[0], rows[-1]
    delta = {split: {key: last["weighted"][split][key] - first["weighted"][split][key]
                     for key in weights} for split in ("train", "validation")}
    return {"best_epoch": manifest["best_epoch"], "epochs_executed": len(history), "rows": rows,
            "last_minus_first_weighted": delta, "history_sha256": file_sha256(history_path)}


def checkpoint_field_loss(directory, prepared):
    import torch
    import torch.nn.functional as F
    torch.set_num_threads(1)
    manifest = json.loads((directory / "training_manifest.json").read_text())
    checkpoint = directory / manifest["checkpoint_file"]
    if file_sha256(checkpoint) != manifest["checkpoint_sha256"]:
        raise ValueError("checkpoint hash mismatch")
    model, _ = load_controller_checkpoint(checkpoint, expected_input_fingerprint=prepared.input_fingerprint)
    model.eval()
    result = {}
    for dataset in (prepared.train_dataset, prepared.validation_dataset):
        sums = {head: {group: [0.0, 0] for group in ("requested", "nonrequested", "requested_nonempty", "requested_empty")}
                for head in ("field_state", "cardinality")}
        for i, trace in enumerate(dataset.traces):
            with torch.no_grad():
                output = model(**{k: torch.from_numpy(v) for k, v in onnx_feed(dataset, i).items()})
            row = dataset[i]
            requested = CARD_SLOT_ROLES.index(trace.query.requested_role)
            for head in sums:
                logits = getattr(output, head + "_logits")[0]
                losses = F.cross_entropy(logits, row[head + "_labels"], reduction="none")
                for j, loss in enumerate(losses.tolist()):
                    groups = ["requested" if j == requested else "nonrequested"]
                    if j == requested:
                        groups.append("requested_nonempty" if row["cardinality_labels"][j] > 0 else "requested_empty")
                    for group in groups:
                        sums[head][group][0] += loss; sums[head][group][1] += 1
        stats = {}
        for head, groups in sums.items():
            total = groups["requested"][0] + groups["nonrequested"][0]
            stats[head] = {key: {"loss_sum": value, "slots": n, "mean_ce": value / n if n else None}
                           for key, (value, n) in groups.items()}
            stats[head]["nonrequested_share_of_all_slot_ce"] = groups["nonrequested"][0] / total if total else None
        result[dataset.traces[0].split.value] = stats
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", default="results/experiments/research_point_3/field_supervision_audit_v1")
    args = p.parse_args()
    out = Path(args.output_dir)
    if out.exists():
        raise FileExistsError("audit report exists; preserve it")
    root = Path("results/experiments/research_point_3/head_ablation_v1")
    prepared = prepare(root / "seed_7042027/A3/config.json", attach_development=False)
    labels = {}
    for ds in (prepared.train_dataset, prepared.validation_dataset):
        for kind in ("all", "original", "derived"):
            traces = [t for t in ds.traces if kind == "all" or (t.perturbation_id == "original") == (kind == "original")]
            labels[ds.traces[0].split.value + "_" + kind] = label_counts(traces)
    histories, checkpoints = {}, {}
    for seed in (7042027, 7042028, 7042029):
        for arm in ("A1", "A2", "A3"):
            key = f"{arm}/{seed}"
            directory = root / f"seed_{seed}" / arm / "bootstrap"
            histories[key] = history_audit(directory)
            if arm == "A3":
                checkpoints[key] = checkpoint_field_loss(directory, prepared)
    result = {"schema": "rp3_field_supervision_audit_v1", "labels": labels, "histories": histories,
              "saved_a3_checkpoint_field_losses": checkpoints, "input_fingerprint": prepared.input_fingerprint,
              "development_read": False, "external_read": False,
              "boundary": "saved epoch-1 checkpoints only; no claims about unavailable later-epoch per-slot logits or gradients"}
    _write_immutable(out / "audit.json", canonical_json_bytes(result))
    lines = ["# 字段监督与既有早停审计", "", "仅构建集，未重训；标签占比不等于实际梯度贡献。", "",
             "| 子集 | 请求字段零数量 | 非请求字段零数量 | 全字段零数量 |", "|---|---:|---:|---:|"]
    for subset, row in labels.items():
        cells = [f"{row[g]['zero_count']}/{row[g]['slots']} ({row[g]['zero_fraction']:.2%})" for g in ("requested", "nonrequested", "all")]
        lines.append(f"| {subset} | " + " | ".join(cells) + " |")
    lines += ["", "| 臂/种子 | 最优epoch | 已跑epochs | validation rank增量 | support增量 | field增量 | cardinality增量 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for key, item in histories.items():
        delta = item["last_minus_first_weighted"]["validation"]
        lines.append(f"| {key} | {item['best_epoch']} | {item['epochs_executed']} | {delta['ranking']:.4f} | {delta['support']:.4f} | {delta['field_state']:.4f} | {delta['cardinality']:.4f} |")
    lines += ["", "## A3最佳checkpoint的非请求字段CE贡献占比", "", "| 种子 | split | field CE占比 | cardinality CE占比 |", "|---|---|---:|---:|"]
    for key, splits in checkpoints.items():
        for split, stats in splits.items():
            lines.append(f"| {key} | {split} | {stats['field_state']['nonrequested_share_of_all_slot_ce']:.2%} | {stats['cardinality']['nonrequested_share_of_all_slot_ce']:.2%} |")
    lines += ["", "旧训练只保存最优checkpoint；后续epoch只有分项历史，不能恢复其逐字段CE或任务质量。上述增量为最后epoch减epoch1，使用实际损失权重。"]
    _write_immutable(out / "audit.md", ("\n".join(lines) + "\n").encode())
    print(out)


if __name__ == "__main__":
    main()
