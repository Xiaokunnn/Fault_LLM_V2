#!/usr/bin/env python3
"""Offline development on all 138 preserved outputs; no generation/graph write."""
import json
import sys
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from rp1_offline_contract_v3 import BASE,REGISTRY,rows,write,sha
from research_point_1_graph_evidence.stage02_triple_extraction.step_fragment_extraction import prepare_local_catalog,local_model_input,compile_local_records

OLD=BASE/'fragment_extraction/validation';OUT=BASE/'sentence_step_extraction/development'


def flat(s):return ''.join(s.casefold().split())


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for d in ['catalogs','model_inputs']:(OUT/d).mkdir(exist_ok=True)
    dictionary=json.load(open(BASE/'fragment_extraction/development/endpoint_dictionary.json'))
    source={s['page_key']:s for s in rows(OLD/'sources.jsonl')};audit=[];roundtrips=0;examples=[]
    for req in rows(OLD/'requests.jsonl'):
        rid=req['request_id'];s=source[req['page_key']]
        cat=prepare_local_catalog(s['target'],s['context_pages'],dictionary)
        assert cat['coverage']['source_character_coverage']==1
        write(OUT/'catalogs'/f'{rid}.json',cat);write(OUT/'model_inputs'/f'{rid}.json',local_model_input(cat))
        native={}
        for p in [s['target'],*s['context_pages']]:
            native.update({b['block_id']:b for b in p['text_blocks']})
            native.update({c['cell_id']:c for t in p['tables'] for r in t['rows'] for c in r['cells']})
        for obj in [*cat['headings'].values(),*[a for u in cat['units'].values() for a in [u,*u['choices'].values()]]]:
            for w in obj['source_spans']:
                assert native[w['unit_id']]['text'][w['start']:w['end']]==w['text']
                assert native[w['unit_id']]['bbox']==w['bbox'];roundtrips+=1
        oldcat=json.load(open(OLD/'catalogs'/f'{rid}.json'))
        response=json.load(open(OLD/'api'/f'{rid}.parsed.json'))
        for i,raw in enumerate(response['records'],1):
            matches=[]
            if isinstance(raw,dict):
                ep={side:oldcat['candidates'].get(raw.get(side,[None])[0],{}) for side in ['head','tail']}
                for u in cat['units'].values():
                    if not u['target']:continue
                    found={}
                    for side in ['head','tail']:
                        old=ep[side];kind='action' if raw.get(side,[None,None])[1] in ('MaintenanceAction','InspectionAction','InspectionMethod') else None
                        found[side]=[c['id'] for c in u['choices'].values() if old.get('text') and
                            (c['kind']==kind if kind else c['kind']!='action') and
                            flat(old['text']) in flat(c['text']) and
                            any(a['unit_id']==b['unit_id'] and a['start']<b['end'] and b['start']<a['end'] for a in old.get('source_spans',[]) for b in c['source_spans'])]
                    if all(found.values()):matches.append(dict(unit=u['id'],choices=found))
            audit.append(dict(candidate_id=f'{rid}:{i:03d}',page_key=s['page_key'],matches=matches,
                both_endpoints_representable=bool(matches),cached_response_changed=False,
                semantic_quality_improvement_established=False))
        # Regression examples exercise selection/ownership only, not new output.
        if rid in ['F01','F06']:
            phrase='Place the support disc' if rid=='F01' else '4 Mount the preheated bearing'
            for u in cat['units'].values():
                actions=[c for c in u['choices'].values() if c['kind']=='action' and phrase in c['text']]
                if actions:
                    a=max(actions,key=lambda c:len(c['text']))
                    examples.append(dict(page_key=s['page_key'],source_action=a['text'],required_local=a['required'],
                        shared=[cat['headings'][sid]['text'] for sid in u['shared_ids']],
                        claim='source-interface regression, not generated new knowledge'))
                    break
    write(OUT/'cache_audit.jsonl',audit);write(OUT/'source_regressions.jsonl',examples)
    result=dict(cached_candidates=len(audit),both_endpoints_representable=sum(a['both_endpoints_representable'] for a in audit),
        all_cached_candidates_preserved=True,native_source_roundtrips=roundtrips,API_calls=0,
        source_semantic_accuracy_or_model_gain=None,graph_promoted=False,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [OLD/'sources.jsonl',OLD/'decisions.jsonl',OLD/'quality_metrics.json']},
        cached_interface_flags=dict(Counter(f for a in rows(OLD/'decisions.jsonl') for f in a['flags'])))
    write(OUT/'summary.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['source_hashes','cached_interface_flags']},indent=2))


if __name__=='__main__':main()
