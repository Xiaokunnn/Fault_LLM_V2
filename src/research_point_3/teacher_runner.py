"""Offline RP2 teacher replay adapter; upstream functions remain unmodified."""
from __future__ import annotations

import sys
from dataclasses import replace
from .artifacts import stable_sha256
from .contracts import ContractError

def capture_scored_pool(function, *args, **kwargs):
    """Observe RP2's actual pre-selection pool at return, without changing K.

    Deliberately offline and single-threaded. Increasing RP2's selection budget
    to 32 would change family-cap semantics. A profile hook instead copies only
    the local scored list and restores any caller profile even on exceptions.
    This instrumentation is excluded from all deployment latency claims.
    """
    captured = []
    previous = sys.getprofile()
    def observer(frame, event, arg):
        if frame.f_code is function.__code__ and event == "return":
            captured.extend(frame.f_locals.get("scored", ()))
        if previous is not None:
            previous(frame, event, arg)
    sys.setprofile(observer)
    try:
        result = function(*args, **kwargs)
    finally:
        sys.setprofile(previous)
    if len(captured) != result.scored_candidates:
        raise ContractError("RP2 pool capture failed; upstream implementation may have changed")
    return result, tuple(captured)

def replay_candidates(query, candidates, graph_index, dense_index, encoder, config):
    from src.research_point_2.graph_rag_v2 import retrieve_dense_graph
    from src.research_point_2.retrieval import RetrievalBudget
    values = config["retrieval"]
    budget = RetrievalBudget(**{k: values[k] for k in (
        "max_scored_candidates", "max_per_source_family", "source_family_bonus", "redundancy_penalty"
    )}, max_selected_evidence=3)
    return capture_scored_pool(
        retrieve_dense_graph, query, candidates, graph_index, dense_index, encoder,
        method="dense_ours_v4", budget=budget,
        **{k: values[k] for k in ("dense_top_n", "anchor_evidence_count", "fixed_hops",
            "ours_graph_hops", "ours_graph_decay", "graph_score_weight",
            "fault_affinity_weight", "fault_affinity_floor")},
    )

def verify_selection(query, retrieval, evidence, generator, config, cache_dir, identity, suffix="base"):
    # Exactly the RP2 two-stage verifier and coverage guard, including K=3.
    from scripts.run_rp2_equal_budget_v6 import _run_measurement, system_prompt_for_strategy
    scenario = next(x for x in config["scenarios"] if x["id"] == "Ours_v6_k3_equal")
    return _run_measurement(
        repeat=0, method_order=[scenario["id"]], scenario=scenario, query=query,
        retrieval=retrieval, evidence=evidence, generator=generator,
        contract=config["generation_contract"],
        stage1_system=system_prompt_for_strategy("evidence_mask_v3"),
        stage1_max_new_tokens=config["generator"]["stage1_max_new_tokens"],
        review_max_new_tokens=config["generator"]["review_max_new_tokens"],
        cache_dir=cache_dir, model_identity=identity, protocol_version="rp3_teacher_replay_v2",
        protocol_fingerprint=stable_sha256({"identity": identity, "config": config, "suffix": suffix}),
        force_generation=False,
    )

def compile_candidate_row(query, retrieval, pool, base_run, tail_runs):
    """Keep base teacher selection separate from auxiliary tail support labels."""
    base_ids = [x.evidence_id for x in retrieval.ranked]
    pool_by_id = {x.evidence_id: (x, score) for x, score in pool}
    ids = base_ids + [x.evidence_id for x, _ in pool if x.evidence_id not in base_ids]
    support = dict(zip(base_ids, base_run["final_mask"]))
    for eid, run in tail_runs.items():
        if not run["cascade_contract_valid"]:
            raise ContractError(f"invalid auxiliary verifier response: {eid}")
        support[eid] = run["final_mask"][0]
    if not base_run["cascade_contract_valid"] or set(support) != set(ids):
        raise ContractError("incomplete or invalid teacher support decisions")
    selected = [eid for point in base_run["answer"]["answer_points"] for eid in point["evidence_ids"]]
    return {
        "schema": "rp3_teacher_candidate_trace_v1", "query_id": query.query_id,
        "teacher_method": "Ours_v6_k3_equal", "perturbation_id": "original",
        "candidates": [{"evidence_id": eid, "available": True,
            "score": float(len(ids)-index), "raw_base_score": float(pool_by_id[eid][1])}
            for index, eid in enumerate(ids)],
        "ranking_target": "RP2_selected_prefix_then_remaining_base_score_order",
        "final_support_by_evidence_id": support, "selected_evidence_ids": selected,
        "underfill_reason_codes": ["frozen_RP2_active_underfill"] if len(selected) < 3 else [],
        "rp2_selected_before_verifier": base_ids,
        "route": {"action": "answer" if selected else "abstain",
            "reason_codes": ["teacher_acceptance_only_route_learning_pending"],
            "estimated_student_cost": 0.0, "estimated_teacher_cost": 0.0,
            "estimated_error_cost": 0.0, "confidence": 1.0},
        # Explicit unlabelled placeholders; tensorizer masks ALL route losses.
        "route_action_costs": {"answer": 0.0, "fallback": 0.0, "abstain": 0.0},
        "route_supervision_status": "pending_student_rollout",
        "route_cost_boundary": "unlabelled_zero_placeholders_not_measured_costs",
        "base_verifier_run": base_run, "auxiliary_tail_verifier_runs": tail_runs,
        "auxiliary_tail_may_change_base_selection": False,
    }
