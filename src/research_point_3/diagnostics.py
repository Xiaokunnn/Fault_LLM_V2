"""Build-only, teacher-relative diagnostics. Never issues deployment certificates."""
from __future__ import annotations

from collections import Counter, defaultdict
import math

import numpy as np

from .contracts import CARD_SLOT_ROLES, SupportVerdict
from .evaluation import binary_classification_metrics, pointer_metrics
from .experiment_io import decode_row
from .model import CARD_FIELD_STATES, ROUTE_ACTIONS


def mean(values):
    values = list(values)
    return float(np.mean(values)) if values else None


def binary_summary(probabilities, labels, *, threshold=0.5, bins=10):
    """Tie-grouped average precision; ECE uses positive-class probabilities."""
    if len(probabilities) != len(labels) or bins < 1:
        raise ValueError("invalid binary metric inputs")
    if not labels:
        return {"count": 0, "positive_count": 0, "precision": None, "recall": None,
                "f1": None, "brier": None, "auprc_average_precision": None, "ece": None}
    result = binary_classification_metrics(probabilities, labels, threshold=threshold)
    grouped = defaultdict(list)
    for p, y in zip(probabilities, labels):
        grouped[float(p)].append(int(y))
    positives = sum(labels)
    ap = tp = seen = 0
    for score in sorted(grouped, reverse=True):
        ys = grouped[score]
        new_tp = sum(ys)
        tp += new_tp
        seen += len(ys)
        ap += new_tp * tp / seen
    buckets = defaultdict(list)
    for p, y in zip(probabilities, labels):
        buckets[min(int(p * bins), bins - 1)].append((p, y))
    ece = sum(len(xs) / len(labels) * abs(mean(p for p, _ in xs) - mean(y for _, y in xs))
              for xs in buckets.values())
    return {**result, "count": len(labels), "positive_count": int(positives),
            "auprc_average_precision": ap / positives if positives else None, "ece": ece}


def risk_coverage(rows, score_key="local_confidence"):
    """Achievable confidence thresholds, grouping ties without consulting errors.

    Only nonempty contract-eligible proposals can be accepted. AURC is integrated
    over reachable coverage, never extrapolated to ineligible/empty proposals.
    """
    groups = defaultdict(list)
    for row in rows:
        if row["eligible"]:
            groups[row[score_key]].append(row)
    curve = []
    count = errors = 0
    area = previous = 0.0
    for score in sorted(groups, reverse=True):
        xs = groups[score]
        count += len(xs)
        errors += sum(not x["exact_set"] for x in xs)
        coverage, risk = count / len(rows), errors / count
        area += (coverage - previous) * risk
        previous = coverage
        curve.append({"threshold": score, "answers": count, "coverage": coverage,
                      "errors": errors, "risk": risk})
    return {"curve": curve, "maximum_coverage": previous,
            "aurc_reachable": area if count else None,
            "aurc_normalized_to_reachable_coverage": area / previous if count else None}


def action_costs(row, profile):
    success = row["eligible"] and row["exact_set"]
    return {"answer": profile["local"] + profile["error"] * (not success),
            "fallback": profile["local"] + profile["teacher"]
                        + profile["error"] * (not bool(row["teacher_selected_ids"])),
            "abstain": profile["review"]}


def policy_action(row, policy, config):
    if policy == "R1_always_teacher":
        return "fallback"
    if policy == "R2_always_abstain":
        return "abstain"
    if policy == "cost_sensitive_route":
        return row["decoded_action"] if row["eligible"] or row["decoded_action"] != "answer" else "abstain"
    if policy == "R0_always_local":
        return "answer" if row["eligible"] else "abstain"
    if policy == "R3_confidence":
        accept = row["local_confidence"] >= config["simple_confidence_threshold"]
    elif policy == "R3_entropy":
        accept = row["local_normalized_entropy"] <= config["simple_normalized_entropy_threshold"]
    else:
        raise ValueError(f"unknown diagnostic policy: {policy}")
    return "answer" if row["eligible"] and accept else "fallback"


def routing_summary(rows, policy, config):
    actions = [policy_action(r, policy, config) for r in rows]
    costs = [action_costs(r, config["costs"]) for r in rows]
    optimum = [min(ROUTE_ACTIONS, key=lambda a: c[a]) for c in costs]
    answered = [r for r, a in zip(rows, actions) if a == "answer"]
    teacher_answers = sum(a == "fallback" and bool(r["teacher_selected_ids"])
                         for a, r in zip(actions, rows))
    confusion = {target: {action: 0 for action in ROUTE_ACTIONS} for target in ROUTE_ACTIONS}
    for target, action in zip(optimum, actions):
        confusion[target][action] += 1
    count = Counter(actions)
    return {"actions": {a: count[a] for a in ROUTE_ACTIONS},
            "local_answer_coverage": len(answered) / len(rows),
            "local_teacher_disagreement": mean(not r["exact_set"] for r in answered),
            "fallback_rate": count["fallback"] / len(rows),
            "abstain_rate": count["abstain"] / len(rows),
            "replayed_teacher_calls": count["fallback"], "actual_teacher_calls": 0,
            "teacher_call_avoidance_fraction": 1 - count["fallback"] / len(rows),
            "replayed_final_answer_coverage": (len(answered) + teacher_answers) / len(rows),
            "mean_declared_utility_cost": mean(c[a] for c, a in zip(costs, actions)),
            "mean_route_regret": mean(c[a] - min(c.values()) for c, a in zip(costs, actions)),
            "counterfactual_target_counts": dict(Counter(optimum)),
            "target_by_predicted_confusion": confusion}


