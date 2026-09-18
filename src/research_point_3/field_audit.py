"""Read-only field-loss telemetry and task metrics, never model-selection logic."""
from collections import defaultdict

from .ablations import ablation_row
from .diagnostics import mean


def counted_rate(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "rate": numerator / denominator if denominator else None}


def field_task_metrics(rows):
    nonempty = [r for r in rows if r["target_cardinalities"][r["requested_index"]] > 0]
    teacher_empty = [r for r in rows if not r["teacher_selected_ids"]]
    unavailable = [r for r in rows if not r["available_ids"]]
    return {
        "rows": len(rows), "scenario_count": len({r["scenario_id"] for r in rows}),
        "nonempty_target_raw_zero": counted_rate(sum(r["raw_cardinalities"][r["requested_index"]] == 0 for r in nonempty), len(nonempty)),
        "nonempty_target_decoded_empty": counted_rate(sum(not r["selected_ids"] for r in nonempty), len(nonempty)),
        "requested_raw_cardinality_accuracy": mean(r["raw_cardinalities"][r["requested_index"]] == r["target_cardinalities"][r["requested_index"]] for r in rows),
        "requested_decoded_cardinality_accuracy": mean(r["decoded_cardinalities"][r["requested_index"]] == r["target_cardinalities"][r["requested_index"]] for r in rows),
        "pointer_precision": mean(r["pointer"]["precision"] for r in rows),
        "pointer_recall": mean(r["pointer"]["recall"] for r in rows),
        "pointer_f1": mean(r["pointer"]["f1"] for r in rows),
        "teacher_empty_false_fill": counted_rate(sum(bool(r["selected_ids"]) for r in teacher_empty), len(teacher_empty)),
        "no_available_false_fill": counted_rate(sum(bool(r["selected_ids"]) for r in unavailable), len(unavailable)),
        "nonempty_exact_success": sum(r["nonempty_exact_success"] for r in rows),
        "proposal_nonempty": sum(bool(r["selected_ids"]) for r in rows),
        "proposal_contract_violations": sum(not r["proposal_contract_passed"] for r in rows),
        "nonrequested_raw_nonzero": counted_rate(sum(r["raw_cardinalities"][j] != 0 for r in rows for j in range(4) if j != r["requested_index"]), 3 * len(rows)),
    }


def grouped_field_metrics(rows):
    result = {}
    for split in ("train", "validation"):
        for kind in ("all", "original", "derived"):
            subset = [r for r in rows if r["split"] == split and
                      (kind == "all" or (r["perturbation_id"] == "original") == (kind == "original"))]
            if not subset:
                continue
            metrics = field_task_metrics(subset)
            by_scenario = defaultdict(list)
            for row in subset:
                by_scenario[row["scenario_id"]].append(row)
            metrics["by_scenario"] = {key: field_task_metrics(value) for key, value in sorted(by_scenario.items())}
            scalar_names = ("pointer_precision", "pointer_recall", "pointer_f1", "requested_raw_cardinality_accuracy", "requested_decoded_cardinality_accuracy")
            metrics["scenario_macro"] = {key: mean(s[key] for s in metrics["by_scenario"].values()) for key in scalar_names}
            for key in ("nonempty_target_raw_zero", "nonempty_target_decoded_empty", "teacher_empty_false_fill", "no_available_false_fill"):
                eligible = [s[key]["rate"] for s in metrics["by_scenario"].values() if s[key]["rate"] is not None]
                metrics["scenario_macro"][key] = {"mean": mean(eligible), "eligible_scenarios": len(eligible)}
            result[split + "_" + kind] = metrics
    return result


class EpochFieldAudit:
    """Consume existing detached outputs; performs no extra forward pass or RNG use."""
    def __init__(self, dataset):
        self.traces = {t.trace_id: t for t in dataset.traces}
        self.records = dataset.records
        self.rows = []
        self.group_loss = {head: {group: [0.0, 0] for group in ("requested", "nonrequested")}
                           for head in ("field_state", "cardinality")}

    def observe(self, output, batch):
        import torch
        import torch.nn.functional as F
        mask = batch["requested_field_mask"].cpu().bool()
        if torch.any(mask.sum(dim=1) != 1):
            raise ValueError("field audit requires single-request-role rows")
        logits = [getattr(output, key).detach().cpu() for key in
                  ("rank_logits", "support_logits", "field_state_logits", "cardinality_logits", "route_logits")]
        for head, values in (("field_state", logits[2]), ("cardinality", logits[3])):
            losses = F.cross_entropy(values.flatten(0, 1), batch[head + "_labels"].cpu().flatten(), reduction="none").reshape_as(mask)
            for group, active in (("requested", mask), ("nonrequested", ~mask)):
                self.group_loss[head][group][0] += float(losses[active].sum())
                self.group_loss[head][group][1] += int(active.sum())
        protocol = {"support_threshold": 0.5, "route_confidence_threshold": 0.0}
        for index, trace_id in enumerate(batch["trace_id"]):
            row = ablation_row(self.traces[trace_id], self.records, [x[index:index+1].numpy() for x in logits], protocol, "full_local")
            self.rows.append(row)

    def summary(self):
        return {"group_ce": {head: {group: {"sum": total, "slots": count, "mean": total / count if count else None}
                                    for group, (total, count) in groups.items()}
                              for head, groups in self.group_loss.items()},
                "tasks": grouped_field_metrics(self.rows),
                "used_for_model_selection": False,
                "scope": "train batches are pre-update train-mode outputs; validation is fixed eval-mode checkpoint at epoch end"}
