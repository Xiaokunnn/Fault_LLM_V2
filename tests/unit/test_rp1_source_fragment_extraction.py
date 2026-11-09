import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from rp1_offline_contract_v3 import REGISTRY
from research_point_1_graph_evidence.stage02_triple_extraction.source_fragment_extraction import (
    prepare_catalog,model_input,compile_records,source_endpoint_dictionary,real_table)


def page(texts):
    return dict(doc_id='MP005',pdf_page_number=108,page_width=600,tables=[],
        text_blocks=[dict(block_id=f'b{i}',text=t,bbox=dict(x0=10,x1=280,top=20*i,bottom=20*i+12)) for i,t in enumerate(texts)],
        source_url='https://example.org',document_sha256='d',page_text_sha256='p')


def choose(cat,prefix,contains):
    values=[c for cid,c in cat['candidates'].items() if cid.startswith(prefix) and contains in c['text']]
    assert values,contains
    return min(values,key=lambda c:len(c['text']))


def record(cat,action,entity='carbon ring'):
    a=choose(cat,'A',action);e=choose(cat,'E',entity)
    scope=[s for s in a['scope_ids'] if cat['candidates'][s].get('scope_kind') in ['phase','branch','applicability']]
    return dict(catalog_sha256=cat['catalog_sha256'],condition_names={cid:'源文条件' for cid in a['local_condition_ids']+scope},records=[dict(head=[e['id'],'Component','碳环'],relation='maintained_by',
        tail=[a['id'],'MaintenanceAction','安装碳环'],local=a['local_condition_ids'],shared=scope,
        evidence=list(dict.fromkeys(e['parents']+a['parents'])),mode='required',polarity='positive',unresolved=None)])


def test_complete_multiline_source_action_and_parent_roundtrip():
    p=page(['ASSEMBLING PUMP SET','If the carbon ring is loose, install the carbon ring','with its lapped face toward the seat.'])
    before=copy.deepcopy(p);c=prepare_catalog(p);r=record(c,'install the carbon ring')
    out=compile_records(r,c,REGISTRY)[0]
    assert out['automatic_pass'] and 'lapped face toward the seat' in out['tail']['surface']
    assert len(out['tail']['source_spans'])==2 and p==before
    native={b['block_id']:b for b in p['text_blocks']}
    for w in out['source_witnesses']+out['tail']['source_spans']:
        assert native[w['unit_id']]['text'][w['start']:w['end']]==w['text']
    assert c['coverage']['source_character_coverage']==1


def test_different_if_conditions_never_share_an_action_owner():
    p=page(['If the bellows are tight, use a fitting tool.','If the carbon ring is loose, install the carbon ring.'])
    c=prepare_catalog(p);r=record(c,'install the carbon ring');wrong=choose(c,'C','bellows')
    r['records'][0]['local'].append(wrong['id'])
    assert 'local_condition_wrong_action_or_unresolved' in compile_records(r,c,REGISTRY)[0]['flags']


def test_omitted_local_if_condition_is_detected():
    c=prepare_catalog(page(['If the carbon ring is loose, install the carbon ring.']))
    r=record(c,'install');r['records'][0]['local']=[]
    assert 'required_local_condition_omitted' in compile_records(r,c,REGISTRY)[0]['flags']


def test_scope_header_does_not_need_character_overlap_with_action():
    c=prepare_catalog(page(['ASSEMBLING PUMP SET','Ø215/265','1. Install the carbon ring.','2. Check the carbon ring.']))
    r=record(c,'Install');out=compile_records(r,c,REGISTRY)[0]
    assert out['automatic_pass']
    assert any(x['text']=='Ø215/265' for x in out['conditions'])
    second=choose(c,'A','Check');assert any(c['candidates'][sid]['text']=='Ø215/265' for sid in second['scope_ids'])
    r['records'][0]['shared']=[]
    assert 'required_shared_condition_omitted' in compile_records(r,c,REGISTRY)[0]['flags']


def test_step_numbers_and_abbreviations_do_not_split_into_fake_sentences():
    c=prepare_catalog(page(['1. Install the carbon ring in abt. 15 minutes.']))
    ps=[p['text'] for p in c['paragraphs'].values()]
    assert ps==['1. Install the carbon ring in abt. 15 minutes.']


