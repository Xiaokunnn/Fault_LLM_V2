#!/usr/bin/env python3
"""Replay 224 cached records and try address selection on two DEVELOPMENT pages.

No hidden retries, held-out claims, source text rewrite, or graph promotion.
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
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from rp1_offline_contract_v3 import BASE, REGISTRY, rows, sha, write
from run_rp1_targeted_v2_1 import payload_bytes, NoRedirect
from research_point_1_graph_evidence.stage02_triple_extraction.native_evidence_selection import (
    catalog, compile_selection, digest, model_input, replay_legacy, system_prompt)

OLD=BASE/'extraction_validation'
OUT=BASE/'source_selection_development'
MODULE=ROOT/'src/research_point_1_graph_evidence/stage02_triple_extraction/native_evidence_selection.py'
ENDPOINT='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'


def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()


def prepare():
    OUT.mkdir(exist_ok=True)
    sources=rows(OLD/'sources.jsonl'); requests=rows(OLD/'requests.jsonl')
    source_map={s['page_key']:s for s in sources}
    decisions=[]; inputs=[OLD/'sources.jsonl',OLD/'requests.jsonl',OLD/'completion.json',
        ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json',MODULE,Path(__file__),
        ROOT/'tests/unit/test_rp1_native_evidence_selection.py',
        ROOT/'src/research_point_1_graph_evidence/stage02_triple_extraction/contextual_extraction.py',
        ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/layout_direction_context_v1.py',
        ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/batch_evidence_repair_v1.py']
    for req in requests:
        path=OLD/'api'/f'{req["request_id"]}.parsed.json';inputs.append(path)
        s=source_map[req['page_key']]
        replay=replay_legacy(json.loads(path.read_text()),s['target'],s['context_pages'])
        decisions += [dict(page_key=s['page_key'],candidate_id=f'{req["request_id"]}:{a["index"]:03d}',**a) for a in replay]
    write(OUT/'legacy_replay.jsonl',decisions)
    counters=dict(candidates=len(decisions),formatting_changed=sum(a.get('formatting_changed',False) for a in decisions),
        both_endpoints_bound=sum(a.get('head_bound',False) and a.get('tail_bound',False) for a in decisions),
        all_quotes_bound=sum(a.get('all_quotes_bound',False) for a in decisions),
        all_quotes_and_both_endpoints_bound=sum(a.get('all_quotes_bound',False) and a.get('head_bound',False) and a.get('tail_bound',False) for a in decisions),
        records_with_unassigned_context_conditions=sum(bool(a.get('unassigned_context_conditions')) for a in decisions),
        ownership_inferred=0,semantic_repair=0,API_calls=0)
    write(OUT/'legacy_summary.json',counters)
    # Previously used pages, selected by known interface stressors BEFORE new
    # responses: shared conditional branches and a genuine two-column procedure.
    selected=[s for s in sources if s['page_key'] in {'MP005:p0108','MP021:p0006'}]
    assert len(selected)==2
    new_requests=[]
    for i,s in enumerate(selected,1):
        data=model_input(s['target'],s['context_pages'])
        payload=dict(model='qwen3.8-max',temperature=0,enable_thinking=False,
            response_format=dict(type='json_object'),max_tokens=16384,
            messages=[dict(role='system',content=system_prompt(REGISTRY)),
                      dict(role='user',content=json.dumps(data,ensure_ascii=False))])
        new_requests.append(dict(request_id=f'N{i:02d}',page_key=s['page_key'],catalog_sha256=data['catalog_sha256'],
            payload_sha256=hashlib.sha256(payload_bytes(payload)).hexdigest(),payload=payload))
    write(OUT/'sources.jsonl',selected);write(OUT/'requests.jsonl',new_requests)
    inputs += [OUT/'legacy_replay.jsonl',OUT/'legacy_summary.json',OUT/'sources.jsonl',OUT/'requests.jsonl']
    write(OUT/'request_freeze.json',dict(prepared_at=now(),purpose='development interface trial, not unseen validation',
        maximum_calls=2,automatic_retries=0,graph_promotion=False,
        method='native token-range selection; source materialization; explicit bidirectional condition ownership',
        candidate_denominator='all returned records; malformed/unresolved outputs retained',
        semantic_quality='structural pass is not source-semantic adequacy or attainment of the 75% goal',
        page_selection='MP005 p108 conditional branches; MP021 p6 two-column procedures; old development pages',
        input_sha256={str(p.relative_to(ROOT)):sha(p) for p in inputs}))
    print(json.dumps(counters,ensure_ascii=False,indent=2))


def verify_inputs():
    freeze=json.loads((OUT/'request_freeze.json').read_text())
    for name,h in freeze['input_sha256'].items():
        assert sha(ROOT/name)==h,name
    return rows(OUT/'requests.jsonl')


def execute(prompt_key=False):
    requests=verify_inputs()
    key=os.environ.get('DASHSCOPE_API_KEY','').strip()
    if not key and prompt_key: key=getpass.getpass('DASHSCOPE_API_KEY (hidden, memory only): ').strip()
    if not key: raise ValueError('API key missing; zero calls')
    run=OUT/'api';run.mkdir(exist_ok=True)
    def worker(item):
        rid=item['request_id'];started=run/f'{rid}.started.json';raw=run/f'{rid}.response.bin'
        if started.exists(): return dict(page_key=item['page_key'],status='existing_attempt_preserved_no_retry')
        write(started,dict(started_at=now(),payload_sha256=item['payload_sha256']))
        begin=time.monotonic();status=None
        try:
            request=urllib.request.Request(ENDPOINT,data=payload_bytes(item['payload']),
                headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Connection':'close'},method='POST')
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=600) as response,raw.open('xb') as stream:
                status=response.status
                while True:
                    chunk=response.read(65536)
                    if not chunk: break
                    stream.write(chunk)
            envelope=json.loads(raw.read_bytes());choice=envelope['choices'][0]
            content=json.loads(choice['message']['content'])
            if choice.get('finish_reason')!='stop': raise ValueError('incomplete_response')
            if not isinstance(content,dict) or not isinstance(content.get('records'),list) or not isinstance(content.get('conditions'),list):
                raise ValueError('invalid_outer_schema')
            write(run/f'{rid}.parsed.json',content)
            write(run/f'{rid}.completed.json',dict(completed_at=now(),http_status=status,
                payload_sha256=item['payload_sha256'],response_sha256=sha(raw),returned_model=envelope.get('model'),
                usage=envelope.get('usage'),finish_reason=choice.get('finish_reason'),
                records=len(content['records']),conditions=len(content['conditions']),elapsed_seconds=time.monotonic()-begin))
            return dict(page_key=item['page_key'],status='archived',records=len(content['records']))
        except Exception as error:
            if isinstance(error,urllib.error.HTTPError):
                status=error.code
                if not raw.exists():
                    with raw.open('xb') as stream:stream.write(error.read())
            write(run/f'{rid}.failed.json',dict(exception_class=type(error).__name__,http_status=status,
                elapsed_seconds=time.monotonic()-begin,no_retry=True))
            return dict(page_key=item['page_key'],status='failed',exception_class=type(error).__name__)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(worker,r) for r in requests]):
            print(json.dumps(future.result(),ensure_ascii=False),flush=True)


def collect():
    requests=verify_inputs();sources={s['page_key']:s for s in rows(OUT/'sources.jsonl')}
    decisions=[];page_results=[]
    for req in requests:
        path=OUT/'api'/f'{req["request_id"]}.parsed.json'
        if not path.exists():
            page_results.append(dict(page_key=req['page_key'],status='no_complete_output',output_count=None));continue
        s=sources[req['page_key']];content=json.loads(path.read_text())
        compiled=compile_selection(content,s['target'],s['context_pages'],REGISTRY)
        decisions += [dict(page_key=s['page_key'],candidate_id=f'{req["request_id"]}:{a["index"]:03d}',**a) for a in compiled]
        page_results.append(dict(page_key=s['page_key'],status='complete',output_count=len(compiled),
            automatic_pass=sum(a['automatic_pass'] for a in compiled),conditions=len(content['conditions']),
            flags=dict(Counter(f for a in compiled for f in a['flags']))))
    write(OUT/'selection_decisions.jsonl',decisions)
    witnesses=[]
    for a in decisions:
        witnesses += a.get('source_witnesses',[]) + a.get('negation_witnesses',[])
        for side in ['head','tail']: witnesses += a.get(side,{}).get('source_spans',[])
        for c in a.get('conditions',[]): witnesses += c['source_spans']+c['binding_spans']
    native={}
    for s in sources.values():
        for u in catalog(s['target'],s['context_pages']).values():native[u['native_id']]=u
    for w in witnesses:
        u=native[w['unit_id']]
        assert u['text'][w['start']:w['end']]==w['text'] and u['bbox']==w['bbox']
    metrics=dict(purpose='two reused development pages, not a new-page quality evaluation',
        pages=page_results,candidates=len(decisions),automatic_pass=sum(a['automatic_pass'] for a in decisions),
        source_span_roundtrips=len(witnesses),roundtrips_passed=True,
        program_generated_verbatim=True,API_calls_started=len(list((OUT/'api').glob('*.started.json'))),
        fully_completed_responses=len(list((OUT/'api').glob('*.completed.json'))),
        semantic_accuracy=None,goal_75_percent_established=False,final_graph_promoted=False)
    write(OUT/'metrics.json',metrics);print(json.dumps(metrics,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','execute','collect'])
    parser.add_argument('--prompt-key',action='store_true');args=parser.parse_args()
    if args.stage=='execute':execute(args.prompt_key)
    else:globals()[args.stage]()
