"""Optional, explicitly authorized LOCAL-machine review. Never called by study.

Default/check-only paths do not import a networking module. This machine is
hard-denied; move permitted packets to an authorized desktop to use this tool.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time

PROMPT_VERSION='document_gap_source_review_v1'
SYSTEM=('Review the supplied research hypothesis and source only. Distinguish '
        'explicit source facts, conditional analogies, role/scope conflicts and '
        'unresolved cases. A failed search is not document absence. You are an '
        'AI reviewer, not an expert Gold annotator. Return one JSON object with '
        'assessment, source_ids, required_conditions, rationale and uncertainty.')
DENIED_HOSTS={'hengshan10'}

def digest(x):return hashlib.sha256(x).hexdigest()

def check_environment(enabled,confirmed_local,permission):
    if not enabled:raise RuntimeError('External LLM is OFF; zero requests')
    host=socket.gethostname().split('.')[0].lower()
    if host in DENIED_HOSTS:raise RuntimeError('Known model-server host is blocked; zero requests')
    if any(os.getenv(k) for k in ['SSH_CONNECTION','SSH_CLIENT','SSH_TTY','SLURM_JOB_ID']):raise RuntimeError('Remote/job environment is blocked; zero requests')
    if not confirmed_local:raise RuntimeError('Explicit local-machine confirmation is required; zero requests')
    if permission.get('local_hostname')!=host:raise RuntimeError('Permission is not bound to this local machine; zero requests')
    if permission.get('enabled') is not True or not permission.get('user_authorization_reference'):raise RuntimeError('Missing explicit export authorization; zero requests')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--enable-external-llm',action='store_true')
    ap.add_argument('--confirm-local-machine',action='store_true')
    ap.add_argument('--check-only',action='store_true')
    ap.add_argument('--permission',type=Path)
    ap.add_argument('--packets',type=Path)
    ap.add_argument('--cache-dir',type=Path,default=Path(__file__).resolve().parent/'cache')
    ap.add_argument('--max-requests',type=int,default=3)
    ap.add_argument('--retries',type=int,default=1)
    args=ap.parse_args()
    permission=json.loads(args.permission.read_text()) if args.permission else {}
    try:check_environment(args.enable_external_llm,args.confirm_local_machine,permission)
    except RuntimeError as e:
        if args.check_only:print(json.dumps(dict(allowed=False,network_calls=0,reason=str(e))));return
        raise SystemExit(str(e))
    if args.check_only:print(json.dumps(dict(allowed=True,network_calls=0,reason='Check only; payload and endpoint checks still required')));return
    if not args.packets:raise SystemExit('Missing authorized packets; zero requests')
    if not 1<=args.max_requests<=20 or not 0<=args.retries<=2:raise SystemExit('Request/retry cap exceeded; zero requests')
    # Pin one HTTPS endpoint and bind every input ID to an exact payload hash.
    endpoint=permission.get('endpoint','')
    from urllib.parse import urlparse
    parsed=urlparse(endpoint)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:raise SystemExit('Authorized HTTPS endpoint required; zero requests')
    model=permission.get('model');env=permission.get('api_key_env')
    if not model or not env or not env.replace('_','').isalnum():raise SystemExit('Model and key environment-variable name required; zero requests')
    packets=[json.loads(s) for s in args.packets.read_text().splitlines() if s.strip()]
    for p in packets:
        data=json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        allowed=permission.get('allowed_inputs',{}).get(p['input_id'])
        if allowed!=digest(data):raise SystemExit('Packet is not explicitly authorized: '+p['input_id'])
        if p.get('contains_source_text') and permission.get('allow_source_text_export') is not True:raise SystemExit('Source text export not authorized; zero requests')
    key=os.environ.get(env)
    if not key:raise SystemExit('API key environment variable is unset; zero requests')
    # No network dependency is imported before all guards and payload checks.
    import urllib.request
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*a,**kw):raise RuntimeError('Redirect refused')
    opener=urllib.request.build_opener(NoRedirect)
    args.cache_dir.mkdir(parents=True,exist_ok=True)
    calls=0
    for p in packets:
        raw=json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        fp=digest(json.dumps([model,PROMPT_VERSION,endpoint,raw],ensure_ascii=False).encode())
        cached=args.cache_dir/(fp+'.json')
        if cached.exists():print('cache',p['input_id'],fp);continue
        meta=dict(input_id=p['input_id'],model=model,prompt_version=PROMPT_VERSION,input_sha256=digest(raw.encode()),endpoint_host=parsed.hostname,evaluator='external AI, not expert Gold')
        for attempt in range(args.retries+1):
            if calls>=args.max_requests:print('request cap reached');return
            calls+=1
            payload=dict(model=model,messages=[dict(role='system',content=SYSTEM),dict(role='user',content=raw)],temperature=0,max_tokens=1200)
            req=urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            try:
                with opener.open(req,timeout=90) as response:result=json.loads(response.read())
                # Only the body is persisted. Headers/secrets never enter logs.
                record=dict(**meta,status='complete',attempt=attempt+1,response=result)
                with cached.open('x') as f:json.dump(record,f,ensure_ascii=False,indent=2)
                print('complete',p['input_id'],fp);break
            except Exception as e:
                # Error strings may contain server content, so retain class only.
                error=dict(**meta,status='failed',attempt=attempt+1,error_class=type(e).__name__)
                with (args.cache_dir/(fp+f'.attempt{attempt+1}.error.json')).open('x') as f:json.dump(error,f,ensure_ascii=False,indent=2)
                print('failed',p['input_id'],type(e).__name__)
                if attempt<args.retries:time.sleep(1)


if __name__=='__main__':main()