def test_cleaning_followup_is_a_required_condition_of_same_step():
    p=page(['1. Clean the carbon ring. Make sure it','is free of dirt and scratches.','2. Install the carbon ring.'])
    c=prepare_catalog(p);clean=choose(c,'A','Clean');install=choose(c,'A','Install')
    assert clean['local_condition_ids'] and not install['local_condition_ids']
    cond=c['candidates'][clean['local_condition_ids'][0]]
    assert 'free of dirt and scratches' in cond['text'] and cond['eligible_ids']==[clean['id']]


def test_display_dehyphenation_does_not_change_native_evidence():
    p=page(['Check the pow-','er supply.']);c=prepare_catalog(p)
    a=choose(c,'A','pow-');assert 'power' in a['display_text']
    assert a['source_spans'][0]['text']=='Check the pow-'
    assert a['source_spans'][1]['text']=='er supply.'


def test_geometry_never_joins_two_columns():
    p=page(['If the carbon ring is loose, install it.']*3+['Check pressure and inspect the pump.']*3)
    for i,b in enumerate(p['text_blocks']):
        b['bbox']=dict(x0=10 if i<3 else 330,x1=270 if i<3 else 570,top=20*(i%3),bottom=20*(i%3)+12)
    c=prepare_catalog(p);assert c['geometry'][0]['two_columns']
    for x in c['paragraphs'].values():
        assert len({w['bbox']['x0'] for w in x['source_spans']})==1


def test_unmatched_source_units_are_retained_in_coverage_and_fallback():
    p=page(['Install the carbon ring.'])
    p['tables']=[dict(table_id='t',bbox=dict(x0=300,x1=500,top=30,bottom=60),rows=[dict(row_id='r',cells=[dict(cell_id='extra',text='Special model X99 restriction',bbox=dict(x0=300,x1=500,top=30,bottom=60))])])]
    c=prepare_catalog(p)
    assert any('X99' in x['text'] for x in c['paragraphs'].values())
    assert c['coverage']['source_character_coverage']==1


def test_duplicate_native_representation_has_proof_but_distant_words_not_duplicate():
    p=page(['Install the carbon ring.'])
    p['tables']=[dict(table_id='t',bbox=dict(x0=0,x1=290,top=0,bottom=12),rows=[dict(row_id='r',cells=[dict(cell_id='dup',text='carbon ring',bbox=dict(x0=50,x1=100,top=0,bottom=12)),dict(cell_id='far',text='carbon ring',bbox=dict(x0=50,x1=100,top=600,bottom=612))])])]
    c=prepare_catalog(p)
    assert 'dup' in c['coverage']['duplicate_proofs']
    assert 'far' not in c['coverage']['duplicate_proofs']


@pytest.mark.parametrize('doc',['MP008','MP009','MP014'])
def test_development_external_or_excluded_documents_cannot_enter_build_trial(doc):
    p=page(['Install the carbon ring.']);p['doc_id']=doc
    with pytest.raises(ValueError):prepare_catalog(p)


def test_malformed_and_unknown_choices_are_not_dropped():
    c=prepare_catalog(page(['Install the carbon ring.']));r=record(c,'Install')
    r['records'] += [None,{'head':['E999','Component','碳环'],'tail':{},'mode':[],'local':[{}]}]
    out=compile_records(r,c,REGISTRY)
    assert len(out)==3 and not out[1]['automatic_pass'] and not out[2]['automatic_pass']


def test_whole_statement_cannot_be_declared_a_physical_component():
    c=prepare_catalog(page(['Install the carbon ring.']));r=record(c,'Install')
    stmt=next(x for x in c['candidates'].values() if x.get('kind')=='statement_candidate')
    r['records'][0]['head'][0]=stmt['id']
    assert 'head_statement_as_physical_entity' in compile_records(r,c,REGISTRY)[0]['flags']


