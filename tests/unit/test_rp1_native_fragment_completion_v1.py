import copy
from unittest.mock import patch

import pytest

from research_point_1_graph_evidence.stage02_triple_extraction.contextual_extraction import units_of
from research_point_1_graph_evidence.stage02_triple_extraction.native_fragment_completion_v1 import complete_fragments,display,digest
from research_point_1_graph_evidence.stage03_schema_validation.native_local_reconstruction_v1 import make_pool,local_select


def cell(i,text,col,y=20,width=90):
    return dict(cell_id=i,text=text,column_index=col,bbox=dict(x0=col*100,x1=col*100+width,top=y,bottom=y+10))


def page(text='',tables=()):
    return dict(doc_id='MP005',pdf_page_number=12,page_text=text,page_text_sha256='test',document_sha256='doc',page_width=600,tables=list(tables),text_blocks=[dict(block_id='b',text=text,bbox=dict(x0=10,x1=550,top=10,bottom=20))] if text else [],applicability_scope='test pump')


def assert_native_roundtrips(cat,p):
    native=units_of([p])
    for obj in [*cat['fragments'],*cat['units']]:
        for w in obj['source_spans']:
            assert native[w['unit_id']]['text'][w['start']:w['end']]==w['text']
            assert w['bbox']==native[w['unit_id']]['bbox']


def test_open_compound_completion_dehyphenates_without_inventing_offsets():
    p=page('Severe torsional vibra-\ntion damages the intermediate drive shaft.');before=copy.deepcopy(p)
    with patch('builtins.open',side_effect=AssertionError('Runtime IO')):cat=complete_fragments(p)
    assert any(f['display_text']=='Severe torsional vibration' for f in cat['fragments'])
    assert any('intermediate drive shaft' in f['display_text'] for f in cat['fragments'])
    assert_native_roundtrips(cat,p);assert p==before


def test_overprint_normalization_preserves_raw_header():
    p=page('SSShhhaaafffttt ssseeeaaalll')
    assert display(p['page_text'])=='Shaft seal'
    assert p['page_text']=='SSShhhaaafffttt ssseeeaaalll'


def test_monitoring_method_is_separate_native_cell_not_whole_page():
    headers=[cell('h0','Monitoring Techniques',0,0),cell('h1','Conditions Monitored',1,0),cell('h2','Disadvantages',2,0)]
    data=[cell('m','Envelope\nSpectrum Analysis',0),cell('f','seal failure, corrosion',1),cell('q','Not intended for reciprocating machines',2)]
    p=page(tables=[dict(table_id='t',rows=[dict(row_id='h',cells=headers),dict(row_id='r',cells=data)])]);cat=complete_fragments(p)
    methods=[f for f in cat['fragments'] if f['kind']=='method']
    assert len(methods)==1 and methods[0]['display_text']=='Envelope Spectrum Analysis'
    assert methods[0]['source_spans'][0]['unit_id']=='m'
    assert any(q['role']=='source_limitation' for q in methods[0]['qualifiers'])
    assert_native_roundtrips(cat,p)


def test_matrix_full_actions_keep_correct_component_and_row_condition():
    headers=[cell('h0','',0,0),cell('h1','Valve seals',1,0),cell('h2','Drive bearings',2,0)]
    data=[cell('q','Maintenance after leakage',0),cell('a','Replace the seal when worn.',1),cell('b','Inspect the bearing annually.',2)]
    p=page(tables=[dict(table_id='t',rows=[dict(row_id='h',cells=headers),dict(row_id='r',cells=data)])]);cat=complete_fragments(p)
    action=next(f for f in cat['fragments'] if f['kind']=='action' and 'Replace' in f['display_text'])
    assert [q['text'] for q in action['qualifiers'] if q['role']=='component_header']==['Valve seals']
    assert [q['text'] for q in action['qualifiers'] if q['role']=='row_condition']==['Maintenance after leakage']
    assert_native_roundtrips(cat,p)


def test_merged_geometry_cannot_be_silently_split():
    headers=[cell('h0','',0,0),cell('h1','Valve seals',1,0),cell('h2','Drive bearings',2,0)]
    p=page(tables=[dict(table_id='t',rows=[dict(row_id='h',cells=headers),dict(row_id='r',cells=[cell('q','Planned maintenance',0),cell('x','Replace seal Inspect bearing',1,width=190)])])]);cat=complete_fragments(p)
    assert cat['issues'][0]['kind']=='merged_columns_unresolved'
    assert not any(u['kind']=='table_action' for u in cat['units'])
    assert_native_roundtrips(cat,p)


def test_pool_is_arm_independent_and_local_selection_cannot_mutate_it():
    p=page('Check the intermediate shaft.');cat=complete_fragments(p)
    registry={'inspected_by':dict(domain=['Component'],range=['InspectionAction'])}
    pool=make_pool([],cat,p,registry);before=copy.deepcopy(pool);h=digest(pool)
    assert pool
    for c in pool:local_select(c,dict(included=False,screen_flags=['unbound_quote'],barriers=[]),registry)
    assert pool==before and digest(pool)==h


def test_aliasing_and_unknown_documents_do_not_bypass_split():
    p=page('Check the drive shaft.')
    for doc in ['MP008','MP009','MP014']:
        p['doc_id']=doc
        with pytest.raises(ValueError,match='not_build'):complete_fragments(p)


def test_no_record_id_answer_rule_and_source_changes_affect_pool():
    a=complete_fragments(page('Replace the inlet valve.'))
    b=complete_fragments(page('Replace the outlet valve.'))
    assert a['pool_sha256']!=b['pool_sha256']
    assert any('inlet valve' in f['display_text'] for f in a['fragments'])
    assert not any('inlet valve' in f['display_text'] for f in b['fragments'])


def test_duplicate_cached_outputs_stay_in_all_output_denominator():
    p=page('The pump runs.');cat=complete_fragments(p)
    payload=dict(head_surface='pump',head_type='Equipment',relation='operates_under',tail_surface='runs',tail_type='OperatingCondition',conditions=[],modality='asserted',polarity='positive',scope='primary',applicability='',evidence_text=p['page_text'],evidence_unit_ids=[])
    pool=make_pool([dict(candidate_id='first',payload=payload),dict(candidate_id='second',payload=copy.deepcopy(payload))],cat,p,{})
    assert len(pool)==2 and pool[0]['id']!=pool[1]['id']


def test_physical_parts_list_is_not_a_maintenance_matrix():
    p=page(tables=[dict(table_id='t',rows=[dict(row_id='h',cells=[cell('h0','',0,0),cell('h1','Valve seals',1,0),cell('h2','Drive bearings',2,0)]),dict(row_id='r',cells=[cell('q','Item 123',0),cell('a','Lock nut',1),cell('b','Bent pipe',2)])])])
    cat=complete_fragments(p)
    assert not any(u['kind']=='table_action' for u in cat['units'])


def test_check_valve_noun_does_not_create_inspection_relation():
    p=page('The pump has a check valve in the feed pipe.');cat=complete_fragments(p)
    registry={'inspected_by':dict(domain=['Component'],range=['InspectionAction'])}
    assert make_pool([],cat,p,registry)==[]
