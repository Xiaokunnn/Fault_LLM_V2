#!/usr/bin/env python3
"""One small extraction validation: prepare -> execute -> collect -> review.

No silent retries, failed-page replacement, model substitution or key logging.
All original outputs are retained, including malformed/unresolved candidates.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from rp1_offline_contract_v3 import BASE, rows, sha, write, REGISTRY
from run_rp1_targeted_v2_1 import payload_bytes, NoRedirect
from research_point_1_graph_evidence.stage02_triple_extraction.contextual_extraction import system_prompt, compile_records

OUT=BASE/'extraction_validation'
MODULE=ROOT/'src/research_point_1_graph_evidence/stage02_triple_extraction/contextual_extraction.py'
ENDPOINT='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
DOCS=['MP004','MP005','MP006','MP007','MP015','MP016','MP017','MP018','MP020','MP021','MP022']
SEED='RP1-contextual-extraction-20261013'

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(data):return hashlib.sha256(data).hexdigest()
def priority(key):return digest((SEED+'|'+key).encode())

def page_keys(obj):
    found=set()
    if isinstance(obj,dict):
        if isinstance(obj.get('page_key'),str):found.add(obj['page_key'])
        if isinstance(obj.get('doc_id'),str) and isinstance(obj.get('pdf_page_number'),int):found.add(f'{obj["doc_id"]}:p{obj["pdf_page_number"]:04d}')
        for v in obj.values():found |= page_keys(v)
    elif isinstance(obj,list):
        for v in obj:found |= page_keys(v)
    return found

def classify(p,previous=None):
    text=' '.join(p['page_text'].split());low=text.lower()
    if len(text)<400 or len(text)>10000 or p.get('source_language')!='en':return None
    if len(re.findall(r'\b(the|and|of|to|is|with|for|should|must)\b',low))<12:return None
    if len(re.findall(r'\b(pompe|bomba|pumpe|pumpar|pumppu)\b',low))>3:return None
    header_context=low+' '+(' '.join(previous['page_text'].split()).lower() if previous else '')
    if p['tables'] and re.search(r'\b(cause|causes|reason|reasons)\b',header_context) and re.search(r'\b(fault|trouble|symptom|symptoms|defect|problem)\b',header_context) and re.search(r'\b(remedy|remedies|correction|corrections|solution|solutions|what to do)\b',header_context):return 'fault_table'
    if len(text)<800:return None
    if re.search(r'\b(assembly|disassembly|dismantling|maintenance|lubrication|cleaning)\b',low) and len(re.findall(r'\b(remove|fit|install|replace|clean|lubricate|check|tighten|inspect)\b',low))>=3:return 'maintenance'
    if not p['tables'] and re.search(r'\b(pump|pumps)\b',low) and re.search(r'\b(cause|causes|damage|failure|risk|prevent|cavitation)\b',low):return 'prose'
    return None

def source_input(p):
    fields=['doc_id','pdf_page_number','title','applicability_scope','pump_type','source_url','page_text_sha256']
    return dict(metadata={k:p.get(k) for k in fields},page_text=' '.join(p['page_text'].split()),
        blocks=[dict(unit_id=b['block_id'],text=b['text'],bbox=b.get('bbox')) for b in p['text_blocks'] if b['text'].strip()],
        tables=[dict(table_id=t.get('table_id'),bbox=t.get('bbox'),rows=[dict(row_id=row.get('row_id'),cells=[dict(unit_id=c['cell_id'],text=c['text'],bbox=c.get('bbox')) for c in row['cells'] if c['text'].strip()]) for row in t['rows']]) for t in p['tables']])

def prepare():
    OUT.mkdir(exist_ok=True)
    assert not (OUT/'method.json').exists() and not (OUT/'api').exists()
    deps=[Path(__file__),MODULE,ROOT/'tests/unit/test_rp1_contextual_extraction.py',ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json']
    policy=dict(prepared_at=now(),model='qwen3.8-max',maximum_calls=10,concurrency=2,temperature=0,max_tokens=16384,
        target_qualification_fraction=.75,selection='5 prose + 1 fault-table + 4 maintenance pages; fixed hash priority; max 3 pages/document',
        selection_amendment='Before any API calls: original frame has zero unseen full-header English fault tables. Include native table continuations with previous-page headers; one eligible. Keep all three strata and report separately. Initial infeasible setup retained in logs.',
        exclusion='all source/record review packets, development pages, six-page pilot, 29-page holdout, 8-page followup, 80-record expansion sample',
        seed=SEED,method='shared source context + role-bound triples; exact native evidence, polarity and conditions',
        automatic_pass='schema, primary scope, Chinese labels, exact quotes/endpoint addresses, target-page grounding, explicit context, table-role address checks',
        success='automatic pass plus source-semantic and critical-condition support, measured separately on fixed sample',
        review_sample='uniform SHA priority sample of up to 60 of ALL returned records, including failed records; no resampling',
        quality_gate='75% is a goal, never a source label or permission to omit/rewrite failures',
        previous_page='provided as context only; no new triples from it; continuity must be supported',
        validation='unseen for current source-review-driven optimization, same build documents; not document-disjoint external evaluation',
        retries=0,model_substitution=False,API_key_persisted=False,
        sha256={str(p.relative_to(ROOT)):sha(p) for p in deps},system_prompt=system_prompt(REGISTRY))
    write(OUT/'method.json',policy)
    used=set();exclusions=[]
    for path in BASE.rglob('*.jsonl'):
        if OUT in path.parents:continue
        if path.name in ['source_only.jsonl','pilot_sources.jsonl','development_pages.jsonl','quality_sample.jsonl','record_review_packets.jsonl','page_raw_comparison_packets.jsonl','page_reference_annotations.jsonl','page_reference_v2_1.jsonl']:
            used |= page_keys(rows(path));exclusions.append(path)
    candidates=[];all_pages={};source_files=[]
    for doc in DOCS:
        path=ROOT/f'data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl';source_files.append(path)
        document_pages=rows(path)
        for p in document_pages:
            key=f'{doc}:p{p["pdf_page_number"]:04d}';all_pages[key]=p
        for p in document_pages:
            key=f'{doc}:p{p["pdf_page_number"]:04d}';all_pages[key]=p
            kind=classify(p,all_pages.get(f'{doc}:p{p["pdf_page_number"]-1:04d}'))
            if kind and key not in used:
                assert p['document_split']=='build_train'
                candidates.append((priority(key),key,kind,p))
    chosen=[];counts=Counter()
    for kind,needed in [('fault_table',1),('maintenance',4),('prose',5)]:
        for _,key,tag,p in sorted(candidates):
            if tag!=kind or counts[p['doc_id']]>=3:continue
            chosen.append(dict(page_key=key,stratum=kind,target=p,context_pages=[all_pages[f'{p["doc_id"]}:p{p["pdf_page_number"]-1:04d}']] if f'{p["doc_id"]}:p{p["pdf_page_number"]-1:04d}' in all_pages else []))
            counts[p['doc_id']]+=1
            if sum(x['stratum']==kind for x in chosen)==needed:break
        assert sum(x['stratum']==kind for x in chosen)==needed,kind
    requests=[]
    for index,s in enumerate(chosen,1):
        message=json.dumps(dict(TARGET=source_input(s['target']),PREVIOUS_CONTEXT=[source_input(p) for p in s['context_pages']]),ensure_ascii=False)
        payload=dict(model='qwen3.8-max',temperature=0,enable_thinking=False,response_format=dict(type='json_object'),max_tokens=16384,
            messages=[dict(role='system',content=policy['system_prompt']),dict(role='user',content=message)])
        requests.append(dict(request_id=f'P{index:02d}',page_key=s['page_key'],stratum=s['stratum'],payload=payload,payload_sha256=digest(payload_bytes(payload))))
    write(OUT/'sources.jsonl',chosen);write(OUT/'requests.jsonl',requests)
    write(OUT/'selection.json',dict(excluded_page_keys=sorted(used),eligible_by_stratum=dict(Counter(x[2] for x in candidates)),selected=[dict(page_key=s['page_key'],stratum=s['stratum']) for s in chosen],postselection_replacement=False,
        input_sha256={str(p.relative_to(ROOT)):sha(p) for p in [*source_files,*exclusions]}))
    print(json.dumps(dict(status='prepared',selected=[dict(page_key=s['page_key'],stratum=s['stratum']) for s in chosen],excluded=len(used)),ensure_ascii=False,indent=2))

def seal():
    assert (OUT/'source_inventory.jsonl').exists(),'Source-first coverage inventory must be prepared before API calls'
    write(OUT/'request_freeze.json',dict(frozen_at=now(),API_calls_started=False,
        sha256={str(p.relative_to(ROOT)):sha(p) for p in [OUT/'method.json',OUT/'sources.jsonl',OUT/'selection.json',OUT/'requests.jsonl',OUT/'source_inventory.jsonl',Path(__file__),MODULE]}))

def verify():
    freeze=json.loads((OUT/'request_freeze.json').read_text());method=json.loads((OUT/'method.json').read_text())
    amendment=json.loads((OUT/'compiler_correction.json').read_text()) if (OUT/'compiler_correction.json').exists() else None
    for section in [freeze['sha256'],method['sha256'],json.loads((OUT/'selection.json').read_text())['input_sha256']]:
        for path,h in section.items():
            if amendment and path in amendment['corrected_sha256']:
                assert sha(ROOT/path)==amendment['corrected_sha256'][path],path
                assert amendment['original_sha256'][path]==h,path
            else:assert sha(ROOT/path)==h,path
    requests=rows(OUT/'requests.jsonl');assert len(requests)==10
    for item in requests:assert digest(payload_bytes(item['payload']))==item['payload_sha256']
    return requests

def execute(prompt_key=False):
    requests=verify();key=os.environ.get('DASHSCOPE_API_KEY','').strip()
    if not key and prompt_key:key=getpass.getpass('DASHSCOPE_API_KEY (hidden, memory only): ').strip()
    if not key:raise ValueError('DASHSCOPE_API_KEY unavailable; no network calls')
    run=OUT/'api';run.mkdir(exist_ok=True)
    manifest=dict(endpoint=ENDPOINT,maximum_calls=10,request_freeze_sha256=sha(OUT/'request_freeze.json'),api_key_persisted=False,automatic_retries=0)
    write(run/'manifest.json',manifest)
    def worker(item):
        prefix=run/item['request_id'];completed=Path(str(prefix)+'.completed.json');started=Path(str(prefix)+'.started.json');raw_path=Path(str(prefix)+'.response.bin')
        if completed.exists():
            m=json.loads(completed.read_text());assert m['payload_sha256']==item['payload_sha256'] and m['response_sha256']==sha(raw_path)
            return dict(page_key=item['page_key'],status='cache_reused')
        if started.exists() or raw_path.exists():return dict(page_key=item['page_key'],status='prior_attempt_not_retried')
        write(started,dict(page_key=item['page_key'],payload_sha256=item['payload_sha256'],started_at=now()))
        begin=time.monotonic();status=None
        try:
            request=urllib.request.Request(ENDPOINT,data=payload_bytes(item['payload']),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Connection':'close'},method='POST')
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=180) as response,raw_path.open('xb') as stream:
                status=response.status
                while True:
                    chunk=response.read(65536)
                    if not chunk:break
                    stream.write(chunk)
            response=json.loads(raw_path.read_bytes());choice=response['choices'][0];content=json.loads(choice['message']['content'])
            if choice.get('finish_reason')!='stop':raise ValueError('incomplete finish')
            if not isinstance(content,dict) or not isinstance(content.get('contexts'),list) or not isinstance(content.get('records'),list):raise ValueError('invalid outer schema')
            write(Path(str(prefix)+'.parsed.json'),content)
            meta=dict(payload_sha256=item['payload_sha256'],response_sha256=sha(raw_path),returned_model=response.get('model'),response_id=response.get('id'),usage=response.get('usage'),finish_reason=choice.get('finish_reason'),records=len(content['records']),contexts=len(content['contexts']),elapsed_seconds=time.monotonic()-begin,http_status=status)
            write(completed,meta)
            return dict(page_key=item['page_key'],status='archived',records=len(content['records']))
        except Exception as error:
            if isinstance(error,urllib.error.HTTPError):
                status=error.code
                with raw_path.open('xb') as stream:stream.write(error.read())
            write(Path(str(prefix)+'.failed.json'),dict(exception_class=type(error).__name__,http_status=status,elapsed_seconds=time.monotonic()-begin,no_automatic_retry=True))
            return dict(page_key=item['page_key'],status='failed',exception_class=type(error).__name__,http_status=status)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(worker,item) for item in requests]):print(json.dumps(future.result(),ensure_ascii=False),flush=True)
    print(json.dumps(dict(completed=len(list(run.glob('*.completed.json'))),failed=len(list(run.glob('*.failed.json'))),requests=10)),flush=True)

def collect():
    requests=verify();sources={s['page_key']:s for s in rows(OUT/'sources.jsonl')};all_records=[];page_results=[]
    for item in requests:
        p=OUT/'api'/(item['request_id']+'.parsed.json')
        if not p.exists():page_results.append(dict(page_key=item['page_key'],status='missing_or_failed_response'));continue
        s=sources[item['page_key']];response=json.loads(p.read_text())
        compiled=compile_records(response,s['target'],s['context_pages'],REGISTRY)
        for a in compiled:a.update(candidate_id=f'{item["request_id"]}:{a["index"]:03d}',page_key=item['page_key'],stratum=item['stratum'])
        all_records+=compiled
        page_results.append(dict(page_key=item['page_key'],stratum=item['stratum'],status='compiled',records=len(compiled),automatic_pass=sum(a['automatic_pass'] for a in compiled),coverage_note=response.get('coverage_note'),model=json.loads((OUT/'api'/(item['request_id']+'.completed.json')).read_text()).get('returned_model')))
    write(OUT/'candidates.jsonl',all_records)
    sample=sorted(all_records,key=lambda a:priority(a['candidate_id']))[:60]
    write(OUT/'review_sample.jsonl',[dict(candidate_id=a['candidate_id'],page_key=a['page_key'],raw=a['raw'],context=a.get('context'),inherited_conditions_zh=a.get('inherited_conditions_zh'),applicability_zh=a.get('applicability_zh')) for a in sample])
    summary=dict(status='extracted_structurally_checked_semantic_review_pending',pages=page_results,all_returned_candidates=len(all_records),automatic_pass=sum(a['automatic_pass'] for a in all_records),
        automatic_fraction=sum(a['automatic_pass'] for a in all_records)/len(all_records) if all_records else None,flags=dict(Counter(f for a in all_records for f in a['flags'])),
        unresolved_candidates=sum(bool(a.get('raw',{}).get('unresolved_reason')) for a in all_records if isinstance(a.get('raw'),dict)),
        valid_response_pages=sum(p['status']=='compiled' for p in page_results),semantic_review_sample=len(sample),
        returned_models=sorted({p['model'] for p in page_results if p.get('model')}),qualification='Structural/provenance pass is not verified application success')
    write(OUT/'structural_summary.json',summary)
    write(OUT/'output_freeze.json',dict(frozen_at=now(),sha256={str(p.relative_to(ROOT)):sha(p) for p in [OUT/'candidates.jsonl',OUT/'review_sample.jsonl',OUT/'structural_summary.json']}))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','seal','verify','execute','collect']);parser.add_argument('--prompt-key',action='store_true');args=parser.parse_args()
    if args.command=='execute':execute(args.prompt_key)
    elif args.command=='verify':print(json.dumps(dict(status='PASS',requests=len(verify()))))
    else:globals()[args.command]()
