import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from rp1_offline_contract_v3 import REGISTRY
from research_point_1_graph_evidence.stage02_triple_extraction.native_evidence_selection import (
    catalog, compile_selection, digest, normalize_legacy, read_selection, replay_legacy)


def fixture():
    texts = ['M7N seal assembly', 'If bellows are tight, use a fitting tool.',
             'If carbon ring is loose, orient the carbon ring.', 'Wait about 15 min after silicone grease.']
    page = dict(doc_id='MP015', pdf_page_number=42, page_width=600,
        source_url='https://example.org', document_sha256='d', page_text_sha256='p', tables=[],
        text_blocks=[dict(block_id=f'n{i}', text=t,
            bbox=dict(x0=10, x1=240, top=20*i, bottom=20*i+12)) for i,t in enumerate(texts)])
    cat = catalog(page)
    def ref(i, start=0, end=None):
        return dict(unit_id=f'U{i:04d}', start=start, end=end if end is not None else len(cat[f'U{i:04d}']['tokens']))
    recs = []
    for i, head, action, cond, zh in [(1,(1,4),(5,9),(0,4),'皮囊过紧时'), (2,(1,4),(6,10),(0,5),'碳环松动时')]:
        recs.append(dict(record_id=f'R{i}', head=dict(canonical_zh='密封部件', type='Component', spans=[ref(i,*head)]),
            tail=dict(canonical_zh='装配密封部件', type='MaintenanceAction', spans=[ref(i,*action)]),
            relation='maintained_by', evidence=[ref(i)], polarity='positive', negation_evidence=[],
            modality='conditional', scope='primary', condition_ids=[f'C{i}'], conditions_complete=True,
            unresolved_reason=None, table_branch=None))
    response = dict(catalog_sha256=digest(cat), records=recs,
        conditions=[dict(condition_id=f'C{i}',kind='local_antecedent',canonical_zh=zh,
            evidence=[ref(i,*cond)], applies_to=[dict(record_id=f'R{i}',binding_evidence=[ref(i)])])
            for i, cond, zh in [(1,(0,4),'皮囊过紧时'),(2,(0,5),'碳环松动时')]])
    return page, response, ref


def test_exact_native_text_and_owned_conditions_not_context_union():
    p,r,_ = fixture(); before=copy.deepcopy((p,r)); out=compile_selection(r,p,[],REGISTRY)
    assert all(x['automatic_pass'] for x in out)
    assert [c['condition_id'] for c in out[0]['conditions']] == ['C1']
    assert [c['condition_id'] for c in out[1]['conditions']] == ['C2']
    for a in out:
        for w in a['source_witnesses'] + a['head']['source_spans'] + a['tail']['source_spans']:
            text=p['text_blocks'][int(w['unit_id'][1:])]['text']
            assert text[w['start']:w['end']] == w['text']
    assert (p,r)==before


@pytest.mark.parametrize('selection', [None, {}, dict(unit_id='missing',start=0,end=1),
    dict(unit_id='U0001',start=-1,end=2), dict(unit_id='U0001',start=1,end=1),
    dict(unit_id='U0001',start=0,end=999), dict(unit_id='U0001',start=True,end=2),
    dict(unit_id='U0001',start=0,end=1,quote='invented')])
def test_invalid_addresses_cannot_generate_provenance(selection):
    p,_,_=fixture()
    with pytest.raises(ValueError): read_selection(selection,catalog(p))


def test_pdf_hyphens_symbols_and_offsets_remain_original():
    p,_,_=fixture();p['text_blocks'][0]['text']='pow-\ner ≥ 140 °C'
    c=catalog(p);w=read_selection(dict(unit_id='U0000',start=0,end=len(c['U0000']['tokens'])),c)
    assert w['text']=='pow-\ner ≥ 140 °C'


def test_condition_ids_and_owner_list_must_agree_both_directions():
    p,r,_=fixture();r['records'][0]['condition_ids'].append('C2')
    flags=compile_selection(r,p,[],REGISTRY)[0]['flags']
    assert 'condition_ownership_disagrees' in flags
    assert 'unknown_or_unattached_condition' in flags
    r['records'][0]['condition_ids']=[]
    assert 'condition_ownership_disagrees' in compile_selection(r,p,[],REGISTRY)[0]['flags']


def test_warning_alone_cannot_prove_link_to_an_unrelated_relation():
    p,r,ref=fixture();r['conditions'][0]['kind']='prerequisite'
    r['conditions'][0]['applies_to'][0]['binding_evidence']=[ref(3)]
    assert 'condition_binding_outside_relation' in compile_selection(r,p,[],REGISTRY)[0]['flags']


def test_ambiguous_ownership_stays_unresolved():
    p,r,_=fixture();r['records'][0]['conditions_complete']=False
    assert 'condition_ownership_unresolved' in compile_selection(r,p,[],REGISTRY)[0]['flags']


