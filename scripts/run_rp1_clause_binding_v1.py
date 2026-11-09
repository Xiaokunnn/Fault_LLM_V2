#!/usr/bin/env python3
"""Generate one matched filter/repair comparison; never read quality labels."""
import copy
import json
from rp1_offline_contract_v3 import ROOT, BASE, SOURCE, REVIEW, rows, sha, write, object_sha, filter_flags
from verify_rp1_automatic_contract_v4 import load_module, identity_free, rename_addresses
from unittest.mock import patch
PARENT = BASE / 'automatic_contract_v4_1'
OUT = BASE / 'clause_binding_v1'
MODULE = ROOT / 'src/research_point_1_graph_evidence/stage03_schema_validation/clause_binding_v1.py'
RESULT_KEYS = ('payload','included','rules','source_witnesses','barriers','screen_flags','changes','semantic_certification')

def inputs():
    pages = {p['page_key']:p for p in rows(SOURCE/'pilot_sources.jsonl')}
    raw = {a['candidate_review_id']:{k:v for k,v in a.items() if k not in ['candidate_review_id','mechanical']}
           for p in rows(REVIEW/'arm_masked_review_packets.jsonl') for a in p['assertions']}
    parents = [d for d in rows(PARENT/'automatic_outputs.jsonl') if d['stage']=='P1']
    assert len(parents)==len(raw)==233
    return pages,raw,parents

def semantic_parent(d): return {k:copy.deepcopy(d[k]) for k in RESULT_KEYS}

def verify(model,outputs,pages,raw,parents):
    parent_by_id={d['candidate_review_id']:d for d in parents}
    n_witnesses=0
    for d in reversed(outputs):
        p,a=pages[d['page_key']],raw[d['candidate_review_id']]
        b=semantic_parent(parent_by_id[d['candidate_review_id']])
        rp,ra=rename_addresses(p,a)
        oldcells=[c for t in p['tables'] for row in t['rows'] for c in row['cells']]
        newcells=[c for t in rp['tables'] for row in t['rows'] for c in row['cells']]
        mapping={x[k]:y[k] for x,y in zip(oldcells,newcells) for k in ['cell_id','row_id']}
        def remap(obj):
            if isinstance(obj,dict):return {k:remap(v) for k,v in obj.items()}
            if isinstance(obj,list):return [remap(v) for v in obj]
            return mapping.get(obj,obj) if isinstance(obj,str) else obj
        with patch('builtins.open',side_effect=AssertionError('runtime file IO forbidden')):
            exact=model.refine(a,p,b,filter_flags,d['mode'])
            renamed=model.refine(ra,rp,remap(b),filter_flags,d['mode'])
        assert all(d[k]==v for k,v in exact.items()),(d['stage'],d['candidate_review_id'])
        assert identity_free(exact)==identity_free(renamed),'identifier-dependent result'
        native={c['cell_id']:c for c in oldcells}
        for w in d['source_witnesses']:
            text=p['page_text'] if w['kind']=='page_span' else native[w['cell_id']]['text']
            assert text[w['start']:w['end']]==w['text']
            if w['kind']!='page_span':assert w['bbox']==native[w['cell_id']].get('bbox')
            n_witnesses+=1
    return dict(reverse_order_replays=len(outputs),ID_invariance_checks=len(outputs),runtime_file_open_blocked=True,
                source_witness_occurrences=n_witnesses)

def main():
    if (OUT/'outputs.jsonl').exists():raise SystemExit('Existing completed generation: preserve it; do not overwrite.')
    files=[MODULE,ROOT/'tests/unit/test_rp1_clause_binding_v1.py',ROOT/'scripts/run_rp1_clause_binding_v1.py',
           ROOT/'scripts/rp1_offline_contract_v3.py',ROOT/'scripts/verify_rp1_automatic_contract_v4.py',
           ROOT/'docs/research/RP1_CLAUSE_BINDING_V1_PROTOCOL_20261003.md',
           ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json',
           SOURCE/'pilot_sources.jsonl',REVIEW/'arm_masked_review_packets.jsonl',
           PARENT/'automatic_outputs.jsonl',PARENT/'execution_freeze.json']
    write(OUT/'execution_freeze.json',dict(stage='before first batch generation',sha256={str(p.relative_to(ROOT)):sha(p) for p in files},
        runtime_label_access=False,new_API_calls=0,heldout_pages_opened=0))
    pages,raw,parents=inputs();model=load_module(MODULE);outputs=[]
    for stage,mode in [('F','filter'),('R','repair')]:
        for parent in parents:
            a=raw[parent['candidate_review_id']];p=pages[parent['page_key']]
            assert object_sha(a)==parent['original_sha256']
            d=model.refine(a,p,semantic_parent(parent),filter_flags,mode)
            meta={k:parent[k] for k in ['candidate_review_id','prompt_arm','page_key','original_sha256','source_page_sha256']}
            outputs.append(dict(stage=stage,mode=mode,**meta,**d))
    write(OUT/'outputs.jsonl',outputs)
    verification=verify(model,outputs,pages,raw,parents)
    before=json.loads((OUT/'preservation_before.json').read_text())['sha256']
    # Also check the earlier preservation lineage, including RP3 experiment files.
    before.update(json.loads((PARENT/'parent_preservation.json').read_text())['sha256'])
    for path,digest in before.items():assert sha(ROOT/path)==digest,path
    verification.update(existing_files_unchanged=len(before),status='passed',new_API_calls=0,heldout_pages_opened=0)
    write(OUT/'verification.json',verification)
    write(OUT/'generation_completion.json',dict(outputs=len(outputs),inputs=233,baseline_reused=233,output_sha256=sha(OUT/'outputs.jsonl'),
        effect_metrics='not yet computed',semantic_review='pending separately'))
    touched=[dict(stage=d['stage'],id=d['candidate_review_id'],arm=d['prompt_arm'],**d['clause_binding'])
             for d in outputs if d['clause_binding']['issues']]
    write(OUT/'mechanism_events.jsonl',touched)
    print(json.dumps(dict(outputs=len(outputs),affected_decisions=len(touched),verification=verification),ensure_ascii=False))
if __name__=='__main__':main()
