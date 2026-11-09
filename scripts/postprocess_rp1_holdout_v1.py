#!/usr/bin/env python3
"""Three unchanged postprocessing arms on one frozen extraction batch.

Default verifies the existing 233 development records without rewriting them.
--generate requires all 29 archived responses. No model calls or label access.
"""
import argparse
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path

from prepare_rp1_ai_review_v1 import ROOT, BASE, OUT, rows, sha, save, now
from run_rp1_ai_holdout_v1 import verify
from run_rp1_targeted_v2_1 import request_state
from rp1_offline_contract_v3 import REGISTRY, filter_flags, object_sha, channel, exact_key

MODULE_ROOT=ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation'


def load(name):
    spec=importlib.util.spec_from_file_location(name,MODULE_ROOT/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTEXT=load('automatic_contract_v4_1')
CLAUSE=load('clause_binding_v1')


def branches(raw,page):
    before=object_sha(raw)
    flags=filter_flags(raw,page)
    context=CONTEXT.transform(raw,page,REGISTRY,filter_flags,'roles')
    repair=CLAUSE.refine(raw,page,context,filter_flags,'repair')
    if object_sha(raw)!=before:
        raise ValueError('Runtime changed original response')
    return {
        'raw':dict(payload=copy.deepcopy(raw),included=True,screen_flags=flags),
        'mechanical_filter':dict(payload=copy.deepcopy(raw),included=not flags,screen_flags=flags),
        'source_constrained_repair':repair,
    }


def verify_development():
    # Compare exact saved outputs rather than creating another experimental run.
    pages={p['page_key']:p for p in rows(BASE/'adjudication_targeted_v2_1/pilot_sources.jsonl')}
    saved={r['candidate_review_id']:r for r in rows(BASE/'clause_binding_v1/outputs.jsonl') if r['stage']=='R'}
    checked=0
    for packet in rows(BASE/'targeted_api_review_v2_1/arm_masked_review_packets.jsonl'):
        for item in packet['assertions']:
            raw={k:v for k,v in item.items() if k not in ['candidate_review_id','mechanical']}
            got=branches(raw,pages[packet['page_key']])
            if any(saved[item['candidate_review_id']][k]!=v for k,v in got['source_constrained_repair'].items()):
                raise ValueError('Repair replay differs: '+item['candidate_review_id'])
            if got['raw']['payload']!=raw or got['mechanical_filter']['payload']!=raw:
                raise ValueError('A non-repair arm changed semantics')
            checked+=1
    if checked!=233:
        raise ValueError('Development inventory changed')
    return dict(status='passed',exact_saved_repair_replays=checked,raw_and_filter_payloads_unchanged=True,
        method_tuning=False,new_model_calls=0)


def generate():
    requests,_=verify()
    run=OUT/'heldout_api_run_001'
    completed=[]
    for request in requests:
        state=request_state(run,request)
        if state is None:
            raise ValueError('Not all 29 requests completed; no partial result promoted: '+request['page_key'])
        completed.append((request,json.loads((run/(request['request_id']+'.parsed.json')).read_text())))
    models={json.loads((run/(r['request_id']+'.completed.json')).read_text())['returned_model'] for r,_ in completed}
    if len(models)!=1:
        raise ValueError('Different models in batch')
    preflight=verify_development()
    pages={p['page_key']:p for p in rows(OUT/'heldout_sources/source_only.jsonl')}
    target=OUT/'holdout_comparison_v1'
    target.mkdir(exist_ok=False)
    deps=[Path(__file__),ROOT/'scripts/run_rp1_ai_holdout_v1.py',ROOT/'scripts/rp1_offline_contract_v3.py',
        MODULE_ROOT/'automatic_contract_v4_1.py',MODULE_ROOT/'clause_binding_v1.py',
        OUT/'ai_method_freeze.json',OUT/'heldout_materials/reference_and_request_freeze.json']
    deps+=list(run.glob('*.parsed.json'))+list(run.glob('*.response.bin'))+list(run.glob('*.completed.json'))
    save(target/'generation_freeze.json',dict(created_at=now(),sha256={str(p.relative_to(ROOT)):sha(p) for p in deps},
        development_replay=preflight,labels_or_references_used_for_transformation=False))
    outputs=[];sidecars=[]
    for request,parsed in completed:
        key=request['page_key'];page=pages[key]
        sidecars.append(dict(page_key=key,auxiliary=parsed['auxiliary'],unresolved=parsed['unresolved']))
        for ordinal,raw in enumerate(parsed['assertions'],1):
            cid=f'{key}:H29:{ordinal:03d}'
            for arm,result in branches(raw,page).items():
                outputs.append(dict(candidate_id=cid,page_key=key,arm=arm,original_sha256=object_sha(raw),
                    source_page_sha256=page['page_text_sha256'],**result))
    save(target/'outputs.jsonl',outputs)
    save(target/'extraction_sidecars.jsonl',sidecars)

    # Each identical page/payload is reviewed once, even if it appears in several
    # arms. Arm identity/acceptance are absent from the review packet.
    unique={}
    for d in outputs:
        key=(d['page_key'],object_sha(d['payload']))
        unique.setdefault(key,dict(page_key=d['page_key'],payload=d['payload'],payload_sha256=key[1],
            source_page_sha256=d['source_page_sha256']))
    packets=[];identity={}
    for i,(key,p) in enumerate(sorted(unique.items()),1):
        review_id=f'HQR{i:04d}';identity[key]=review_id
        packets.append(dict(review_id=review_id,**p,verdict=None,reason=None,reference_matches=None))
    mapping=[dict(candidate_id=d['candidate_id'],arm=d['arm'],included=d['included'],
        review_id=identity[(d['page_key'],object_sha(d['payload']))]) for d in outputs]
    save(target/'quality_review_packets.jsonl',packets)
    save(target/'private_arm_mapping.jsonl',mapping)
    counts=[]
    for key in pages:
        for arm in ['raw','mechanical_filter','source_constrained_repair']:
            group=[d for d in outputs if d['page_key']==key and d['arm']==arm]
            retained=[d for d in group if d['included']]
            counts.append(dict(page_key=key,arm=arm,inputs=len(group),retained=len(retained),
                retained_exact_unique=len({exact_key(d['payload']) for d in retained}),
                retained_channels=dict(Counter(channel(d['payload']) for d in retained))))
    save(target/'mechanical_counts.jsonl',counts)
    summary=dict(status='postprocessing_completed_quality_review_pending',pages=29,
        original_assertions=len(outputs)//3,decisions=len(outputs),unique_review_payloads=len(packets),
        returned_model=next(iter(models)),quality_and_coverage_metrics='pending_source_review_and_matching',
        additional_API_calls=0,outputs_sha256=sha(target/'outputs.jsonl'))
    save(target/'completion.json',summary)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--generate',action='store_true')
    args=p.parse_args()
    print(json.dumps(generate() if args.generate else verify_development(),ensure_ascii=False,indent=2))