def test_negative_exception_must_be_preserved_in_canonical_action():
    c=prepare_catalog(page(['Never touch the carbon ring with anything except clean hands.']))
    r=record(c,'Never');r['records'][0]['polarity']='negative'
    r['records'][0]['tail'][2]='仅用干净手触摸碳环'
    assert 'prohibition_not_preserved' in compile_records(r,c,REGISTRY)[0]['flags']
    r['records'][0]['tail'][2]='不得用干净手以外的物品触摸碳环'
    assert compile_records(r,c,REGISTRY)[0]['automatic_pass']


def test_not_recommended_must_not_become_prohibition():
    c=prepare_catalog(page(['Coat the carbon ring with P-80. Grease is not recommended.']))
    r=record(c,'Grease');r['records'][0]['polarity']='negative'
    assert 'recommendation_strength_or_polarity_changed' in compile_records(r,c,REGISTRY)[0]['flags']
    r['records'][0]['mode']='recommended'
    assert 'recommendation_strength_or_polarity_changed' not in compile_records(r,c,REGISTRY)[0]['flags']


def test_dictionary_uses_all_cached_surfaces_without_truth_labels_and_no_articles():
    cache={'records':[dict(head_surface='the',head_type='Component',tail_surface='carbon ring',tail_type='Component'),dict(head_surface='push it over',head_type='Component')]}
    assert source_endpoint_dictionary([cache])==['carbon ring']


def test_model_input_has_short_choices_and_no_source_coordinates():
    c=prepare_catalog(page(['Install the carbon ring.']));m=model_input(c)
    assert m['choice_format'][0]=='id' and isinstance(m['choices'][0],list)
    assert all('source_spans' not in x for x in m['choice_format'])
    assert c==prepare_catalog(page(['Install the carbon ring.']))


def test_holding_clip_variant_and_after_installation_belong_only_to_clip_action():
    p=page(['3. Some seals are equipped with holding clips which compress the springs.',
        'Remove holding clips after the seal is installed on shaft.','4. Install the carbon ring.'])
    c=prepare_catalog(p);a=choose(c,'A','Remove');other=choose(c,'A','Install the carbon')
    texts=[c['candidates'][x]['text'] for x in a['local_condition_ids']]
    assert any('Some seals' in text for text in texts)
    assert any('after the seal is installed' in text for text in texts)
    assert not other['local_condition_ids']


def test_source_table_rows_are_preserved_and_cross_row_pairing_is_rejected():
    p=page([])
    p['tables']=[dict(table_id='t',bbox=dict(x0=0,x1=600,top=0,bottom=100),column_roles=['fault','cause','remedy'],
        rows=[dict(row_id=f'r{i}',row_index=i,cells=[dict(cell_id=f'c{i}',text=text,bbox=dict(x0=0,x1=200,top=20*i,bottom=20*i+12))])
              for i,text in enumerate(['Leakage','Replace the carbon ring.'])])]
    c=prepare_catalog(p);r=record(c,'Replace');e=choose(c,'E','Leakage')
    r['records'][0].update(head=[e['id'],'FaultMode','泄漏'],relation='mitigated_by')
    r['records'][0]['evidence']+=e['parents']
    assert 'cross_table_rows' in compile_records(r,c,REGISTRY)[0]['flags']
    assert len(c['branches'])==2 and c['coverage']['source_character_coverage']==1


def test_incorrect_lifting_warning_is_not_a_fault_table():
    table=dict(column_roles=[],rows=[dict(cells=[dict(text='FALLING LOAD HAZARD',column_index=0),
        dict(text='Incorrect lifting methods can cause failure. Use transport devices.',column_index=1)])])
    assert not real_table(table)


def test_numeric_section_after_a_logo_retains_section_scope():
    c=prepare_catalog(page(['FreFlow','7.8.3 Assembly of bearings','1. Install the carbon ring.']))
    a=choose(c,'A','Install')
    assert any(c['candidates'][sid]['text']=='7.8.3 Assembly of bearings' for sid in a['scope_ids'])


def test_unknown_component_name_does_not_require_a_cached_dictionary_entry():
    p=page(['The ceramic zorbulators must be installed carefully.','1. Rework the ceramic zorbulators.'])
    c=prepare_catalog(p,endpoint_dictionary=[])
    e=choose(c,'E','ceramic zorbulators')
    assert e['kind']=='nominal_candidate'
    assert choose(c,'A','Rework')['text']=='1. Rework the ceramic zorbulators.'
