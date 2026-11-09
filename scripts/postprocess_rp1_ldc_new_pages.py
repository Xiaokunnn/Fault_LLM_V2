#!/usr/bin/env python3
"""Apply frozen B/L/D/C to one cached E1 batch; raw is a descriptive audit arm."""
import copy
import json
from pathlib import Path
from rp1_offline_contract_v3 import ROOT, BASE, rows, sha, write, object_sha, REGISTRY, filter_flags, channel
from postprocess_rp1_holdout_v1 import branches, load
from run_rp1_ldc_new_pages import verify, OUT, PAGE
from run_rp1_targeted_v2_1 import request_state

def main():
    requests=verify();run=OUT/'api_run_001';target=OUT/'new_page_comparison'
    completed=[]
    for r in requests:
        state=request_state(run,r)
        if state is None:raise ValueError('Pending cached response: '+r['request_id'])
        completed.append((r,json.loads((run/(r['request_id']+'.parsed.json')).read_text())))
    target.mkdir(exist_ok=False)
    module=load('layout_direction_context_v1')
    pages={p['page_key']:p for p in rows(PAGE/'source_only.jsonl')}
    deps=[Path(__file__),ROOT/'scripts/run_rp1_ldc_new_pages.py',OUT/'method_freeze.json',PAGE/'reference_and_request_freeze.json']
    deps+=list(run.glob('*.parsed.json'))+list(run.glob('*.response.bin'))+list(run.glob('*.completed.json'))
    write(target/'execution_freeze.json',dict(sha256={str(p.relative_to(ROOT)):sha(p) for p in deps},
        runtime_reference_access=False,stages=['B','L','D','C'],raw_role='descriptive loss audit'))
    outputs=[];sidecars=[];deltas=[]
    for r,parsed in completed:
        p=pages[r['page_key']]
        sidecars.append(dict(page_key=r['page_key'],auxiliary=parsed['auxiliary'],unresolved=parsed['unresolved']))
        for i,raw in enumerate(parsed['assertions'],1):
            cid=f'{r["page_key"]}:LDC:{i:03d}'
            parent=branches(raw,p)['source_constrained_repair']
            for stage in ['raw','B','L','D','C']:
                value=dict(payload=copy.deepcopy(raw),included=True,screen_flags=filter_flags(raw,p)) if stage=='raw' else copy.deepcopy(parent) if stage=='B' else module.refine(raw,p,parent,REGISTRY,filter_flags,stage)
                outputs.append(dict(candidate_id=cid,page_key=r['page_key'],stage=stage,original_sha256=object_sha(raw),**value))
                if stage in ['L','D','C'] and (value['payload']!=parent['payload'] or value['included']!=parent['included']):
                    deltas.append(dict(candidate_id=cid,page_key=r['page_key'],stage=stage,
                        before=parent['payload'],after=value['payload'],before_included=parent['included'],after_included=value['included'],
                        new_rules=value['new_rules'],flags=value['screen_flags'],barriers=value['barriers']))
    unique={}
    for d in outputs:
        k=(d['page_key'],object_sha(d['payload']))
        unique.setdefault(k,dict(page_key=k[0],payload_sha256=k[1],payload=d['payload']))
    packets=[dict(review_id=f'LQ{i:04d}',**p) for i,p in enumerate(sorted(unique.values(),key=lambda p:(p['page_key'],p['payload_sha256'])),1)]
    write(target/'outputs.jsonl',outputs);write(target/'deltas.jsonl',deltas)
    write(target/'review_packets.jsonl',packets);write(target/'extraction_sidecars.jsonl',sidecars)
    summary=dict(original_assertions=len(outputs)//5,decision_rows=len(outputs),unique_review_payloads=len(packets),changed_decisions=len(deltas),quality_metrics='pending source review')
    write(target/'generation_summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
