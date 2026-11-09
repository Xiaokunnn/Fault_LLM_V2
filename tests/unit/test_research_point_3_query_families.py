"""Structural grouping and label-boundary tests for the new coverage audit."""
from copy import deepcopy

import pytest

from scripts.audit_rp3_query_families import (
    components, concentration, direction_anchor, normalize, propose_split, verify_location,
)


def fixture_rows():
    entities = {key: {'entity_id': key, 'canonical_label_zh': key, 'source_surfaces': [key],
        'entity_type': 'FaultMode' if key.startswith('F') else 'Component'}
        for key in ('F1', 'F2', 'F3', 'a', 'b', 'c')}
    claims = {f'c{i}': {'claim_id': f'c{i}', 'head_entity_id': f'F{i}',
        'tail_entity_id': tail, 'relation': 'causes'} for i, tail in enumerate(('a', 'b', 'c'), 1)}
    rows = [{'evidence_id': f'e{i}', 'claim_id': f'c{i}', 'role': 'cause_or_mechanism',
        'metadata': {'card_selectable': True},
        'provenance': {'doc_id': f'D{i}', 'physical_pdf_page': 1, 'source_family_id': f'S{i}'}}
        for i in range(1, 4)]
    return rows, claims, entities


def test_no_false_link_from_same_page_number_in_different_documents():
    rows, claims, entities = fixture_rows()
    assert len(components(rows, claims, entities)[0]) == 3


def test_transitive_page_and_entity_bridges_are_retained():
    rows, claims, entities = fixture_rows()
    rows[1]['provenance']['doc_id'] = 'D1'
    claims['c3']['tail_entity_id'] = 'b'
    groups, _ = components(rows, claims, entities)
    assert len(groups) == 1
    assert groups[0]['evidence_ids'] == ['e1', 'e2', 'e3']


def test_alias_matching_is_sensitivity_rule_not_record_rewrite():
    rows, claims, entities = fixture_rows()
    entities['a']['source_surfaces'] = ['ＰＵＭＰ  SEAL']
    entities['b']['source_surfaces'] = ['pump seal']
    before = deepcopy(entities)
    assert len(components(rows, claims, entities)[0]) == 3
    assert len(components(rows, claims, entities, aliases=True)[0]) == 2
    assert entities == before
    assert normalize('ＰＵＭＰ  SEAL') == 'pump seal'


def test_source_family_closure_merges_documents():
    rows, claims, entities = fixture_rows()
    rows[1]['provenance']['source_family_id'] = 'S1'
    assert len(components(rows, claims, entities, source_family=True)[0]) == 2


def test_components_and_ids_are_input_order_invariant():
    rows, claims, entities = fixture_rows()
    assert components(rows, claims, entities) == components(list(reversed(rows)), claims, entities)


def test_cause_question_anchor_uses_effect_not_cause():
    rows, claims, _ = fixture_rows()
    assert direction_anchor(rows[0], claims['c1'], 'a')
    assert not direction_anchor(rows[0], claims['c1'], 'F1')


@pytest.mark.parametrize('relation,side', [('indicates', 'tail_entity_id'), ('manifests_as', 'head_entity_id')])
def test_symptom_relation_direction(relation, side):
    rows, claims, _ = fixture_rows()
    rows[0]['role'] = 'symptom'
    claims['c1']['relation'] = relation
    assert direction_anchor(rows[0], claims['c1'], claims['c1'][side])
    rows[0]['metadata']['card_selectable'] = False
    assert not direction_anchor(rows[0], claims['c1'], claims['c1'][side])


def test_split_is_group_disjoint_deterministic_and_largest_in_train():
    groups = [{'group_id': str(i), 'scope_entity_ids': list(range(i + 1))} for i in range(7)]
    result = propose_split(groups, 'seed', 2)
    assert result == propose_split(list(reversed(groups)), 'seed', 2)
    assert result['6'] == 'train'
    assert sorted(result.values()).count('validation') == 2
    assert sorted(result.values()).count('build_confirmation') == 2
    assert len(result) == 7
    with pytest.raises(ValueError, match='too few'):
        propose_split(groups[:4], 'seed', 2)


def test_concentration_is_descriptive_weight_concentration():
    assert concentration([{'scope_entity_ids': [1, 2]}, {'scope_entity_ids': [3, 4]}]) == 2
    assert concentration([{'scope_entity_ids': [1, 2, 3]}, {'scope_entity_ids': [4]}]) == 1.6


def test_E2_requires_real_cell_identity_and_preserves_representation_differences():
    unit = {'text': 'a\n b', 'table_id': 't', 'row_id': 'r', 'row_group_id': 'r',
        'column_name': 'cause', 'bbox': [1, 2, 3, 4]}
    cell = {**unit, 'text': 'a b', 'cell_id': 'c', 'column_name': '',
        'bbox': dict(zip(('x0', 'top', 'x1', 'bottom'), (1, 2, 3, 4)))}
    row = {'evidence_text': 'a\n b', 'metadata': {'evidence_level': 'E2'},
        'provenance': {'doc_id': 'D1', 'physical_pdf_page': 1, 'evidence_char_start': None, 'evidence_char_end': None}}
    source = {'doc_id': 'D1', 'pdf_page_number': 1, 'evidence_level': 'E2', 'evidence_text': 'a\n b',
        'evidence_unit_ids': ['c'], 'evidence_validation': {'units': [unit]}}
    page = {'tables': [{'rows': [{'cells': [cell]}]}]}
    result = verify_location(row, source, page)
    assert not result['contiguous_span_verified'] and result['existing_table_bbox_verified']
    assert len(result['cell_representation_differences']) == 2
    cell['text'] = 'a WRONG'
    with pytest.raises(ValueError, match='nonwhitespace'):
        verify_location(row, source, page)
