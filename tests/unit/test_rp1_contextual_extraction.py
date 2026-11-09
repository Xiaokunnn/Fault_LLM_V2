import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from rp1_offline_contract_v3 import REGISTRY
from research_point_1_graph_evidence.stage02_triple_extraction.contextual_extraction import compile_records

def fixture():
    texts=['M7N seal assembly','The opening must match the locking pin.','Press the counter ring into the seal compartment.']
    p=dict(doc_id='MP015',pdf_page_number=42,source_url='https://example.org/source',document_sha256='d',page_text_sha256='p',tables=[],
        text_blocks=[dict(block_id=f'u{i}',text=t,bbox=dict(x0=10,x1=200,top=20*i,bottom=20*i+10)) for i,t in enumerate(texts)])
    c=dict(context_id='c',kind='procedure',qualifier_evidence=[dict(unit_id='u0',quote=texts[0]),dict(unit_id='u1',quote=texts[1])],
        conditions_zh=['M7N密封装配','开孔必须匹配定位销'],applicability_zh='FreFlow M7N密封',branch={})
    a=dict(context_id='c',head_surface='counter ring',head_canonical_zh='静环',head_type='Component',relation='maintained_by',
        tail_surface=texts[2][:-1],tail_canonical_zh='将静环压入密封腔',tail_type='MaintenanceAction',polarity='positive',modality='required',
        scope='primary',head_evidence_ids=['u2'],tail_evidence_ids=['u2'],evidence=[dict(unit_id='u2',quote=texts[2])],conditions_zh=[],unresolved_reason=None)
    return p,dict(contexts=[c],records=[a])

def test_shared_model_and_pin_condition_inherit_with_native_witnesses():
    p,r=fixture();before=copy.deepcopy((p,r));a=compile_records(r,p,[],REGISTRY)[0]
    assert a['automatic_pass'] and a['inherited_conditions_zh']==['M7N密封装配','开孔必须匹配定位销']
    assert (p,r)==before
    units={b['block_id']:b for b in p['text_blocks']}
    for w in a['source_witnesses']:assert units[w['unit_id']]['text'][w['start']:w['end']]==w['text']

def test_fabricated_qualifier_does_not_pass():
    p,r=fixture();r['contexts'][0]['qualifier_evidence'][1]['quote']='Use a different pump model.'
    assert not compile_records(r,p,[],REGISTRY)[0]['automatic_pass']

def test_previous_page_can_only_supply_context():
    p,r=fixture();prev=copy.deepcopy(p);prev['pdf_page_number']=41
    for b in prev['text_blocks']:b['block_id']='prev'+b['block_id']
    r['contexts'][0]['qualifier_evidence'][0]['unit_id']='prevu0'
    assert compile_records(r,p,[prev],REGISTRY)[0]['automatic_pass']
    r['records'][0]['evidence'][0]['unit_id']='prevu2'
    assert 'no_target_page_relation' in compile_records(r,p,[prev],REGISTRY)[0]['flags']

def test_negation_is_not_lost_on_compile():
    p,r=fixture();r['records'][0]['polarity']='negative'
    assert compile_records(r,p,[],REGISTRY)[0]['raw']['polarity']=='negative'

def test_malformed_and_unresolved_records_remain_in_denominator():
    p,r=fixture();r['records'] += [None,{'relation':[],'context_id':[],'head_evidence_ids':[{}]}]
    r['records'][0]['unresolved_reason']='ambiguous source'
    out=compile_records(r,p,[],REGISTRY)
    assert len(out)==3 and all(not a['automatic_pass'] for a in out)

def test_duplicate_context_id_and_wrong_semantic_schema_are_rejected():
    p,r=fixture();r['contexts'].append(copy.deepcopy(r['contexts'][0]))
    assert 'missing_or_duplicate_context' in compile_records(r,p,[],REGISTRY)[0]['flags']
    r['contexts'].pop();r['records'][0]['tail_type']='Component'
    assert 'schema_type_or_relation' in compile_records(r,p,[],REGISTRY)[0]['flags']

def test_table_cause_roles_cannot_be_reversed():
    p,r=fixture();c=r['contexts'][0];c.update(kind='table_branch',branch=dict(fault_ids=['u1'],cause_ids=['u2'],action_ids=['u2']))
    a=r['records'][0];a.update(relation='causes',head_type='FaultMode',tail_type='FaultMode')
    assert 'table_cause_direction' in compile_records(r,p,[],REGISTRY)[0]['flags']

def test_contiguous_multiblock_endpoint_keeps_individual_original_spans():
    p,r=fixture();p['text_blocks'][2]['text']='Press the counter ring'
    p['text_blocks'].append(dict(block_id='u3',text='into the seal compartment.',bbox=dict(x0=10,x1=200,top=60,bottom=70)))
    # Adjacent line gap must match the native locator contract.
    p['text_blocks'][3]['bbox'].update(top=53,bottom=63)
    r['records'][0]['tail_evidence_ids']=['u2','u3']
    r['records'][0]['evidence']=[dict(unit_id='u2',quote='Press the counter ring'),dict(unit_id='u3',quote='into the seal compartment.')]
    out=compile_records(r,p,[],REGISTRY)[0]
    assert out['automatic_pass'] and {w['unit_id'] for w in out['source_witnesses']}=={'u0','u1','u2','u3'}
    r['records'][0]['evidence'][1]['quote']='compartment.'
    assert not compile_records(r,p,[],REGISTRY)[0]['automatic_pass']

def test_multiblock_endpoint_cannot_cross_large_gap():
    p,r=fixture();p['text_blocks'][2]['text']='Press the counter ring'
    p['text_blocks'].append(dict(block_id='u3',text='into the seal compartment.',bbox=dict(x0=10,x1=200,top=300,bottom=310)))
    r['records'][0]['tail_evidence_ids']=['u2','u3'];r['records'][0]['evidence']=[dict(unit_id='u2',quote='Press the counter ring'),dict(unit_id='u3',quote='into the seal compartment.')]
    assert not compile_records(r,p,[],REGISTRY)[0]['automatic_pass']

def test_explicit_blocks_remain_valid_when_parser_also_wraps_prose_as_table():
    p,r=fixture();p['text_blocks'][2]['text']='Press the counter ring'
    p['text_blocks'].append(dict(block_id='u3',text='into the seal compartment.',bbox=dict(x0=10,x1=200,top=53,bottom=63)))
    p['tables']=[dict(table_id='t',bbox=dict(x0=0,x1=250,top=35,bottom=75),rows=[dict(row_id='row',cells=[dict(cell_id='cell',text='Press the counter ring\ninto the seal compartment.',bbox=dict(x0=0,x1=250,top=35,bottom=75))])])]
    r['records'][0]['tail_evidence_ids']=['u2','u3'];r['records'][0]['evidence']=[dict(unit_id='u2',quote='Press the counter ring'),dict(unit_id='u3',quote='into the seal compartment.')]
    assert compile_records(r,p,[],REGISTRY)[0]['automatic_pass']
