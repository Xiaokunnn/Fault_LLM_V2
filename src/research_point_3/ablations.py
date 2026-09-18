"""Offline head-ablation decoders; rank-only proposals are never deployable."""
from __future__ import annotations

from collections import Counter
import math

import numpy as np

from .diagnostics import prediction_row, mean, summarize
from .evaluation import pointer_metrics


def ablation_row(trace, records, logits, protocol, decoder):
    if decoder not in {"rank_only", "rank_support", "full_local", "full"}:
        raise ValueError("unknown ablation decoder")
    row = prediction_row(trace, records, logits, protocol)
    row["decoder"] = decoder
    row["support_contract_enabled"] = decoder != "rank_only"
    if decoder in {"rank_only", "rank_support"}:
        candidates = list(trace.candidate_evidence_ids)
        scores = logits[0][0, :len(candidates)]
        probs = 1 / (1 + np.exp(-np.clip(logits[1][0, :len(candidates)], -80, 80)))
        selected = []
        selected_probabilities = []
        for i in np.argsort(-scores, kind="stable"):
            eid = candidates[i]
            if not trace.availability_mask[i] or eid not in records or records[eid].role != trace.query.requested_role:
                continue
            if decoder == "rank_support" and probs[i] < protocol["support_threshold"]:
                continue
            if len(selected) < trace.selection_budget:
                selected.append(eid)
                selected_probabilities.append(float(probs[i]))
        exact = set(selected) == set(trace.selected_evidence_ids)
        # A1 is only structurally eligible: this is explicitly NOT a supported production answer.
        row.update(selected_ids=selected, exact_set=exact, nonempty_exact_success=bool(selected) and exact,
                   eligible=bool(selected), pointer=pointer_metrics(selected, trace.selected_evidence_ids),
                   proposal_contract_passed=True, unknown_ids=[], unavailable_ids=[], wrong_role_ids=[])
        if decoder == "rank_support":
            row["local_confidence"] = min(selected_probabilities) if selected_probabilities else 0.0
            entropies = [-(p * math.log2(max(p, 1e-30)) + (1-p) * math.log2(max(1-p, 1e-30))) for p in selected_probabilities]
            row["local_normalized_entropy"] = mean(entropies) if entropies else 1.0
        else:
            row["local_confidence"] = 0.0
            row["local_normalized_entropy"] = 1.0
    if decoder != "full":
        row["decoded_action"] = "answer" if row["eligible"] else "abstain"
    return row


def ablation_summary(rows, protocol, decoder):
    result = summarize(rows, protocol)
    result["decoder"] = decoder
    result["trained_head_metrics_only"] = True
    result["deployment_allowed"] = False
    if decoder in {"rank_only", "rank_support"}:
        result["fields"] = None
    if decoder == "rank_only":
        result["support"] = None
        result["risk_coverage_min_selected_support"] = None
    if decoder != "full":
        result["raw_route_counts"] = None
        result["raw_route_target_by_prediction_confusion"] = None
        result["routing"] = {"ablation_policy": result["routing"]["R0_always_local"]}
    else:
        result["routing"] = {"ablation_policy": result["routing"]["cost_sensitive_route"]}
    result["answer_boundary"] = ("rank-only proposal; no learned support contract, internal unsafe comparison only"
                                 if decoder == "rank_only" else "internal teacher-relative proposal, not calibrated deployment")
    return result


def seed_statistics(values):
    """Predeclared three-seed descriptive t interval; never clip its endpoints."""
    values = np.asarray(values, dtype=float)
    if len(values) != 3 or not np.isfinite(values).all():
        raise ValueError("the declared protocol requires exactly three finite seed values")
    center = float(values.mean())
    std = float(values.std(ddof=1))
    half_width = 4.302652729911275 * std / math.sqrt(3)
    return {"seeds": 3, "mean": center, "sample_std": std, "min": float(values.min()),
            "max": float(values.max()), "descriptive_t95_df2": [center - half_width, center + half_width]}