def prediction_row(trace, records, logits, config):
    decoded = decode_row(logits, trace, records, support_threshold=config["support_threshold"],
                         minimum_route_confidence=config["route_confidence_threshold"])
    candidate_ids = list(trace.candidate_evidence_ids)
    available = {eid for eid, avail in zip(candidate_ids, trace.availability_mask) if avail}
    selected = list(decoded.selected_evidence_ids)
    unknown = [eid for eid in selected if eid not in records or eid not in candidate_ids]
    unavailable = [eid for eid in selected if eid not in available]
    wrong_role = [eid for eid in selected if eid in records and records[eid].role != trace.query.requested_role]
    contract = (not unknown and not unavailable and not wrong_role
                and len(selected) <= trace.selection_budget and len(set(selected)) == len(selected))
    support_probabilities, support_labels = [], []
    not_assessed = 0
    for decision, avail, prob in zip(trace.evidence_decisions, trace.availability_mask,
                                     decoded.support_probabilities):
        if not avail:
            continue
        if decision.support == SupportVerdict.NOT_ASSESSED:
            not_assessed += 1
            continue
        support_probabilities.append(float(prob))
        support_labels.append(int(decision.support == SupportVerdict.DIRECT))
    requested = CARD_SLOT_ROLES.index(trace.query.requested_role)
    raw_states = [CARD_FIELD_STATES[int(x)] for x in np.argmax(logits[2][0], axis=-1)]
    raw_counts = np.argmax(logits[3][0], axis=-1).astype(int).tolist()
    target_states = [slot.state.value for slot in trace.diagnosis_card.slots]
    target_counts = [len(slot.items) for slot in trace.diagnosis_card.slots]
    probs = dict(zip(candidate_ids, decoded.support_probabilities))
    chosen_probabilities = [float(probs[eid]) for eid in selected if eid in probs]
    entropies = [-(p * math.log2(max(p, 1e-30)) + (1-p) * math.log2(max(1-p, 1e-30)))
                 for p in chosen_probabilities]
    route = np.asarray(logits[4][0], dtype=float)
    route = np.exp(route - route.max())
    route /= route.sum()
    teacher_ids = list(trace.selected_evidence_ids)
    rank_top = [eid for eid in decoded.ranked_evidence_ids if eid in available][:trace.selection_budget]
    pointer = pointer_metrics(selected, teacher_ids)
    return {"trace_id": trace.trace_id, "scenario_id": trace.query.scenario_id,
            "split": trace.split.value, "perturbation_id": trace.perturbation_id,
            "parent_trace_id": trace.metadata.get("parent_trace_id"),
            "teacher_selected_ids": teacher_ids, "selected_ids": selected,
            "available_ids": sorted(available), "exact_set": set(selected) == set(teacher_ids),
            "nonempty_exact_success": bool(selected) and set(selected) == set(teacher_ids),
            "pointer": pointer,
            "rank_ndcg_at_budget": pointer_metrics(rank_top, teacher_ids)["ndcg"] if teacher_ids else None,
            "proposal_contract_passed": bool(contract), "eligible": bool(selected) and bool(contract),
            "unknown_ids": unknown, "unavailable_ids": unavailable, "wrong_role_ids": wrong_role,
            "support_probabilities": support_probabilities, "support_labels": support_labels,
            "support_not_assessed_available": not_assessed,
            "requested_index": requested, "raw_field_states": raw_states, "raw_cardinalities": raw_counts,
            "target_field_states": target_states, "target_cardinalities": target_counts,
            "decoded_field_states": [f.state.value for f in decoded.card_fields],
            "decoded_cardinalities": [f.cardinality for f in decoded.card_fields],
            "raw_route_action": ROUTE_ACTIONS[int(np.argmax(route))],
            "route_probabilities": route.tolist(), "decoded_action": decoded.route_action.value,
            "local_confidence": min(chosen_probabilities) if chosen_probabilities else 0.0,
            "local_normalized_entropy": mean(entropies) if entropies else 1.0}


def scenario_summary(rows, config):
    groups = defaultdict(list)
    for row in rows:
        groups[row["scenario_id"]].append(row)
    scenarios = [{"scenario_id": k, "rows": len(xs),
                  "exact_set_rate": mean(x["exact_set"] for x in xs),
                  "nonempty_exact_success_rate": mean(x["nonempty_exact_success"] for x in xs),
                  "pointer_f1": mean(x["pointer"]["f1"] for x in xs)}
                 for k, xs in sorted(groups.items())]
    stats = {}
    rng = np.random.default_rng(config["bootstrap_seed"])
    for key in ("exact_set_rate", "nonempty_exact_success_rate", "pointer_f1"):
        values = np.asarray([x[key] for x in scenarios])
        sampled = rng.choice(values, size=(config["bootstrap_replicates"], len(values)), replace=True).mean(axis=1)
        stats[key] = {"scenario_macro_mean": float(values.mean()),
                      "descriptive_cluster_bootstrap_95_interval": np.percentile(sampled, [2.5, 97.5]).tolist()}
    return {"independent_scenario_count": len(scenarios), "scenarios": scenarios, "metrics": stats,
            "warning": "descriptive resampling of scenario groups; not seed variance, not independent external evaluation; few groups give unstable intervals"}


