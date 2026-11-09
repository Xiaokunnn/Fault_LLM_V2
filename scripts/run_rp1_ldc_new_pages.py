#!/usr/bin/env python3
"""Execute the eight frozen new-page requests, with immutable response caching."""
import argparse
import getpass
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from rp1_offline_contract_v3 import ROOT, BASE, rows, sha, write
from run_rp1_targeted_v2_1 import payload_bytes, digest, parse_response, request_state, NoRedirect

OUT=BASE/'layout_direction_context_v1'
PAGE=OUT/'new_pages'
ENDPOINT='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'

def verify():
    for p in [OUT/'method_freeze.json',PAGE/'reference_and_request_freeze.json']:
        for name,h in json.loads(p.read_text())['sha256'].items():
            if sha(ROOT/name)!=h:raise ValueError('Frozen dependency changed: '+name)
    requests=rows(PAGE/'requests.jsonl')
    template=json.loads((BASE/'independent_review_v1/extraction_template.json').read_text())
    pages={p['page_key']:p for p in rows(PAGE/'source_only.jsonl')}
    assert len(requests)==len(pages)==8
    assert {r['page_key'] for r in requests}==set(pages)
    assert len({r['request_id'] for r in requests})==8
    for r in requests:
        payload=r['payload'];p=pages[r['page_key']]
        assert digest(payload_bytes(payload))==r['payload_sha256']
        assert {k:v for k,v in payload.items() if k!='messages'}=={k:v for k,v in template.items() if k!='system_prompt'}
        assert payload['messages'][0]==dict(role='system',content=template['system_prompt'])
        content=payload['messages'][1]['content']
        assert digest(content.encode())==r['shared_input_sha256']
        assert all(p.get(k)==v for k,v in json.loads(content).items())
        assert digest(p['page_text'].encode())==r['source_page_sha256']
    return requests

def execute(key):
    requests=verify()
    if not key:raise ValueError('API key absent; no network calls')
    run=OUT/'api_run_001';run.mkdir(exist_ok=True)
    config=dict(runner_sha256=sha(Path(__file__)),freeze_sha256=sha(PAGE/'reference_and_request_freeze.json'),
        endpoint=ENDPOINT,maximum_requests=8,timeout_seconds=180,no_automatic_retries=True,api_key_persisted=False)
    if (run/'run_manifest.json').exists():assert json.loads((run/'run_manifest.json').read_text())['config']==config
    else:write(run/'run_manifest.json',dict(started_at_unix=time.time(),config=config))
    opener=urllib.request.build_opener(NoRedirect());returned=None;calls=0
    for item in requests:
        state=request_state(run,item)
        if state is not None:
            assert returned is None or state['returned_model']==returned
            returned=state['returned_model'];continue
        write(run/(item['request_id']+'.started.json'),dict(payload_sha256=item['payload_sha256'],page_key=item['page_key'],arm='E1',started_at_unix=time.time()))
        start=time.monotonic();raw=run/(item['request_id']+'.response.bin');status=None
        try:
            req=urllib.request.Request(ENDPOINT,data=payload_bytes(item['payload']),headers={
                'Authorization':'Bearer '+key,'Content-Type':'application/json','Connection':'close'},method='POST')
            calls+=1
            with opener.open(req,timeout=180) as response,raw.open('xb') as stream:
                status=response.status
                while True:
                    chunk=response.read(65536)
                    if not chunk:break
                    stream.write(chunk)
            content,meta=parse_response(raw.read_bytes(),returned)
            write(run/(item['request_id']+'.parsed.json'),content)
            write(run/(item['request_id']+'.completed.json'),dict(**meta,payload_sha256=item['payload_sha256'],
                response_sha256=sha(raw),http_status=status,elapsed_seconds=time.monotonic()-start))
            returned=meta['returned_model']
            print(json.dumps(dict(page_key=item['page_key'],assertions=meta['assertion_count'],status='archived'),ensure_ascii=False),flush=True)
        except Exception as error:
            if isinstance(error,urllib.error.HTTPError):
                status=error.code
                with raw.open('xb') as stream:stream.write(error.read())
            write(run/(item['request_id']+'.failed.json'),dict(exception_class=type(error).__name__,http_status=status,
                elapsed_seconds=time.monotonic()-start,resume_policy='stop_no_automatic_retry'))
            raise RuntimeError(item['request_id']+': archived without retry; '+type(error).__name__) from None
    result=dict(status='extraction_completed_review_pending',requests=8,network_calls_this_invocation=calls,returned_model=returned)
    if not (run/'completion.json').exists():write(run/'completion.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--prompt-key',action='store_true');args=p.parse_args()
    verify()
    if args.execute:
        key=os.environ.get('DASHSCOPE_API_KEY','').strip()
        if not key and args.prompt_key:key=getpass.getpass('DASHSCOPE_API_KEY (hidden, memory only): ').strip()
        print(json.dumps(execute(key),ensure_ascii=False,indent=2))
    else:print(json.dumps(dict(status='verified_without_network',requests=8,reference_atoms=45)))
