import itertools
import pytest
from scripts.audit_rp3_scope_feasibility import oracle_frontier


def test_fixed_proposal_frontier_matches_exhaustive_zero_error_policies():
    rows = [{'teacher_selected_ids':t,'selected_ids':s,'proposal_contract_passed':valid,'scenario_id':'synthetic'}
            for t,s,valid in [(['A'],['A'],True), (['B'],[],True), (['C'],['wrong'],True),
                              (['D'],['D'],False), ([],['spurious'],True)]]
    frontier = oracle_frontier(rows)
    assert frontier['teacher_nonempty']==4 and frontier['correct_nonempty_local']==1
    assert frontier['minimum_full_teacher_calls_for_all_nonempty_exact']==3
    for point in frontier['frontier']:
        best=0
        for policy in itertools.product(('local','teacher','abstain'),repeat=len(rows)):
            if policy.count('teacher')>point['full_teacher_call_budget']:continue
            answers=0;invalid=False
            for row,action in zip(rows,policy):
                if action=='abstain':continue
                if action=='local':
                    prediction=row['selected_ids']
                    if prediction and (not row['proposal_contract_passed'] or set(prediction)!=set(row['teacher_selected_ids'])):invalid=True;break
                else:prediction=row['teacher_selected_ids']
                answers+=bool(prediction)
            if not invalid:best=max(best,answers)
        assert best==point['max_exact_nonempty_served']


def test_empty_targets_have_undefined_nonempty_coverage_and_no_fake_answers():
    result=oracle_frontier([{'teacher_selected_ids':[],'selected_ids':[],'proposal_contract_passed':True,'scenario_id':'s'}])
    assert result['correct_nonempty_local']==0 and result['frontier'][0]['max_nonempty_service_coverage'] is None
    with pytest.raises(ValueError):oracle_frontier([])
