"""CPU-only checks for newly executable RP3 preparation boundaries."""
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pytest
from src.research_point_3.features import HashingFeatureProvider, hash_text, query_vector, evidence_vector
from src.research_point_3.teacher_runner import capture_scored_pool, compile_candidate_row
from src.research_point_3.trace_export import export_candidate_decisions
from src.research_point_3.contracts import ContractError, QueryContext, DiagnosticRole

def query():
    return QueryContext("Q1","泵振动的原因是什么？","F01","泵振动",DiagnosticRole.CAUSE_OR_MECHANISM,"scenario1")

def test_hash_features_deterministic_and_query_id_independent():
    a=query()
    assert query_vector(a)==query_vector(replace(a,query_id="unseen",scenario_id="unseen"))
    assert hash_text("Ａ B")==hash_text("ab")
    assert len(query_vector(a))==256
    assert abs(sum(x*x for x in query_vector(a))-1)<1e-10
    assert query_vector(a)!=query_vector(replace(a,question_zh="如何维护密封？"))

def test_unavailable_feature_never_reads_record():
    class Candidate:
        available=False
        @property
        def record(self):
            raise AssertionError("unavailable content accessed")
    q,e=HashingFeatureProvider().features_for(query=query(),candidates=(Candidate(),),query_dimension=256,evidence_dimension=288)
    assert e==((0.0,)*288,)

def test_capture_restores_profile_and_keeps_original_budget():
    def selector(k):
        scored=[("E1",0.8),("E2",0.4)]
        return SimpleNamespace(scored_candidates=len(scored),selected=scored[:k])
    old=sys.getprofile()
    result,pool=capture_scored_pool(selector,1)
    assert result.selected==[("E1",0.8)]
    assert len(pool)==2
    assert sys.getprofile() is old

def test_capture_restores_on_failure():
    def fail():
        raise ValueError("test")
    old=sys.getprofile()
    with pytest.raises(ValueError):
        capture_scored_pool(fail)
    assert sys.getprofile() is old

def test_empty_real_teacher_pool_is_not_filled_with_fake_candidates():
    run={"final_mask":[],"cascade_contract_valid":True,"answer":{"answer_points":[]}}
    row=compile_candidate_row(SimpleNamespace(query_id="Q1"),SimpleNamespace(ranked=()),(),run,{})
    exported=export_candidate_decisions(row,candidate_count_policy="at_most")
    assert exported.candidate_ids==()
    assert row["route"]["action"]=="abstain"
    assert row["route_supervision_status"]=="pending_student_rollout"
    with pytest.raises(ContractError):
        export_candidate_decisions(row) # legacy exact-width mode must still reject

def test_teacher_tail_support_cannot_change_base_selection():
    r=SimpleNamespace(evidence_id="E1")
    t=SimpleNamespace(evidence_id="E2")
    base={"final_mask":[0],"cascade_contract_valid":True,"answer":{"answer_points":[]}}
    tail={"final_mask":[1],"cascade_contract_valid":True}
    row=compile_candidate_row(SimpleNamespace(query_id="Q1"),SimpleNamespace(ranked=(r,)),((r,0.9),(t,0.8)),base,{"E2":tail})
    assert row["selected_evidence_ids"]==[]
    assert row["final_support_by_evidence_id"]["E2"]==1
    assert len(export_candidate_decisions(row,candidate_count_policy="at_most").candidate_ids)==2

def test_invalid_auxiliary_tail_is_unassessed_not_negative():
    r=SimpleNamespace(evidence_id="E1")
    t=SimpleNamespace(evidence_id="E2")
    base={"final_mask":[1],"cascade_contract_valid":True,
        "answer":{"answer_points":[{"evidence_ids":["E1"]}]}}
    invalid={"final_mask":[0],"cascade_contract_valid":False,
        "first_audit":{"issues":["mask_length_mismatch"]}}
    row=compile_candidate_row(SimpleNamespace(query_id="Q1"),SimpleNamespace(ranked=(r,)),
        ((r,0.9),(t,0.8)),base,{"E2":invalid})
    assert "E2" not in row["final_support_by_evidence_id"]
    assert row["auxiliary_contract_failure_evidence_ids"]==["E2"]
    assert row["support_supervision"]["not_assessed"]==1
    exported=export_candidate_decisions(row,candidate_count_policy="at_most")
    assert exported.decisions[1].support.value=="not_assessed"

def test_invalid_base_verifier_still_fails_closed():
    r=SimpleNamespace(evidence_id="E1")
    base={"final_mask":[0],"cascade_contract_valid":False,"answer":{"answer_points":[]}}
    with pytest.raises(ContractError,match="base RP2"):
        compile_candidate_row(SimpleNamespace(query_id="Q1"),SimpleNamespace(ranked=(r,)),
            ((r,0.9),),base,{})

def test_feature_stage_declares_training_and_development_boundaries():
    root = Path(__file__).resolve().parents[2]
    runner = (root / "scripts" / "run_rp3_experiments.sh").read_text(
        encoding="utf-8"
    )
    assert "build_rp3_features.py --purpose training" in runner
    assert "build_rp3_features.py --purpose development" in runner

def test_shared_experiment_decoder_uses_the_runtime_decoder():
    np = pytest.importorskip("numpy")
    from src.research_point_3.experiment_io import decode_row

    trace = SimpleNamespace(
        candidate_evidence_ids=("E1",),
        availability_mask=(True,),
        selection_budget=1,
    )
    records = {"E1": SimpleNamespace(role=DiagnosticRole.SYMPTOM)}
    outputs = (
        np.asarray([[1.0]], dtype=np.float32),
        np.asarray([[8.0]], dtype=np.float32),
        np.asarray([[[0.0, 1.0, 0.0, 0.0]] * 4], dtype=np.float32),
        np.asarray([[[1.0, 0.0, 0.0, 0.0]] * 4], dtype=np.float32),
        np.asarray([[0.0, 1.0, 0.0]], dtype=np.float32),
    )
    decoded = decode_row(outputs, trace, records)
    assert decoded.route_action.value == "fallback"
    assert decoded.direct_support_evidence_ids == ("E1",)

def test_calibration_search_distinguishes_coverage_and_risk_failures():
    from scripts.calibrate_rp3_thresholds import select_operating_point

    low_coverage = [{"support": .5, "confidence": .5, "answered": 2, "risk": 0.0}]
    best, blocked = select_operating_point(
        low_coverage, maximum_teacher_disagreement=.1, minimum_answers=5
    )
    assert best is None
    assert blocked["reason"] == "insufficient_answer_coverage"

    high_risk = [{"support": .5, "confidence": .5, "answered": 8, "risk": .25}]
    best, blocked = select_operating_point(
        high_risk, maximum_teacher_disagreement=.1, minimum_answers=5
    )
    assert best is None
    assert blocked["reason"] == "teacher_disagreement_above_limit"

    feasible = [{"support": .7, "confidence": .8, "answered": 6, "risk": 0.0}]
    best, blocked = select_operating_point(
        feasible, maximum_teacher_disagreement=.1, minimum_answers=5
    )
    assert best == feasible[0]
    assert blocked is None
