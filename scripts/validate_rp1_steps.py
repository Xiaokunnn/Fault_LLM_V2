#!/usr/bin/env python3
"""Fixed new-page trial of sentence/step selection; no graph publication."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from rp1_offline_contract_v3 import BASE,REGISTRY,rows,sha,write
import validate_rp1_fragments as transport
from run_rp1_targeted_v2_1 import payload_bytes
from research_point_1_graph_evidence.stage02_triple_extraction.step_fragment_extraction import prepare_local_catalog,local_model_input,local_system_prompt,compile_local_records
from research_point_1_graph_evidence.stage02_triple_extraction.source_fragment_extraction import BUILD_DOCS

OUT=BASE/'sentence_step_extraction';RUN=OUT/'validation';OLD=BASE/'fragment_extraction/validation'
SEED='RP1-sentence-step-new-pages-20261013'
MODULE=ROOT/'src/research_point_1_graph_evidence/stage02_triple_extraction/step_fragment_extraction.py'


def prepare():
    if (RUN/'method.json').exists():raise ValueError('method already frozen; no replacement')
    RUN.mkdir(parents=True,exist_ok=True)
    for d in ['catalogs','model_inputs']:(RUN/d).mkdir(exist_ok=True)
    dependencies=[MODULE,Path(__file__),ROOT/'tests/unit/test_rp1_step_fragment_extraction.py',
        ROOT/'src/research_point_1_graph_evidence/stage02_triple_extraction/source_fragment_extraction.py',
        ROOT/'src/research_point_1_graph_evidence/stage02_triple_extraction/contextual_extraction.py',
        ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/layout_direction_context_v1.py',
        ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json',
        BASE/'fragment_extraction/development/endpoint_dictionary.json',OUT/'development/summary.json']
    write(RUN/'method.json',dict(frozen_at=transport.now(),model='qwen3.8-max',temperature=0,
        max_tokens=16384,maximum_requests=10,automatic_retries=0,selection_seed=SEED,
        allocation={'maintenance':6,'prose':4},maximum_target_pages_per_document=3,
        source_frame='build documents except MP003 general vessel rules; explicit English pump-page requirements. Target unused; preceding page is context only and prior exposure disclosed. Same build-document page validation, not external/generalization study.',
        tables='maintenance interval/native-row handling developed from cached MP005 p69; no remaining eligible unseen English fault table in the existing pump-page selection frame, no new-table generalization claim',
        quality_population='all outputs, including malformed, duplicate, context-only, unresolved; no deletion from denominator',
        expansion_gate={'joint_supported_fraction':.75,'complete_reference_fraction':.75,'minimum_joint_distinct_relations':30,'all_in_scope_pages_nonempty':True},
        minimum_quantity='30 is a predeclared pilot adequacy threshold, not final graph scale or a theoretical guarantee',
        review='one existing source-AI review, not extra API review or expert approval. Pre-output source checklist nonexhaustive; not formal recall.',
        system_prompt=local_system_prompt(REGISTRY),sha256={str(p.relative_to(ROOT)):sha(p) for p in dependencies}))
    excluded=set(json.load(open(OLD/'selection.json'))['excluded_page_keys'])
    for s in rows(OLD/'sources.jsonl'):
        for p in [s['target'],*s['context_pages']]:excluded.add(f'{p["doc_id"]}:p{p["pdf_page_number"]:04d}')
    eligible=[];all_pages={};paths=[]
    for doc in sorted(BUILD_DOCS):
        path=ROOT/f'data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl';paths.append(path)
        for p in rows(path):
            key=f'{doc}:p{p["pdf_page_number"]:04d}';all_pages[key]=p
            kind=transport.classify(p)
            if doc!='MP003' and key not in excluded and kind in ('maintenance','prose'):
                eligible.append((hashlib.sha256((SEED+'|'+key).encode()).hexdigest(),key,kind,p))
    selected=[];counts=Counter()
    for kind,n in [('maintenance',6),('prose',4)]:
        for _,key,tag,p in sorted(eligible):
            if kind!=tag or counts[p['doc_id']]>=3:continue
            context=all_pages.get(f'{p["doc_id"]}:p{p["pdf_page_number"]-1:04d}')
            selected.append(dict(page_key=key,stratum=kind,target=p,context_pages=[context] if context else []));counts[p['doc_id']]+=1
            if sum(x['stratum']==kind for x in selected)==n:break
        assert sum(x['stratum']==kind for x in selected)==n
    requests=[];overview=[]
    dictionary=json.load(open(BASE/'fragment_extraction/development/endpoint_dictionary.json'))
    for i,s in enumerate(selected,1):
        rid=f'L{i:02d}';assert s['target']['document_split']=='build_train'
        cat=prepare_local_catalog(s['target'],s['context_pages'],dictionary)
        assert cat['coverage']['source_character_coverage']==1
        data=local_model_input(cat);write(RUN/'catalogs'/f'{rid}.json',cat);write(RUN/'model_inputs'/f'{rid}.json',data)
        payload=dict(model='qwen3.8-max',temperature=0,enable_thinking=False,response_format=dict(type='json_object'),max_tokens=16384,
            messages=[dict(role='system',content=local_system_prompt(REGISTRY)),dict(role='user',content=json.dumps(data,ensure_ascii=False))])
        requests.append(dict(request_id=rid,page_key=s['page_key'],stratum=s['stratum'],payload=payload,payload_sha256=hashlib.sha256(payload_bytes(payload)).hexdigest()))
        overview.append(dict(request_id=rid,page_key=s['page_key'],stratum=s['stratum'],
            context_pages=[f'{p["doc_id"]}:p{p["pdf_page_number"]:04d}' for p in s['context_pages']],
            context_previously_seen=[f'{p["doc_id"]}:p{p["pdf_page_number"]:04d}' in excluded for p in s['context_pages']],
            target_units=sum(u['target'] for u in cat['units'].values())))
    write(RUN/'sources.jsonl',selected);write(RUN/'requests.jsonl',requests)
    write(RUN/'selection.json',dict(excluded_page_keys=sorted(excluded),selected=overview,postselection_replacement=False,
        eligible_by_stratum=dict(Counter(x[2] for x in eligible)),parsed_source_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths}))
    print(json.dumps(overview,ensure_ascii=False,indent=2))


def seal():
    refs=rows(RUN/'source_reference.jsonl');assert set(x['page_key'] for x in refs)==set(x['page_key'] for x in rows(RUN/'sources.jsonl'))
    assert len({x['reference_id'] for x in refs})==len(refs)
    paths=[RUN/n for n in ['method.json','selection.json','sources.jsonl','requests.jsonl','source_reference.jsonl']]+sorted((RUN/'catalogs').glob('*.json'))+sorted((RUN/'model_inputs').glob('*.json'))
    write(RUN/'request_freeze.json',dict(frozen_at=transport.now(),requests_not_started=True,sha256={str(p.relative_to(ROOT)):sha(p) for p in paths}))
    print(json.dumps(dict(status='sealed',requests=10,reference_items=len(refs))))


def verify_inputs():
    transport.RUN=RUN
    return transport.verify_inputs()


def execute(prompt_key=False):
    transport.RUN=RUN
    return transport.execute(prompt_key)


def collect():
    decisions=[];pages=[]
    for req in verify_inputs():
        rid=req['request_id'];path=RUN/'api'/f'{rid}.parsed.json'
        if not path.exists():pages.append(dict(page_key=req['page_key'],status='no_complete_response'));continue
        cat=json.load(open(RUN/'catalogs'/f'{rid}.json'));response=json.load(open(path))
        records=compile_local_records(response,cat,REGISTRY)
        decisions += [dict(candidate_id=f'{rid}:{a["index"]:03d}',page_key=req['page_key'],**a) for a in records]
        pages.append(dict(page_key=req['page_key'],candidates=len(records),automatic_pass=sum(a['automatic_pass'] for a in records),
            reported_missing=response.get('missing'),flags=dict(Counter(f for a in records for f in a['flags']))))
    write(RUN/'decisions.jsonl',decisions)
    write(RUN/'automatic_summary.json',dict(candidates=len(decisions),automatic_pass=sum(a['automatic_pass'] for a in decisions),pages=pages,source_semantic_quality=None,graph_promoted=False))
    print(json.dumps(dict(candidates=len(decisions),automatic_pass=sum(a['automatic_pass'] for a in decisions),pages=pages),ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','seal','execute','collect']);parser.add_argument('--prompt-key',action='store_true');args=parser.parse_args()
    if args.stage=='execute':execute(args.prompt_key)
    else:globals()[args.stage]()