def test_catalog_hash_and_malformed_records_fail_without_dropping_denominator():
    p,r,_=fixture();r['catalog_sha256']='bad';r['records'] += [None]
    out=compile_selection(r,p,[],REGISTRY)
    assert len(out)==3 and all(not a['automatic_pass'] for a in out)


def test_previous_page_only_relation_cannot_pass():
    p,r,_=fixture();prev=copy.deepcopy(p);prev['pdf_page_number']=41
    for b in prev['text_blocks']:b['block_id']='prev'+b['block_id']
    c=catalog(p,[prev]);r['catalog_sha256']=digest(c)
    r['records'][0]['evidence']=[dict(unit_id='U0005',start=0,end=10)]
    assert 'no_target_page_relation' in compile_selection(r,p,[prev],REGISTRY)[0]['flags']


def test_multiblock_endpoints_cannot_cross_gap_or_read_in_reverse():
    p,r,ref=fixture();r['records'][0]['tail']['spans']=[ref(1,5,9),ref(2,0,5)]
    r['records'][0]['evidence']=[ref(1),ref(2)]
    p['text_blocks'][2]['bbox'].update(top=300,bottom=312);r['catalog_sha256']=digest(catalog(p))
    assert 'tail_not_native_contiguous_path' in compile_selection(r,p,[],REGISTRY)[0]['flags']
    p['text_blocks'][2]['bbox'].update(top=40,bottom=52)
    r['records'][0]['tail']['spans'].reverse();r['catalog_sha256']=digest(catalog(p))
    assert 'tail_not_native_contiguous_path' in compile_selection(r,p,[],REGISTRY)[0]['flags']


def test_negative_assertions_need_source_negation_address():
    p,r,ref=fixture();r['records'][0]['polarity']='negative'
    assert 'negation_missing' in compile_selection(r,p,[],REGISTRY)[0]['flags']
    r['records'][0]['negation_evidence']=[ref(1)]
    # Address check alone does not establish the semantic truth of negation.
    assert compile_selection(r,p,[],REGISTRY)[0]['negation_witnesses'][0]['text']==p['text_blocks'][1]['text']


def test_format_recovery_does_not_rewrite_source_text_and_rejects_collision():
    a={' head_surface':'  pow-\ner ', ' relation':' causes ', ' head_evidence_ids':[' u1 ']}
    b=normalize_legacy(a)
    assert b=={'head_surface':'  pow-\ner ','relation':'causes','head_evidence_ids':['u1']}
    with pytest.raises(ValueError): normalize_legacy({'unit_id':'u',' unit_id':'v'})


def test_legacy_replay_keeps_conditions_unassigned_not_auto_inherited():
    p,_,_=fixture();old=dict(contexts=[dict(context_id='c',conditions_zh=['皮囊过紧','碳环松动'],qualifier_evidence=[])],
        records=[dict(context_id='c',head_surface='bellows',tail_surface='fitting tool',head_evidence_ids=['n1'],
            tail_evidence_ids=['n1'],evidence=[dict(unit_id='n1',quote=p['text_blocks'][1]['text'])],conditions_zh=[]),None])
    out=replay_legacy(old,p,[])
    assert len(out)==2 and out[0]['head_bound'] and out[0]['tail_bound']
    assert out[0]['unassigned_context_conditions']==['皮囊过紧','碳环松动']
    assert not out[0]['ownership_inferred']


def test_malformed_enum_objects_are_counted_and_flagged_not_crashes():
    p,r,_=fixture();r['records'][0].update(modality=[],polarity={})
    r['conditions'][0]['kind']={}
    out=compile_selection(r,p,[],REGISTRY)
    assert len(out)==2 and not out[0]['automatic_pass']
    assert {'modality_missing','polarity_missing','invalid_condition_kind'} <= set(out[0]['flags'])


def test_contiguous_multiunit_endpoint_reads_individual_actual_spans():
    p,r,_=fixture();p['text_blocks'][1]['text']='Use a fitting';p['text_blocks'][2]['text']='tool carefully.'
    c=catalog(p)
    refs=[dict(unit_id=f'U{i:04d}',start=0,end=len(c[f'U{i:04d}']['tokens'])) for i in [1,2]]
    a=r['records'][0];a['head']['spans']=[dict(unit_id='U0001',start=2,end=3)]
    a['tail']['spans']=refs;a['evidence']=refs;a['condition_ids']=[]
    r.update(records=[a],conditions=[],catalog_sha256=digest(c))
    out=compile_selection(r,p,[],REGISTRY)[0]
    assert out['automatic_pass'] and out['tail']['surface']=='Use a fitting\ntool carefully.'
    assert len(out['tail']['source_spans'])==2
