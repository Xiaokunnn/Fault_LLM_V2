#!/usr/bin/env python3
"""Schedule the frozen, anonymous review contract as generation completes.

The final evaluate command reuses the same content-addressed review files.
No extra generation, retries, prompts, grading rules or model tuning.
"""
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_rp1_complex_binding_baselines import *

def run(out):
    verify(out)
    resources=read(out/'resources.json');actual=ollama('/api/show',{'model':JUDGE})
    tags=json.load(urllib.request.urlopen(JUDGE_URL+'/api/tags'))
    identity=next(x for x in tags['models'] if x['name']==JUDGE)['digest']
    if identity!=resources['judge']['digest']:raise ValueError('judge changed')
    save(out/'evaluation/scheduler.json',dict(script_sha256=sha(Path(__file__)),contract='identical to frozen evaluate; content-addressed deduplication',concurrent_gpu_workloads=True,latency_not_isolated_hardware_benchmark=True))
    sources={s['page_key']:s for s in read(out/'sources.jsonl')};targets=read(out/'targets.jsonl');ind={s['page_key']:s for s in read(out/'independent/sources.jsonl')}
    completed=set();last_progress=time.monotonic()
    while True:
        available=[]
        for trial in read(out/'trials.jsonl'):
            p=out/'runs'/trial['trial_id']/'result.json'
            if p.exists() and trial['trial_id'] not in completed:available.append(trial)
        for trial in available:
            r=read(out/'runs'/trial['trial_id']/'result.json');key=trial['page_key']
            focus=[dict(focus_id=t['target_id'],source_quotes=t['anchors']) for t in targets if t['page_key']==key] if trial['split']=='development' else [dict(focus_id=ind[key]['sample_id'],source_quotes=[ind[key]['focus_quote']])]
            for channel,value in [('raw',r['output'] if r['output'] is not None else {'triples':[],'unresolved':['No complete model JSON was returned.']}),('validated',validated_view(r))]:
                body=dict(source=source_view(sources[key]['target']),focus=focus,anonymous_output=value)
                rid='E'+digest(body)[:24];p=out/'evaluation'/f'{rid}.json'
                save(out/'evaluation/scheduled_inputs'/f'{rid}.json',dict(review_id=rid,body=body))
                save(out/'evaluation/scheduling_map'/f'{trial["trial_id"]}_{channel}.json',dict(trial_id=trial['trial_id'],channel=channel,review_id=rid))
                if p.exists():continue
                start=out/'evaluation'/f'{rid}.started.json'
                if start.exists():raise ValueError('Uncertain review; do not retry '+rid)
                payload=dict(model=JUDGE,stream=False,think=False,format='json',messages=[dict(role='system',content=JUDGE_SYSTEM),dict(role='user',content=canonical(body))],options=dict(temperature=0,seed=20261110,num_predict=4096,num_ctx=32768))
                save(start,dict(request_sha256=digest(payload),judge_digest=identity))
                try:
                    raw=ollama('/api/chat',payload,timeout=1200);save(out/'evaluation'/f'{rid}.raw.json',raw)
                    if not raw.get('done') or raw.get('done_reason')!='stop':raise ValueError('judge_truncated')
                    v=strict_parse(raw['message']['content']);expected={x['focus_id'] for x in focus}
                    if {x['focus_id'] for x in v['assessments']}!=expected:raise ValueError('incomplete_focus_assessment')
                    n=len(value.get('triples',[]));vv=v['relation_verdicts']
                    if len(vv)!=n or {x['index'] for x in vv}!=set(range(1,n+1)):raise ValueError('incomplete_relation_audit')
                    for a in v['assessments']:
                        if any(a.get(d) not in ['S','P','N','U','NA'] for d in DIMENSIONS+['explicit_binding']):raise ValueError('bad_grade')
                    save(p,dict(status='complete_AI_cross_evaluation',assessment=v,usage={k:raw.get(k) for k in ['prompt_eval_count','eval_count','total_duration']},judge_alias=JUDGE,judge_digest=identity,human_Gold=False))
                except Exception as e:
                    save(p,dict(status='unassessed_failure',failure=type(e).__name__+': '+str(e),human_Gold=False))
                print('reviewed',rid,flush=True)
            completed.add(trial['trial_id']);last_progress=time.monotonic()
        if (out/'generation_complete.json').exists() and len(completed)==len(read(out/'trials.jsonl')):
            evaluation(out);return
        if time.monotonic()-last_progress>3600:raise RuntimeError('No generation progress for one hour; preserve and inspect, no automatic retry')
        time.sleep(10)

if __name__=='__main__':run(OUT)
