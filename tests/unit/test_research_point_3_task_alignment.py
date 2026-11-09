"""Semantic edge cases for the read-only supervision alignment audit."""
import pytest

from scripts.audit_rp3_task_alignment import (
    alias_summary, coverage, label_from_run, origin_for, prompt_summary,
)


def test_invalid_auxiliary_response_is_missing_not_negative():
    run = {'cascade_contract_valid': False, 'final_mask': [0],
           'expanded_model_answer': {'evidence_assessments': [{'evidence_id': 'e'}]}}
    assert label_from_run(run, 'e') is None
    run['cascade_contract_valid'] = True
    assert label_from_run(run, 'e') == 0


@pytest.mark.parametrize('eid,prefix,base,derived,expected', [
    ('a', ['a'], ['a'], False, 'base_k3'),
    ('b', ['a'], ['a'], False, 'base_singleton_tail'),
    ('b', ['b'], ['a'], True, 'fresh_intervention_k3'),
    # A candidate leaving K3 still inherits its original BATCH label.
    ('a', ['b'], ['a'], True, 'inherited_base_k3'),
    ('c', ['b'], ['a'], True, 'inherited_base_singleton_tail'),
])
def test_label_origin_tracks_assessment_not_current_position(eid, prefix, base, derived, expected):
    assert origin_for(eid, prefix, base, derived) == expected


def test_alias_bound_ignores_unavailable_and_unassessed_slots():
    rows = [{'pair': 'q/e', 'eligible': ok, 'label': label} for ok,label in
            [(True, 1), (True, 0), (True, 1), (False, 0), (True, None)]]
    result = alias_summary(rows, 'pair')
    assert result['occurrences'] == 3
    assert result['unique_inputs'] == result['conflicting_inputs'] == 1
    assert result['minimum_empirical_errors'] == 1


def test_prompt_consistency_exposes_identical_prompt_disagreement():
    calls = [{'stage': stage, 'user_prompt_sha256': prompt, 'response': answer}
             for stage,prompt,answer in [
                 ('precision_mask', 'p', {'direct': [1]}),
                 ('precision_mask', 'p', {'direct': [0]}),
                 ('precision_mask', 'q', {'direct': [0]}),
                 ('recall_review', 'r', {'direct': 0}),
                 ('recall_review', 'r', {'direct': 0})]]
    result = prompt_summary(calls)
    assert result['precision_mask']['different_response_groups'] == 1
    assert result['recall_review']['different_response_groups'] == 0
    assert result['recall_review']['repeated_prompt_groups'] == 1


def test_derived_rows_do_not_add_query_families_and_shared_memory_is_disclosed():
    def trace(split, fault, perturbation):
        return {'split': split, 'perturbation_id': perturbation,
                'query': {'scenario_id': 'fault:' + fault, 'query_id': fault + '-SYM',
                          'fault_name_zh': fault, 'question_zh': fault + '有哪些症状？',
                          'requested_role': 'symptom', 'operating_context': []},
                'candidate_evidence_ids': ['e'], 'evidence_decisions': [{'evidence_id': 'e', 'selected': True}]}
    memory = {'e': {'claim_id': 'c', 'provenance': {'doc_id': 'MP001', 'source_family_id': 'f'}}}
    report = coverage([trace('train', '汽蚀', 'original'), trace('train', '汽蚀', 'remove'),
                       trace('validation', '堵塞', 'original')], memory)
    assert report['train']['all_traces'] == 2
    assert report['train']['original_queries'] == report['train']['scenario_count'] == 1
    assert report['scenario_overlap'] == []
    assert report['template_overlap'] == ['{fault_scope}有哪些症状？']
    assert report['overlap']['candidate_documents']['intersection_count'] == 1
