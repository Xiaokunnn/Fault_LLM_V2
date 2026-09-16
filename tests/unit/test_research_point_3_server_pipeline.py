"""CPU-only checks for newly executable RP3 preparation boundaries."""
import sys
from dataclasses import replace
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
