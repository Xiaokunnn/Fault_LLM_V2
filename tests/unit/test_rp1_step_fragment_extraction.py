import copy
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from rp1_offline_contract_v3 import REGISTRY
from research_point_1_graph_evidence.stage02_triple_extraction.step_fragment_extraction import (
    prepare_local_catalog,local_model_input,compile_local_records)


def page(texts):
    return dict(doc_id='MP005',pdf_page_number=108,page_width=600,tables=[],
        text_blocks=[dict(block_id=f'b{i}',text=t,bbox=dict(x0=10,x1=280,top=20*i,bottom=20*i+12)) for i,t in enumerate(texts)])


def pick(c,phrase,kind='action'):
    for u in c['units'].values():
        values=[v for v in u['choices'].values() if phrase in v['text'] and v['kind']==kind]
        if values:return u,min(values,key=lambda v:len(v['text']))
    raise AssertionError(phrase)


def output(c,phrase):
    u,a=pick(c,phrase)
    e=next(x for x in u['choices'].values() if x['kind']=='entity' and 'carbon ring' in x['text'])
    return dict(scopes_zh={s:'源文装配阶段/型号' for s in u['shared_ids']},records=[dict(unit=u['id'],head_id=e['id'],head_type='Component',head_zh='碳环',relation='maintained_by',tail_id=a['id'],tail_type='MaintenanceAction',tail_zh='按源文要求安装碳环',conditions=[dict(id=s,zh='源文局部条件') for s in a['required']],mode='required',polarity='positive',unresolved=None)])


def test_local_ids_are_small_and_source_recovered_without_citations():
    p=page(['Install the carbon ring.','Clean the carbon ring.']);before=copy.deepcopy(p)
    c=prepare_local_catalog(p);r=output(c,'Install')
    assert compile_local_records(r,c,REGISTRY)[0]['automatic_pass']
    assert all('1' in u['choices'] for u in c['units'].values())
    assert p==before and 'evidence' not in r['records'][0]


def test_inline_model_continuation_does_not_leak_into_next_step():
    c=prepare_local_catalog(page(['ASSEMBLING PUMP SET','1. Place the carbon ring (only for','Ø330/415) in the housing.','2. Install the carbon ring.']))
    u,a=pick(c,'Place');v,b=pick(c,'Install')
    assert 'Ø330/415' in a['text']
    assert not any('Ø330' in c['headings'][s]['text'] for s in v['shared_ids'])
    assert c['coverage']['source_character_coverage']==1


def test_step_survives_floating_note_and_final_continuation():
    c=prepare_local_catalog(page(['1 Mount the bearing at drive side','Let the bearing cool down!','and push it firmly against the outer circlip.','2 Install the carbon ring.']))
    u,a=pick(c,'1 Mount')
    assert 'push it firmly against the outer circlip' in a['text']
    assert 'cool down' in a['text'] and '2 Install' not in a['text']


def test_if_required_only_in_own_sentence_and_detects_omission():
    c=prepare_local_catalog(page(['If the carbon ring is loose, install the carbon ring.','If the bellows is tight, use the tool.']))
    r=output(c,'install');assert compile_local_records(r,c,REGISTRY)[0]['automatic_pass']
    r['records'][0]['conditions']=[]
    assert 'required_local_condition_omitted' in compile_local_records(r,c,REGISTRY)[0]['flags']


def test_condition_can_be_cause_endpoint_without_self_condition():
    c=prepare_local_catalog(page(['If the carbon ring is damaged, inspect the carbon ring.']))
    u,a=pick(c,'inspect');cond=next(iter(u['conditions']))
    r=dict(scopes_zh={},records=[dict(unit=u['id'],head_id=cond,head_type='FaultMode',head_zh='碳环损坏',relation='diagnosed_by',tail_id=a['id'],tail_type='InspectionAction',tail_zh='检查碳环',conditions=[],mode='required',polarity='positive',unresolved=None)])
    assert compile_local_records(r,c,REGISTRY)[0]['automatic_pass']


def test_topic_is_not_a_shared_required_condition():
    c=prepare_local_catalog(page(['GENERAL NOTES','Install the carbon ring.']))
    assert not next(iter(c['units'].values()))['shared_ids']


def test_new_phase_drops_previous_model():
    c=prepare_local_catalog(page(['ASSEMBLY','FOR MODEL X99','1 Install the carbon ring.','DISASSEMBLY','1 Remove the carbon ring.']))
    u,a=pick(c,'Remove');assert all('X99' not in c['headings'][s]['text'] for s in u['shared_ids'])


def test_unknown_id_and_malformed_candidates_stay_in_population():
    c=prepare_local_catalog(page(['Install the carbon ring.']));r=output(c,'Install')
    r['records'] += [None,dict(unit='u999'),{**r['records'][0],'tail_id':'999'}]
    d=compile_local_records(r,c,REGISTRY);assert len(d)==4 and sum(x['automatic_pass'] for x in d)==1


def test_context_nouns_can_resolve_pronoun_but_not_context_only_relation():
    c=prepare_local_catalog(page(['The carbon ring is loose.','Install it carefully.']))
    u,a=pick(c,'Install');assert any(v['context'] and 'carbon ring' in v['text'] for v in u['choices'].values())
    r=output(c,'Install');assert compile_local_records(r,c,REGISTRY)[0]['automatic_pass']


def test_every_witness_roundtrips_to_raw_source_without_mutation():
    p=page(['ASSEMBLY','1 Install the carbon','ring in the housing.','2 Clean the ring.']);c=prepare_local_catalog(p)
    native={b['block_id']:b for b in p['text_blocks']}
    for u in c['units'].values():
        for obj in [u,*u['choices'].values()]:
            for w in obj['source_spans']:
                assert native[w['unit_id']]['text'][w['start']:w['end']]==w['text']
                assert native[w['unit_id']]['bbox']==w['bbox']


def test_model_does_not_receive_native_coordinates_or_old_global_ids():
    c=prepare_local_catalog(page(['Install the carbon ring.']));m=local_model_input(c)
    assert 'source_spans' not in str(m) and 'catalog_sha256' not in m
    assert m['units'][0]['choices'][0]['id']=='1'


@pytest.mark.parametrize('doc',['MP008','MP009','MP014'])
def test_split_boundary(doc):
    p=page(['Install the carbon ring.']);p['doc_id']=doc
    with pytest.raises(ValueError):prepare_local_catalog(p)


def test_columns_and_native_rows_do_not_cross():
    p=page(['Install the carbon ring carefully.']*3+['Check pressure and inspect the pump.']*3)
    for i,b in enumerate(p['text_blocks']):b['bbox']=dict(x0=10 if i<3 else 330,x1=270 if i<3 else 570,top=20*(i%3),bottom=20*(i%3)+12)
    c=prepare_local_catalog(p);assert c['geometry'][0]['two_columns']
    for u in c['units'].values():assert len({w['bbox']['x0'] for w in u['source_spans']})==1
