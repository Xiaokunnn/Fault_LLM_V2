import copy
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from rp1_offline_contract_v3 import REGISTRY
from research_point_1_graph_evidence.stage03_schema_validation.batch_evidence_repair_v1 import repair


def cell(i, text, x, y, height=10):
    return dict(cell_id=i, text=text, bbox=dict(x0=x, x1=x+90, top=y, bottom=y+height))


def source(merged=False):
    headers=[cell('h0','Fault',0,0),cell('h1','Cause',100,0),cell('h2','Remedy',200,0)]
    # Extra padding cell deliberately disagrees with data-cell list positions.
    headers.insert(1,cell('pad','',92,0))
    data=[cell('f','Low flow',0,20,30 if merged else 10),cell('c','Blocked pipe',100,20),cell('a','Clean pipe',200,20)]
    return dict(doc_id='MP005',pdf_page_number=1,page_text_sha256='p',document_sha256='d',
        page_width=600,page_text='',text_blocks=[],tables=[dict(rows=[dict(cells=headers),dict(cells=data)])])


def candidate(**kw):
    r=dict(doc_id='MP005',pdf_page_number=1,page_text_sha256='p',document_sha256='d',
        head_surface='Low flow',head_type='FaultMode',head='low',head_canonical_zh='低流量',
        relation='causes',tail_surface='Blocked pipe',tail_type='Cause',tail='pipe',tail_canonical_zh='堵管',
        evidence_text='Low flow Blocked pipe',evidence_unit_ids=[],rejection_reasons=[])
    r.update(kw)
    return r


def test_header_geometry_recovers_direction_and_all_endpoint_fields():
    r=candidate();p=source();before=copy.deepcopy((r,p))
    with patch('builtins.open', side_effect=AssertionError('runtime IO')):
        result,reason=repair(r,p,REGISTRY)
    assert reason is None and result['swapped']
    assert result['payload']['head_type']=='Cause'
    assert result['payload']['head_canonical_zh']=='堵管'
    assert result['payload']['tail_canonical_zh']=='低流量'
    assert result['modality']=='possible'
    assert (r,p)==before


def test_merged_fault_cell_accepts_second_cause_but_not_different_fault():
    p=source(True);p['tables'][0]['rows'].append(dict(cells=[cell('c2','Low speed',100,40)]))
    assert repair(candidate(tail_surface='Low speed'),p,REGISTRY)[0]
    p['tables'][0]['rows'][-1]['cells'][0]['bbox'].update(top=60,bottom=70)
    assert repair(candidate(tail_surface='Low speed'),p,REGISTRY)[0] is None


def test_ambiguous_table_matches_stay_unresolved():
    p=source();other=copy.deepcopy(p['tables'][0])
    for row in other['rows']:
        for c in row['cells']:c['cell_id']+='second'
    p['tables'].append(other)
    assert repair(candidate(),p,REGISTRY)==(None,'ambiguous_table_binding')


def test_no_explicit_header_no_table_recovery():
    p=source();p['tables'][0]['rows'][0]['cells'][0]['text']='Details'
    assert repair(candidate(),p,REGISTRY)[0] is None


def test_known_model_contradiction_is_preserved():
    assert repair(candidate(rejection_reasons=['dual_qwen_relation_not_entailed']),source(),REGISTRY)==(None,'prior_model_contradiction')


def test_source_identity_mismatch_is_error():
    with pytest.raises(ValueError,match='Source identity'):
        repair(candidate(page_text_sha256='wrong'),source(),REGISTRY)


def test_nonbuild_or_general_manual_not_expanded():
    for doc in ['MP008','MP009','MP001','MP019']:
        p=source();p['doc_id']=doc
        assert repair(candidate(doc_id=doc),p,REGISTRY)==(None,'scope_not_extended')


@pytest.mark.parametrize('quote,swapped',[
    ('Blockage causes low flow.',False),
    ('Low flow is caused by blockage.',False),
    ('Low flow causes blockage.',True),
])
def test_explicit_prose_direction(quote,swapped):
    p=source();p['tables']=[];p['page_text']=quote
    p['text_blocks']=[dict(block_id='b',text=quote,bbox=dict(x0=20,x1=220,top=20,bottom=30))]
    r=candidate(head_surface='Blockage',head_type='FaultMode',tail_surface='low flow',tail_type='FaultMode',evidence_text=quote)
    result,_=repair(r,p,REGISTRY)
    assert result and result['swapped']==swapped
    assert result['source_witnesses'][0]['text'] in quote


def test_prose_flip_cannot_bypass_type_constraints():
    q='Low flow causes blockage.';p=source();p['tables']=[];p['page_text']=q
    p['text_blocks']=[dict(block_id='b',text=q,bbox=dict(x0=20,x1=220,top=20,bottom=30))]
    r=candidate(head_surface='Blockage',head_type='Cause',tail_surface='low flow',tail_type='FaultMode',evidence_text=q)
    # The corrected direction would place Cause in a forbidden range.
    assert repair(r,p,REGISTRY)[0] is None


def test_material_list_is_not_a_maintenance_action():
    p=source();p['tables'][0]['rows'][1]['cells'][2]['text']='Stainless steel'
    r=candidate(tail_surface='Stainless steel',tail_type='MaintenanceAction',relation='mitigated_by')
    assert repair(r,p,REGISTRY)[0] is None


def test_negative_causal_sentence_not_promoted():
    q='Blockage does not cause low flow.';p=source();p['tables']=[];p['page_text']=q
    p['text_blocks']=[dict(block_id='b',text=q,bbox=dict(x0=20,x1=220,top=20,bottom=30))]
    assert repair(candidate(head_surface='Blockage',head_type='Cause',tail_surface='low flow',tail_type='FaultMode',evidence_text=q),p,REGISTRY)[0] is None
