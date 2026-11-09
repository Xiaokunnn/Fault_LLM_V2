"""Checks of source integrity and failure-closed behavior for the experimental probe."""
import copy
import hashlib
import pytest

from research_point_1_graph_evidence.stage03_schema_validation.repair_probe_v2 import (
    locate, probe, relation_warnings, source_witness,
)


def example(text='Wear may cause noise. Inspect the bearing.'):
    page = {'doc_id': 'MP001', 'pdf_page_number': 1, 'document_sha256': 'frozen-doc',
            'page_text': text, 'page_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'page_width': 500, 'page_height': 800, 'tables': []}
    r = {k: page[k] for k in ['doc_id', 'pdf_page_number', 'document_sha256', 'page_text_sha256']}
    r.update(triple_id='synthetic', head_surface='Wear', tail_surface='noise',
             relation='causes', head_type='Cause', tail_type='Symptom', relation_type_valid=True,
             evidence_text='Wear may cause noise.', evidence_level='E3', evidence_validation={}, decision='rejected')
    return r, page


def test_context_proposal_is_not_semantic_acceptance_or_e3_promotion():
    r, p = example()
    before = copy.deepcopy((r, p))
    result = probe(r, p)
    assert result['technical_readiness'] == {'A': False, 'B': True, 'C': False, 'D': True}
    w = result['witness']
    assert p['page_text'][w['start']:w['end']] == w['source_text']
    assert not w['automatically_qualified'] and not w['semantic_support_verified']
    assert w['original_evidence_level'] == 'E3' and result['new_qualification_decision'] is None
    assert (r, p) == before


def test_page_and_document_mismatches_fail_closed():
    r, p = example()
    p['page_text'] += ' changed'
    with pytest.raises(ValueError):
        probe(r, p)
    r, p = example()
    r['document_sha256'] = 'different'
    with pytest.raises(ValueError):
        probe(r, p)


@pytest.mark.parametrize('surface', ['wear', 'Wear ... noise', 'Wear…noise', ''])
def test_locator_never_case_folds_or_bridges_ellipsis(surface):
    assert locate('Wear may cause noise.', surface) is None


def test_whitespace_matching_recovers_original_source():
    text = '检查轴承\n  温度'
    span = locate(text, '检查轴承 温度')
    assert span and text[span[0]:span[1]] == text


def test_far_cooccurrence_does_not_make_witness():
    r, p = example('Wear.' + 'x' * 1400 + 'noise.')
    r['evidence_text'] = 'Wear.'
    assert not source_witness(r, p)['repair_proposed']


def cell(name, text, row='r1', top=10):
    return {'cell_id': name, 'table_id': 't1', 'row_id': row, 'text': text,
            'bbox': {'x0': 10 if name == 'h' else 110, 'top': top,
                     'x1': 100 if name == 'h' else 210, 'bottom': top + 10}}


def test_native_table_witness_preserves_cells_and_requires_unique_row():
    r, p = example()
    h, t = cell('h', 'Wear'), cell('t', 'noise')
    p['tables'] = [{'table_id': 't1', 'rows': [{'row_id': 'r1', 'cells': [h, t]}]}]
    w = source_witness(r, p)
    assert w['repair_proposed'] and w['units'] == [h, t]
    assert not w['semantic_support_verified'] and not w['human_visual_reviewed']
    p['tables'][0]['rows'].append({'row_id': 'r2', 'cells': [cell('h', 'Wear', 'r2'), cell('t', 'noise', 'r2')]})
    assert source_witness(r, p)['status'] == 'ambiguous_native_table_binding'


def test_cross_row_and_invalid_boxes_cannot_be_repaired_as_prose():
    r, p = example()
    p['tables'] = [{'table_id': 't1', 'rows': [{'row_id': 'r1', 'cells': [cell('h', 'Wear'), cell('t', 'noise', 'r2')]}]}]
    assert not source_witness(r, p)['repair_proposed']
    p['tables'][0]['rows'][0]['cells'][1] = cell('t', 'noise', top=900)
    assert not source_witness(r, p)['repair_proposed']


def test_relation_warning_flags_target_and_negative_requirement():
    r, _ = example()
    r.update(relation='maintained_by', tail_surface='requires no maintenance')
    assert 'negative_maintenance_requirement' in relation_warnings(r)
    r.update(relation='prevented_by', head_surface='blockage',
             tail_surface='Never use steam to clear blockage', evidence_text='Never use steam to clear blockage')
    assert 'warning_without_explicit_prevention_link' in relation_warnings(r)


def test_condition_warning_does_not_claim_semantic_falsity():
    r, p = example('If contaminated, inspect the bearing.')
    r.update(head_surface='bearing', relation='inspected_by', tail_surface='inspect', evidence_text=p['page_text'])
    result = probe(r, p)
    assert result['relation_warnings'] == ['condition_requires_explicit_representation']
    assert not result['technical_readiness']['D'] and result['new_qualification_decision'] is None
