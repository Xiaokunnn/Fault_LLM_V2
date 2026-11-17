"""Controls that prevent false improvements in the isolated RP1 study."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from rp1_complex_binding_common import budget,response_schema,validated_view,save,source_view,TYPES,REGISTRY
from research_point_1_graph_evidence.stage02_triple_extraction.chinese_extraction_contract import EVIDENCE_ROLES

def test_ontology_and_roles_remain_frozen():
    s=response_schema()['properties']['triples']['items']['properties']
    assert len(TYPES)==13 and len(REGISTRY)==15
    assert set(s['evidence_role']['enum'])==set(EVIDENCE_ROLES)
    assert 'fault_class_ids' in s

def test_source_retains_entire_page_and_every_cell_and_requests_all_roles():
    p={'page_text':'whole source including difficult cases','tables':[{'table_id':'t1','rows':[{'row_id':'r1','cells':[{'cell_id':'c1','text':'full cell text'}]}]}]}
    v=source_view(p)
    assert v['page_text']==p['page_text']
    assert v['tables'][0]['rows'][0]['cells'][0]['text']=='full cell text'
    assert 'cause_or_mechanism' in v['DOCUMENT_METADATA']['target_evidence_roles']

def test_reread_input_really_consumes_budget():
    first=budget(0,10000,1536)
    used=10000+first
    assert budget(used,12000,3584,total=25000)==25000-used-12000
    assert budget(0,33000,5120)==0
    assert budget(64000,2000,5120)==0

def test_rejected_member_cannot_leave_intact_and_binding():
    r={'output':{'bindings':[{'operator':'AND','members':[1,2],'text':'both','evidence_text':'both'}]},'validation':[{'index':1,'legacy_result':{'included':True,'payload':{'tail_surface':'A'}}},{'index':2,'legacy_result':{'included':False,'payload':{'tail_surface':'B'}}}]}
    v=validated_view(r)
    assert len(v['triples'])==1 and v['bindings']==[]
    assert len(v['unresolved'])==1

def test_surviving_bindings_are_reindexed_not_repaired():
    r={'output':{'bindings':[{'operator':'BEFORE','members':[2,3],'text':'first then second','evidence_text':'quote'}]},'validation':[{'index':2,'legacy_result':{'included':True,'payload':{'x':1}}},{'index':3,'legacy_result':{'included':True,'payload':{'x':2}}}]}
    assert validated_view(r)['bindings'][0]['members']==[1,2]

def test_no_rewriting_an_existing_result(tmp_path):
    p=tmp_path/'result.json';save(p,{'S':1});save(p,{'S':1})
    with pytest.raises(ValueError):save(p,{'S':2})
