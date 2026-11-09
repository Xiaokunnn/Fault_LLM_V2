#!/usr/bin/env python3
"""One fixed ten-page validation of the complete-fragment interface.

prepare -> source-first reference -> seal -> execute -> collect. Preserve all
responses and failures, no silent retries, substitutions or graph publication.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
import datetime
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from rp1_offline_contract_v3 import BASE,REGISTRY,rows,sha,write
from run_rp1_targeted_v2_1 import payload_bytes,NoRedirect
from research_point_1_graph_evidence.stage02_triple_extraction.source_fragment_extraction import (
    BUILD_DOCS,real_table,prepare_catalog,model_input,system_prompt,compile_records)

OUT=BASE/'fragment_extraction';RUN=OUT/'validation';OLD=BASE/'extraction_validation'
MODULE=ROOT/'src/research_point_1_graph_evidence/stage02_triple_extraction/source_fragment_extraction.py'
ENDPOINT='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
SEED='RP1-complete-fragments-fixed-validation-20261013'


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def priority(key):return hashlib.sha256((SEED+'|'+key).encode()).hexdigest()


def classify(p):
    text=' '.join(p['page_text'].split());low=text.lower()
    if p.get('source_language')!='en' or len(text)>9500:return None
    table=any(real_table(t) for t in p['tables'])
    english=len(re.findall(r'\b(the|and|of|to|is|with|for|should|must)\b',low))
    if table:
        if len(text)>=300 and english>=5 and re.search(r'\bpumps?\b',low+' '+p.get('title','').lower()):return 'table'
        return None
    if len(text)<600 or english<15 or not re.search(r'\bpumps?\b',low):return None
    if re.search(r'\b(assembly|disassembly|maintenance|removal|installation|fitting|lubrication)\b',low) and len(re.findall(r'\b(clean|remove|install|fit|replace|check|inspect|lubricate|tighten|press)\b',low))>=3:return 'maintenance'
    return 'prose'


def prepare():
    RUN.mkdir(parents=True,exist_ok=True)
    for d in ['catalogs','model_inputs']:(RUN/d).mkdir(exist_ok=True)
    dependencies=[MODULE,Path(__file__),ROOT/'tests/unit/test_rp1_source_fragment_extraction.py',
        ROOT/'src/research_point_1_graph_evidence/stage02_triple_extraction/contextual_extraction.py',
        ROOT/'src/research_point_1_graph_evidence/stage02_triple_extraction/native_evidence_selection.py',
        ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/layout_direction_context_v1.py',
        ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json',
        OUT/'development/endpoint_dictionary.json',OUT/'development/summary.json',
        OLD/'selection.json',OLD/'sources.jsonl']
    # Method frozen BEFORE target selection/reference reading and API outputs.
    write(RUN/'method.json',dict(frozen_at=now(),model='qwen3.8-max',temperature=0,max_tokens=16384,
        maximum_requests=10,automatic_retries=0,selection_seed=SEED,
        allocation={'maintenance':6,'prose':4},maximum_target_pages_per_document=3,
        selection_amendment='Before API: initial source-QC pages are now excluded. No unseen English native fault-table target remains in this frame. Validate six maintenance/four prose pages; table processing is development-only, no unseen-table gain claim.',
        purpose='new target pages in build documents; previous context may be previously seen; not document-disjoint field evaluation',
        source_characters='require full representation of primary nonwhitespace source characters; proof-backed duplicates recorded separately',
        quality_population='source-reading AI audit of ALL returned candidates including malformed/unresolved; no deletion from denominator',
        expansion_gate={'joint_source_AI_support_and_automatic_fraction':.75,
            'complete_fixed_source_reference_coverage':.75,
            'every_page_with_prespecified_in_scope_knowledge_has_at_least_one_joint_supported_relation':True},
        gate_meaning='engineering expansion criteria; source-first AI reference is not exhaustive expert ground truth or formal recall',
        quantities='all candidates, automatic pass, full-condition source AI support, joint support, exact distinct relations, missing reference items and pages',
        sha256={str(p.relative_to(ROOT)):sha(p) for p in dependencies},system_prompt=system_prompt(REGISTRY)))
    excluded=set(json.load(open(OLD/'selection.json'))['excluded_page_keys'])
    for s in rows(OLD/'sources.jsonl'):
        for p in [s['target'],*s['context_pages']]:excluded.add(f'{p["doc_id"]}:p{p["pdf_page_number"]:04d}')
    preflight=ROOT/'logs/rp1_fragment_preflight_20261013/initial_validation/sources.jsonl'
    preflights=[preflight,ROOT/'logs/rp1_fragment_preflight_20261013/candidate_qc_validation/sources.jsonl']
    for preflight in preflights:
      if preflight.exists():
        for s in rows(preflight):
            for p in [s['target'],*s['context_pages']]:excluded.add(f'{p["doc_id"]}:p{p["pdf_page_number"]:04d}')
    all_pages={};eligible=[];source_files=[]
    for doc in sorted(BUILD_DOCS):
        path=ROOT/f'data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl';source_files.append(path)
        for p in rows(path):
            key=f'{doc}:p{p["pdf_page_number"]:04d}';all_pages[key]=p
            kind=classify(p)
            if kind and key not in excluded:
                assert p['document_split']=='build_train'
                eligible.append((priority(key),key,kind,p))
    selected=[];counts=Counter()
    for kind,needed in [('maintenance',6),('prose',4)]:
        for _,key,tag,p in sorted(eligible):
            if tag!=kind or counts[p['doc_id']]>=3:continue
            previous=all_pages.get(f'{p["doc_id"]}:p{p["pdf_page_number"]-1:04d}')
            selected.append(dict(page_key=key,stratum=kind,target=p,context_pages=[previous] if previous else []))
            counts[p['doc_id']]+=1
            if sum(s['stratum']==kind for s in selected)==needed:break
        assert sum(s['stratum']==kind for s in selected)==needed,kind
    dictionary=json.load(open(OUT/'development/endpoint_dictionary.json'));requests=[];overview=[]
    for i,s in enumerate(selected,1):
        rid=f'F{i:02d}';cat=prepare_catalog(s['target'],s['context_pages'],dictionary)
        # No replacement for a layout failure. This assertion stops before API
        # and leaves the source/method for diagnosis rather than selecting anew.
        assert cat['coverage']['source_character_coverage']==1,s['page_key']
        write(RUN/'catalogs'/f'{rid}.json',cat);data=model_input(cat);write(RUN/'model_inputs'/f'{rid}.json',data)
        payload=dict(model='qwen3.8-max',temperature=0,enable_thinking=False,response_format=dict(type='json_object'),max_tokens=16384,
            messages=[dict(role='system',content=system_prompt(REGISTRY)),dict(role='user',content=json.dumps(data,ensure_ascii=False))])
        requests.append(dict(request_id=rid,page_key=s['page_key'],stratum=s['stratum'],catalog_sha256=cat['catalog_sha256'],
            payload_sha256=hashlib.sha256(payload_bytes(payload)).hexdigest(),payload=payload))
        overview.append(dict(request_id=rid,page_key=s['page_key'],stratum=s['stratum'],
            context_pages=[f'{p["doc_id"]}:p{p["pdf_page_number"]:04d}' for p in s['context_pages']],
            context_previously_seen=[f'{p["doc_id"]}:p{p["pdf_page_number"]:04d}' in excluded for p in s['context_pages']],
            complete_source_characters=cat['coverage']['total_nonwhitespace_characters'],choices=len(cat['candidates'])))
    write(RUN/'sources.jsonl',selected);write(RUN/'requests.jsonl',requests)
    write(RUN/'selection.json',dict(excluded_page_keys=sorted(excluded),eligible_by_stratum=dict(Counter(e[2] for e in eligible)),
        selected=overview,postselection_replacement=False,
        parsed_source_sha256={str(p.relative_to(ROOT)):sha(p) for p in source_files}))
    print(json.dumps(dict(status='prepared_not_called',selected=overview,excluded_target_pages=len(excluded)),ensure_ascii=False,indent=2))


def seal():
    refs=rows(RUN/'source_reference.jsonl');keys={s['page_key'] for s in rows(RUN/'sources.jsonl')}
    assert set(r['page_key'] for r in refs)==keys and len({r['reference_id'] for r in refs})==len(refs)
    paths=[RUN/'method.json',RUN/'sources.jsonl',RUN/'requests.jsonl',RUN/'selection.json',RUN/'source_reference.jsonl']+sorted((RUN/'catalogs').glob('*.json'))+sorted((RUN/'model_inputs').glob('*.json'))
    write(RUN/'request_freeze.json',dict(frozen_at=now(),requests_not_started=True,
        sha256={str(p.relative_to(ROOT)):sha(p) for p in paths}))
    print(json.dumps({'status':'sealed','reference_items':len(refs),'requests':10}))


def verify_inputs():
    for filename in ['method.json','request_freeze.json']:
        for name,h in json.load(open(RUN/filename))['sha256'].items():assert sha(ROOT/name)==h,name
    for name,h in json.load(open(RUN/'selection.json'))['parsed_source_sha256'].items():assert sha(ROOT/name)==h,name
    requests=rows(RUN/'requests.jsonl');assert len(requests)==10
    for req in requests:assert hashlib.sha256(payload_bytes(req['payload'])).hexdigest()==req['payload_sha256']
    return requests


def execute(prompt_key=False):
    requests=verify_inputs();key=os.environ.get('DASHSCOPE_API_KEY','').strip()
    if not key and prompt_key:key=getpass.getpass('DASHSCOPE_API_KEY (hidden, memory only): ').strip()
    if not key:raise ValueError('API key missing; no calls')
    directory=RUN/'api';directory.mkdir(exist_ok=True)
    def worker(req):
        rid=req['request_id'];started=directory/f'{rid}.started.json';raw=directory/f'{rid}.response.bin'
        if started.exists():return dict(request_id=rid,status='existing_attempt_preserved_no_retry')
        write(started,dict(started_at=now(),page_key=req['page_key'],payload_sha256=req['payload_sha256']))
        begin=time.monotonic();status=None
        try:
            request=urllib.request.Request(ENDPOINT,data=payload_bytes(req['payload']),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Connection':'close'},method='POST')
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=600) as response,raw.open('xb') as stream:
                status=response.status
                while True:
                    chunk=response.read(65536)
                    if not chunk:break
                    stream.write(chunk)
            envelope=json.loads(raw.read_bytes());choice=envelope['choices'][0];content=json.loads(choice['message']['content'])
            if choice.get('finish_reason')!='stop':raise ValueError('incomplete_response')
            if not isinstance(content,dict) or not isinstance(content.get('records'),list):raise ValueError('invalid_outer_schema')
            write(directory/f'{rid}.parsed.json',content)
            write(directory/f'{rid}.completed.json',dict(completed_at=now(),http_status=status,response_sha256=sha(raw),
                payload_sha256=req['payload_sha256'],returned_model=envelope.get('model'),usage=envelope.get('usage'),
                finish_reason=choice.get('finish_reason'),records=len(content['records']),elapsed_seconds=time.monotonic()-begin))
            return dict(request_id=rid,page_key=req['page_key'],status='archived',records=len(content['records']))
        except Exception as error:
            if isinstance(error,urllib.error.HTTPError):
                status=error.code
                if not raw.exists():raw.write_bytes(error.read())
            write(directory/f'{rid}.failed.json',dict(exception_class=type(error).__name__,http_status=status,elapsed_seconds=time.monotonic()-begin,no_retry=True))
            return dict(request_id=rid,status='failed',exception_class=type(error).__name__)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(worker,r) for r in requests]):print(json.dumps(future.result(),ensure_ascii=False),flush=True)


def collect():
    decisions=[];pages=[]
    for req in verify_inputs():
        path=RUN/'api'/f'{req["request_id"]}.parsed.json'
        if not path.exists():pages.append(dict(page_key=req['page_key'],candidates=None,status='no_complete_output'));continue
        cat=json.load(open(RUN/'catalogs'/f'{req["request_id"]}.json'));content=json.load(open(path))
        compiled=compile_records(content,cat,REGISTRY)
        decisions += [dict(candidate_id=f'{req["request_id"]}:{a["index"]:03d}',page_key=req['page_key'],**a) for a in compiled]
        pages.append(dict(page_key=req['page_key'],candidates=len(compiled),automatic_pass=sum(a['automatic_pass'] for a in compiled),
            unrepresented_source=content.get('unrepresented_source'),flags=dict(Counter(f for a in compiled for f in a['flags']))))
    write(RUN/'decisions.jsonl',decisions)
    write(RUN/'automatic_summary.json',dict(candidates=len(decisions),automatic_pass=sum(a['automatic_pass'] for a in decisions),pages=pages,
        source_semantic_quality=None,graph_promoted=False))
    print(json.dumps({'candidates':len(decisions),'automatic_pass':sum(a['automatic_pass'] for a in decisions),'pages':pages},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','seal','execute','collect'])
    parser.add_argument('--prompt-key',action='store_true');args=parser.parse_args()
    if args.stage=='execute':execute(args.prompt_key)
    else:globals()[args.stage]()