def summarize(rows, config):
    if not rows:
        return None
    probabilities = [v for r in rows for v in r["support_probabilities"]]
    labels = [v for r in rows for v in r["support_labels"]]
    metrics = {"rows": len(rows), "teacher_nonempty": sum(bool(r["teacher_selected_ids"]) for r in rows),
               "student_nonempty": sum(bool(r["selected_ids"]) for r in rows),
               "set_exact_including_empty": sum(r["exact_set"] for r in rows),
               "set_exact_rate_including_empty": mean(r["exact_set"] for r in rows),
               "nonempty_exact_success": sum(r["nonempty_exact_success"] for r in rows),
               "pointer_macro": {k: mean(r["pointer"][k] for r in rows) for k in ("precision", "recall", "f1")},
               "rank_ndcg_at_budget_nonempty_teacher": mean(r["rank_ndcg_at_budget"] for r in rows if r["rank_ndcg_at_budget"] is not None),
               "support": binary_summary(probabilities, labels, threshold=config["support_threshold"], bins=config["ece_bins"]),
               "support_not_assessed_excluded": sum(r["support_not_assessed_available"] for r in rows),
               "unknown_id_count": sum(len(r["unknown_ids"]) for r in rows),
               "unavailable_id_count": sum(len(r["unavailable_ids"]) for r in rows),
               "proposal_id_role_budget_contract_pass_rate": mean(r["proposal_contract_passed"] for r in rows),
               "raw_route_counts": dict(Counter(r["raw_route_action"] for r in rows))}
    fields = {}
    for mode in ("raw", "decoded"):
        for scope in ("all_slots", "requested_slot"):
            pairs = [(r, j) for r in rows for j in (range(len(CARD_SLOT_ROLES)) if scope == "all_slots" else [r["requested_index"]])]
            fields[mode + "_" + scope] = {
                "state_accuracy": mean(r[mode + "_field_states"][j] == r["target_field_states"][j] for r, j in pairs),
                "cardinality_accuracy": mean(r[mode + "_cardinalities"][j] == r["target_cardinalities"][j] for r, j in pairs),
                "empty_target_cardinality_accuracy": mean(r[mode + "_cardinalities"][j] == 0 for r, j in pairs if r["target_cardinalities"][j] == 0),
                "nonempty_target_cardinality_accuracy": mean(r[mode + "_cardinalities"][j] == r["target_cardinalities"][j] for r, j in pairs if r["target_cardinalities"][j] > 0),
                "nonempty_target_predicted_zero_count": sum(r[mode + "_cardinalities"][j] == 0 for r, j in pairs if r["target_cardinalities"][j] > 0)}
    metrics["fields"] = fields
    metrics["routing"] = {policy: routing_summary(rows, policy, config) for policy in
                          ("R0_always_local", "R1_always_teacher", "R2_always_abstain", "R3_confidence", "R3_entropy", "cost_sensitive_route")}
    raw_confusion = {a: {b: 0 for b in ROUTE_ACTIONS} for a in ROUTE_ACTIONS}
    for row in rows:
        costs = action_costs(row, config["costs"])
        target = min(ROUTE_ACTIONS, key=lambda a: costs[a])
        raw_confusion[target][row["raw_route_action"]] += 1
    metrics["raw_route_target_by_prediction_confusion"] = raw_confusion
    metrics["risk_coverage_min_selected_support"] = risk_coverage(rows)
    metrics["scenario_aggregation"] = scenario_summary(rows, config)
    by_id = {r["trace_id"]: r for r in rows}
    pairs = [(by_id[r["parent_trace_id"]], r) for r in rows if r["parent_trace_id"] in by_id]
    def sign(x):
        return (x > 0) - (x < 0)
    metrics["intervention"] = {
        "parent_child_pairs": len(pairs),
        "selection_count_direction_agreement": mean(
            sign(len(c["selected_ids"]) - len(p["selected_ids"])) ==
            sign(len(c["teacher_selected_ids"]) - len(p["teacher_selected_ids"])) for p, c in pairs),
        "removed_selected_id_violations": sum(bool(set(c["selected_ids"]) - set(c["available_ids"])) for _, c in pairs),
        "boundary": "count-change sign including zero; not paired directional training loss or full-graph intervention"}
    timings = [t for r in rows for t in r.get("controller_timings_ms", [])]
    metrics["controller_only_latency_ms"] = {"samples": len(timings),
        "p50": float(np.percentile(timings, 50)) if timings else None,
        "p95": float(np.percentile(timings, 95)) if timings else None}
    return metrics
