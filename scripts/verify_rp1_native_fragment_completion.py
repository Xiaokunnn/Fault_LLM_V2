#!/usr/bin/env python3
"""Independent artifact checks; no model, repair, generation or graph writes."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_rp1_native_fragment_completion import DEFAULT,rows,sha,save,verify_preservation
from research_point_1_graph_evidence.stage02_triple_extraction.contextual_extraction import units_of


def verify(out):
    verify_preservation(out)
    complete=json.loads((out/'generation_complete.json').read_text())
    assert sha(out/'outputs.jsonl')==complete['outputs_sha256']
    assert sha(out/'blind_relation_inputs.jsonl')==complete['blind_inputs_sha256']
    manifest=json.loads((out/'candidate_pool_manifest.json').read_text())
    assert manifest['B1']==manifest['B2'] and len(manifest['B1'])==39
    decisions=rows(out/'outputs.jsonl');counts=Counter(r['arm'] for r in decisions)
    assert counts['B0']==484 and counts['B1']==counts['B2']==complete['common_candidates']
    for page,h in manifest['B1'].items():
        path=out/'common_candidates'/f'{page}.jsonl';assert sha(path)==h
        pool={r['id'] for r in rows(path)}
        for arm in ['B1','B2']:
            selected=[r for r in decisions if r['page_key']==page and r['arm']==arm]
            assert len(selected)==len(pool) and {r['candidate_id'] for r in selected}==pool
            assert all(r['common_pool_sha256']==h for r in selected)
    checked=0
    def spans(obj,native):
        nonlocal checked
        if isinstance(obj,list):
            for value in obj:spans(value,native)
        elif isinstance(obj,dict):
            if {'unit_id','start','end','text'}<=set(obj) and obj['unit_id'] in native:
                u=native[obj['unit_id']]
                assert u['text'][obj['start']:obj['end']]==obj['text']
                assert obj.get('bbox')==u.get('bbox');checked+=1
            for value in obj.values():
                if isinstance(value,(dict,list)):spans(value,native)
    for source in rows(out/'sources.jsonl'):
        key=source['page_key'];native=units_of([source['target'],*source['context_pages']])
        spans(json.loads((out/'catalogs'/f'{key}.json').read_text()),native)
        spans(rows(out/'common_candidates'/f'{key}.jsonl'),native)
    blind=rows(out/'blind_relation_inputs.jsonl')
    for row in blind:
        assert set(row)=={'review_id','page_key','body'}
        assert set(row['body'])=={'task','assertion','canonicalization_status'}
        assert not ({'arm','included','origin','grade','verdict','reference_matches'} & set(row['body']['assertion']))
    result=dict(status='PASS',original_occurrences=counts['B0'],common_candidates=counts['B1'],B1_B2_same_candidate_files=True,native_roundtrips_including_qualifiers=checked,original_assets_preserved=True,blind_relation_inputs=len(blind),semantic_audit_complete=(out/'review_complete.json').exists())
    save(out/('verification.json' if result['semantic_audit_complete'] else 'generation_verification.json'),result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=DEFAULT);args=ap.parse_args();verify(args.out)
