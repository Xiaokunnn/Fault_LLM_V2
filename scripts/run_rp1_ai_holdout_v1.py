#!/usr/bin/env python3
"""Verify frozen 29-page extraction; --execute makes at most one attempt/page.

No implicit retries or model substitutions. Successful raw responses and partial
failures are preserved. Default is a read-only preflight without network calls.
"""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from prepare_rp1_ai_review_v1 import ROOT, OLD, OUT, rows, sha, save, now, check, verify_hashes
from run_rp1_targeted_v2_1 import payload_bytes, digest, parse_response, request_state, NoRedirect

MATERIALS=OUT/'heldout_materials'
ENDPOINT='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'


def verify():
    check()
    freeze=json.loads((MATERIALS/'reference_and_request_freeze.json').read_text())
    verify_hashes(freeze['sha256'])
    template=json.loads((OLD/'extraction_template.json').read_text())
    requests=rows(MATERIALS/'requests.jsonl')
    pages={p['page_key']:p for p in rows(OUT/'heldout_sources/source_only.jsonl')}
    if len(requests)!=29 or len({r['request_id'] for r in requests})!=29 or {r['page_key'] for r in requests}!=set(pages):
        raise ValueError('Changed request identities')
    for r in requests:
        payload=r['payload']
        if digest(payload_bytes(payload))!=r['payload_sha256']:
            raise ValueError('Changed payload')
        if payload['model']!='qwen3.8-max' or payload['messages'][0]['content']!=template['system_prompt']:
            raise ValueError('Changed extraction model/prompt')
        if {k:v for k,v in payload.items() if k!='messages'}!={k:v for k,v in template.items() if k!='system_prompt'}:
            raise ValueError('Changed generation settings')
        content=payload['messages'][1]['content']
        if digest(content.encode())!=r['shared_input_sha256']:
            raise ValueError('Changed source input')
        source=json.loads(content); p=pages[r['page_key']]
        if any(p.get(k)!=v for k,v in source.items()) or source['page_text_sha256']!=r['source_page_sha256']:
            raise ValueError('Request source mismatch')
    return requests,freeze


def execute():
    requests,freeze=verify()
    key=os.environ.get('DASHSCOPE_API_KEY','').strip()
    if not key:
        return dict(status='blocked_missing_api_key',network_calls_this_invocation=0,api_key_env='DASHSCOPE_API_KEY')
    run=OUT/'heldout_api_run_001';run.mkdir(exist_ok=True)
    manifest=run/'run_manifest.json'
    expected={'runner_sha256':sha(Path(__file__)),'reference_and_request_freeze_sha256':sha(MATERIALS/'reference_and_request_freeze.json'),
        'endpoint':ENDPOINT,'maximum_requests':29,'timeout_seconds':180,'no_automatic_retries':True,
        'api_key_persisted':False,'source_first_AI_reference_frozen':True}
    if manifest.exists():
        if json.loads(manifest.read_text())['config']!=expected:
            raise ValueError('Runner or frozen request set changed')
    else:save(manifest,dict(started_at=now(),config=expected))
    opener=urllib.request.build_opener(NoRedirect())
    returned_model=None;completed=0;network_calls=0
    for item in requests:
        state=request_state(run,item)
        if state is not None:
            if returned_model is not None and returned_model!=state['returned_model']:
                raise ValueError('Saved model mismatch')
            returned_model=state['returned_model'];completed+=1;continue
        save(run/(item['request_id']+'.started.json'),dict(payload_sha256=item['payload_sha256'],page_key=item['page_key'],arm='E1',started_at_unix=time.time()))
        start=time.monotonic();raw_path=run/(item['request_id']+'.response.bin');http_status=None
        try:
            request=urllib.request.Request(ENDPOINT,data=payload_bytes(item['payload']),headers={
                'Authorization':'Bearer '+key,'Content-Type':'application/json','Connection':'close'},method='POST')
            network_calls+=1
            with opener.open(request,timeout=180) as response,raw_path.open('xb') as stream:
                http_status=response.status
                while True:
                    chunk=response.read(65536)
                    if not chunk:break
                    stream.write(chunk)
            content,meta=parse_response(raw_path.read_bytes(),returned_model)
            save(run/(item['request_id']+'.parsed.json'),content)
            save(run/(item['request_id']+'.completed.json'),dict(**meta,payload_sha256=item['payload_sha256'],
                response_sha256=digest(raw_path.read_bytes()),http_status=http_status,elapsed_seconds=time.monotonic()-start))
            returned_model=meta['returned_model'];completed+=1
            print(json.dumps(dict(page_key=item['page_key'],status='archived',assertions=meta['assertion_count']),ensure_ascii=False),flush=True)
        except Exception as error:
            if isinstance(error,urllib.error.HTTPError):
                http_status=error.code
                with raw_path.open('xb') as stream:stream.write(error.read())
            save(run/(item['request_id']+'.failed.json'),dict(exception_class=type(error).__name__,http_status=http_status,
                elapsed_seconds=time.monotonic()-start,resume_policy='stop_no_automatic_retry'))
            raise RuntimeError(item['request_id']+': attempt archived; no retry; '+type(error).__name__) from None
    result=dict(status='extraction_completed_AI_output_review_pending',completed_requests=completed,
        network_calls_this_invocation=network_calls,returned_model=returned_model,AI_metrics='not_computed',human_review=False)
    if not (run/'completion.json').exists():save(run/'completion.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');args=p.parse_args()
    if args.execute:result=execute()
    else:
        requests,freeze=verify()
        result=dict(status='verified_without_network',requests=len(requests),reference_atoms=freeze['reference_count'],
            model='qwen3.8-max',api_key_present=bool(os.environ.get('DASHSCOPE_API_KEY','').strip()),network_calls=0)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['status']=='blocked_missing_api_key':raise SystemExit(2)
