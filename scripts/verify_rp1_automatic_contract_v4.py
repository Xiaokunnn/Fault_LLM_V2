#!/usr/bin/env python3
"""Artifact, independence, deterministic replay and evidence checks for both runs."""
import ast
import copy
import importlib.util
import json
import re
from unittest.mock import patch
from rp1_offline_contract_v3 import *
BASELINE=BASE/'automatic_contract_v4'
FIXED=BASE/'automatic_contract_v4_1'

def identity_free(x):
    if isinstance(x,dict):return {k:identity_free(v) for k,v in x.items() if k not in {'cell_id','row_id','table_id','row_group_id','evidence_unit_ids'}}
    if isinstance(x,list):return [identity_free(v) for v in x]
    return x

def rename_addresses(page,a):
    p=copy.deepcopy(page);a=copy.deepcopy(a)
    p['doc_id']='opaque-document';p['page_key']='opaque-page';p['pdf_page_number']=99999
    keys={'cell_id','row_id','table_id','row_group_id'};names={}
    def inventory(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k in keys and isinstance(v,str):names.setdefault(v,f'opaque-address-{len(names)}')
                else:inventory(v)
        elif isinstance(x,list):
            for v in x:inventory(v)
    inventory(p)
    def update(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k in keys and isinstance(v,str):x[k]=names.get(v,v)
                else:update(v)
        elif isinstance(x,list):
            for v in x:update(v)
    update(p);a['evidence_unit_ids']=[names.get(x,x) for x in a['evidence_unit_ids']]
    a['candidate_review_id']='arbitrary-changed-candidate';a['teacher_label']='do-not-read';a['arm']='arbitrary-arm'
    return p,a

def load_module(path):
    spec=importlib.util.spec_from_file_location(path.stem,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def verify_run(out,suffix):
    frozen=json.loads((out/'execution_freeze.json').read_text())
    for p,h in frozen['sha256'].items():assert sha(ROOT/p)==h,p
    ef=json.loads((out/'evaluation_freeze.json').read_text())
    assert sha(ROOT/'scripts/evaluate_rp1_automatic_contract_v4.py')==ef['evaluator_sha256']
    assert sha(out/'automatic_outputs.jsonl')==ef['output_sha256']
    assert sha(out/'AI_source_review_466.jsonl')==ef['review_sha256']
    module_path=ROOT/f'src/research_point_1_graph_evidence/stage03_schema_validation/automatic_contract_{suffix}.py'
    code=module_path.read_text();tree=ast.parse(code)
    imports=[n.names[0].name for n in tree.body if isinstance(n,ast.Import)]
    assert set(imports)=={'copy','re'}
    assert not any(isinstance(n,ast.ImportFrom) for n in ast.walk(tree))
    assert not re.search(r'MP\d{3}|VR\d{2}|offline_contract_v3|reference_match|candidate_adjudications',code)
    forbidden={'open','read_text','read_bytes','write_text','exec','eval','__import__'}
    for n in ast.walk(tree):
        if isinstance(n,ast.Call):
            name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
            assert name not in forbidden,(module_path,name)
    module=load_module(module_path)
    pages={p['page_key']:p for p in rows(SOURCE/'pilot_sources.jsonl')}
    raw={a['candidate_review_id']:{k:v for k,v in a.items() if k not in ['candidate_review_id','mechanical']} for p in rows(REVIEW/'arm_masked_review_packets.jsonl') for a in p['assertions']}
    outputs=rows(out/'automatic_outputs.jsonl');assert len(outputs)==466
    witness_count=0
    # Reverse input order, alter identity metadata and block runtime file opens.
    for d in reversed(outputs):
        a=raw[d['candidate_review_id']];p=pages[d['page_key']]
        assert object_sha(a)==d['original_sha256']
        rp,ra=rename_addresses(p,a)
        with patch('builtins.open',side_effect=AssertionError('runtime file IO forbidden')):
            exact=module.transform(a,p,REGISTRY,filter_flags,d['mode'])
            metamorphic=module.transform(ra,rp,REGISTRY,filter_flags,d['mode'])
        for k,v in exact.items():assert d[k]==v,(out.name,d['candidate_review_id'],k)
        assert identity_free(exact)==identity_free(metamorphic),(out.name,d['candidate_review_id'],'ID dependence')
        native={c['cell_id']:c for t in p['tables'] for row in t['rows'] for c in row['cells']}
        for w in d['source_witnesses']:
            source=p['page_text'] if w['kind']=='page_span' else native[w['cell_id']]['text']
            assert source[w['start']:w['end']]==w['text']
            if w['kind']!='page_span':assert w['bbox']==native[w['cell_id']].get('bbox')
            witness_count+=1
        if d['included'] and not d['payload'].get('record_kind'):assert type_valid(d['payload'])
    review={(x['stage'],x['candidate_review_id']):x for x in rows(out/'AI_source_review_466.jsonl')}
    match=rows(out/'reference_matches_340.jsonl');assert len(match)==340
    for s in json.loads((out/'summary.json').read_text()):
        ds=[d for d in outputs if d['stage']==s['stage'] and d['prompt_arm']==s['prompt_arm'] and d['included'] and channel(d['payload'])=='core']
        good=[d for d in ds if review[(d['stage'],d['candidate_review_id'])]['AI_contract_status']=='complete']
        assert len(good)==s['complete_core_records']
        fm=[m for m in match if m['stage']==s['stage'] and m['prompt_arm']==s['prompt_arm'] and m['state']=='full']
        assert len(fm)==s['full_reference_matches'] and len({m['allocated_candidate_id'] for m in fm})==len(fm)
        for m in fm:assert any(d['candidate_review_id']==m['allocated_candidate_id'] for d in good)
    result={'status':'passed','generation_decisions_verified':466,'reverse_order_replays':466,'candidate_page_and_native_ID_invariance_checks':466,
       'runtime_file_open_blocked_during_replay':True,'runtime_only_stdlib_copy_re':True,'source_witnesses_round_tripped':witness_count,
       'reference_matches':340,'synthetic_tests':json.loads((out/'synthetic_tests.json').read_text())['tests'],
       'formal_accuracy_recall':'not_computed','independent_expert_review':'pending','heldout_contents_opened':0,'new_API_calls':0}
    write(out/'verification.json',result)
    return result

def main():
    before=json.loads((BASELINE/'preservation_before.json').read_text())['sha256']
    for p,h in before.items():assert sha(ROOT/p)==h,p
    parent=json.loads((FIXED/'parent_preservation.json').read_text())['sha256']
    for p,h in parent.items():assert sha(ROOT/p)==h,p
    a=verify_run(BASELINE,'v4');b=verify_run(FIXED,'v4_1')
    old={(x['stage'],x['candidate_review_id']):x for x in rows(BASELINE/'automatic_outputs.jsonl')}
    new={(x['stage'],x['candidate_review_id']):x for x in rows(FIXED/'automatic_outputs.jsonl')}
    changed=[k for k in old if old[k]!=new[k]]
    assert set(changed)=={('P0','VR11:A011'),('P1','VR11:A011'),('P1','VR06:A016'),('P1','VR08:A014')}
    write(FIXED/'patch_impact.json',{'changed_outputs':changed,'all_other_decisions_byte_value_identical':462,'parent_frozen_files_preserved':len(parent),'prior_files_preserved':len(before),'patch_scope':'only two documented parser defects'})
    write(FIXED/'promotion_gate.json',{'development_joint_criteria':'PASS_with_AI_technical_labels_after_disclosed_parser_patch',
        'formal_method_promotion':'NOT_ESTABLISHED','reason':['independent reference and expert review pending','residual problem and unresolved outputs remain','six pages used for method development','P1 loses one E0 correct record relative to P0'],
        'heldout_pages_opened':0,'new_API_calls':0,'new_graph_records':0})
    print(json.dumps({'baseline_v4':a,'corrected_v4_1':b,'prior_files_preserved':len(before),'patch_changed_outputs':len(changed)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
