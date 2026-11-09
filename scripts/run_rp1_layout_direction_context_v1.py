#!/usr/bin/env python3
"""Generate B/L/D/C on six-page development responses without labels/API."""
import copy
import json
from pathlib import Path
from rp1_offline_contract_v3 import ROOT,BASE,rows,sha,write,object_sha,filter_flags,REGISTRY
from verify_rp1_automatic_contract_v4 import load_module

OUT=BASE/'layout_direction_context_v1'
MODULE=ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/layout_direction_context_v1.py'


def main():
    out=OUT/'development';out.mkdir(parents=True,exist_ok=True)
    if (out/'outputs.jsonl').exists():raise SystemExit('Completed development generation preserved.')
    pages={p['page_key']:p for p in rows(BASE/'adjudication_targeted_v2_1/pilot_sources.jsonl')}
    raw={a['candidate_review_id']:{k:v for k,v in a.items() if k not in ['candidate_review_id','mechanical']}
        for p in rows(BASE/'targeted_api_review_v2_1/arm_masked_review_packets.jsonl') for a in p['assertions']}
    parents=[p for p in rows(BASE/'clause_binding_v1/outputs.jsonl') if p['stage']=='R']
    assert len(raw)==len(parents)==233 and len(pages)==6
    paths=[MODULE,Path(__file__),ROOT/'tests/unit/test_rp1_layout_direction_context_v1.py',ROOT/'docs/research/RP1_LAYOUT_DIRECTION_CONTEXT_V1_PROTOCOL_20261004.md',ROOT/'scripts/rp1_offline_contract_v3.py',BASE/'clause_binding_v1/outputs.jsonl',BASE/'adjudication_targeted_v2_1/pilot_sources.jsonl',BASE/'targeted_api_review_v2_1/arm_masked_review_packets.jsonl']
    write(out/'execution_freeze.json',dict(sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},source_pages=6,inputs=233,new_page_contents_opened=False,new_API_calls=0))
    module=load_module(MODULE);outputs=[];deltas=[]
    for p in parents:
        a=raw[p['candidate_review_id']];page=pages[p['page_key']]
        for stage in ['B','L','D','C']:
            value=copy.deepcopy(p) if stage=='B' else module.refine(a,page,p,REGISTRY,filter_flags,stage)
            value.update(stage=stage,candidate_review_id=p['candidate_review_id'],page_key=p['page_key'],prompt_arm=p['prompt_arm'])
            outputs.append(value)
            if value['payload']!=p['payload'] or value['included']!=p['included']:
                deltas.append(dict(stage=stage,candidate_review_id=p['candidate_review_id'],page_key=p['page_key'],prompt_arm=p['prompt_arm'],before=p['payload'],after=value['payload'],before_included=p['included'],after_included=value['included'],rules=value.get('new_rules',[]),barriers=value['barriers'],flags=value['screen_flags']))
    write(out/'outputs.jsonl',outputs);write(out/'deltas.jsonl',deltas)
    packets={}
    for d in outputs:
        key=(d['page_key'],object_sha(d['payload']))
        packets.setdefault(key,dict(page_key=d['page_key'],payload_sha256=key[1],payload=d['payload']))
    write(out/'review_packets.jsonl',[dict(review_id=f'LD{i:04d}',**p) for i,p in enumerate(packets.values(),1)])
    print(json.dumps(dict(inputs=233,outputs=len(outputs),unique_payloads=len(packets),changed_decisions=len(deltas),new_API_calls=0)))


if __name__=='__main__':main()
