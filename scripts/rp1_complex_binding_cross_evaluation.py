"""Output-retention auditor with synthetic empty/correct/corrupt controls.

The first auditor confused source support with output retention. Its original
responses remain in evaluation/ and are excluded, never relabelled. This
contract adds output citations; it does not change generation methods.
"""
from run_rp1_complex_binding_baselines import *

AUDITOR=JUDGE_SYSTEM+'''
CRITICAL TASK: Score what ANONYMOUS_OUTPUT actually RETAINS relative to FOCUS
and SOURCE. Do NOT score whether the focus quotation is supported by SOURCE:
it was already copied from SOURCE. The subject of EVERY grade is OUTPUT.
If OUTPUT is empty, all applicable retention dimensions are N, never S.
An absent extraction cannot be supported simply because SOURCE says it.
For each assessment ADD output_refs (e.g. ["triples:1", "auxiliary:2"])
and output_quote (verbatim text actually present in those OUTPUT objects).
Allowed references: triples, bindings, auxiliary, each 1-based. Rejected or
unresolved suggestions are NOT successfully retained knowledge. Source alone
is never an output reference. A complete S requires output evidence for ALL
essential meanings, not inference of missing clauses from SOURCE. Incomplete
but accurate output is P; incorrect or missing meaning is N; NA only when that
dimension is not applicable to the source focus. channel must be main only if
actual triples support the focus, auxiliary if only auxiliary supports it, none
if neither. explicit_binding separately concerns machine-readable linkage.
Keep source evidence_quote separate from output_quote. For relation_verdicts,
judge actual output head/type/relation/tail AND complete conditions/polarity,
not just whether its quoted sentence occurs somewhere in SOURCE.
'''

def check(value,body):
    expected={f['focus_id'] for f in body['focus']};out=body['anonymous_output']
    if len(value['assessments'])!=len(expected) or {a['focus_id'] for a in value['assessments']}!=expected:raise ValueError('incomplete_focus')
    n=len(out.get('triples',[]));vv=value['relation_verdicts']
    if len(vv)!=n or {v['index'] for v in vv}!=set(range(1,n+1)):raise ValueError('incomplete_relations')
    for v in vv:
        if v['verdict'] not in ['S','N','U']:raise ValueError('bad_verdict')
    for a in value['assessments']:
        if any(a.get(d) not in ['S','P','N','U','NA'] for d in DIMENSIONS+['explicit_binding']):raise ValueError('bad_grade')
        refs=a.get('output_refs',[]);parts=[]
        for ref in refs:
            kind,i=ref.split(':');i=int(i)
            if kind not in ['triples','bindings','auxiliary'] or not 1<=i<=len(out.get(kind,[])):raise ValueError('invalid_output_reference')
            parts+=list(strings(out[kind][i-1]))
        if any(a[d] in ['S','P'] for d in DIMENSIONS+['explicit_binding']):
            q=a.get('output_quote','')
            if not refs or not q or not any(norm(q) in norm(s) for s in parts):raise ValueError('positive_grade_without_actual_output_quote')
        if a['channel']=='main' and not any(r.startswith('triples:') for r in refs):raise ValueError('main_without_output_relation')
        if a['channel']=='auxiliary' and not any(r.startswith('auxiliary:') for r in refs):raise ValueError('auxiliary_without_output')

def request(body):
    return dict(model=JUDGE,stream=False,think=False,format='json',messages=[dict(role='system',content=AUDITOR),dict(role='user',content=canonical(body))],options=dict(temperature=0,seed=20261110,num_predict=4096,num_ctx=32768))

def preflight(out):
    d=out/'cross_evaluation';save(d/'contract.json',dict(prompt=AUDITOR,sha256=digest(AUDITOR),script_sha256=sha(Path(__file__)),correction='source support is not output retention; positive grades require real output citations',generation_changed=False,old_reviews_excluded='evaluation/'))
    source='Inspect the pump before restart. Never run the pump dry.'
    cases={'empty':{'triples':[]},'correct':{'triples':[{'head_surface':'pump','relation':'inspected_by','tail_surface':'Inspect the pump before restart.','evidence_text':source},{'head_surface':'pump','relation':'operates_under','tail_surface':'Never run the pump dry.','evidence_text':source}]},'corrupt':{'triples':[{'head_surface':'pump','relation':'inspected_by','tail_surface':'Inspect the pump AFTER restart.'},{'head_surface':'pump','relation':'operates_under','tail_surface':'Always run the pump dry.'}]}}
    results=[]
    for case,output in cases.items():
        body=dict(source=source,focus=[dict(focus_id='synthetic',source_quotes=[source])],anonymous_output=output)
        p=d/'preflight'/f'{case}.json'
        if p.exists():raw=read(p)
        else:raw=ollama('/api/chat',request(body),1200);save(p,raw)
        v=strict_parse(raw['message']['content']);check(v,body);a=v['assessments'][0]
        if case=='empty' and any(a[k] in ['S','P'] for k in DIMENSIONS):raise ValueError('empty output falsely rewarded')
        if case=='correct' and a['literal_complete']!='S':raise ValueError('positive control not recovered')
        if case=='corrupt' and a['literal_complete']=='S':raise ValueError('corrupt control falsely rewarded')
        results.append(dict(case=case,assessment=a))
    save(d/'preflight_passed.json',dict(results=results,synthetic_only=True,not_semantic_accuracy_certificate=True))

def run(out):
    verify(out);preflight(out)
    d=out/'cross_evaluation';identity=read(out/'resources.json')['judge']['digest']
    tags=json.load(urllib.request.urlopen(JUDGE_URL+'/api/tags'))
    if next(x['digest'] for x in tags['models'] if x['name']==JUDGE)!=identity:raise ValueError('model changed')
    sources={s['page_key']:s for s in read(out/'sources.jsonl')};targets=read(out/'targets.jsonl');ind={s['page_key']:s for s in read(out/'independent/sources.jsonl')}
    completed=set();last=time.monotonic()
    while True:
        for trial in read(out/'trials.jsonl'):
            p=out/'runs'/trial['trial_id']/'result.json'
            if not p.exists() or trial['trial_id'] in completed:continue
            result=read(p);key=trial['page_key']
            focus=[dict(focus_id=t['target_id'],source_quotes=t['anchors']) for t in targets if t['page_key']==key] if trial['split']=='development' else [dict(focus_id=ind[key]['sample_id'],source_quotes=[ind[key]['focus_quote']])]
            for channel,output in [('raw',result['output'] or {'triples':[]}),('validated',validated_view(result))]:
                body=dict(source=source_view(sources[key]['target']),focus=focus,anonymous_output=output)
                rid='E'+digest([digest(AUDITOR),body])[:24];p=d/f'{rid}.json'
                save(d/'inputs'/f'{rid}.json',dict(review_id=rid,body=body))
                save(d/'mapping'/f'{trial["trial_id"]}_{channel}.json',dict(**trial,channel=channel,review_id=rid))
                if p.exists():continue
                started=d/f'{rid}.started.json'
                if started.exists():raise ValueError('Uncertain attempt; no retry '+rid)
                payload=request(body);save(started,dict(request_sha256=digest(payload),model_digest=identity))
                try:
                    raw=ollama('/api/chat',payload,1200);save(d/f'{rid}.raw.json',raw)
                    if raw.get('done_reason')!='stop':raise ValueError('review_truncated')
                    v=strict_parse(raw['message']['content']);check(v,body)
                    save(p,dict(status='complete_AI_cross_evaluation',assessment=v,judge_digest=identity,usage={k:raw.get(k) for k in ['prompt_eval_count','eval_count','total_duration']},human_Gold=False))
                except Exception as e:save(p,dict(status='unassessed_failure',failure=type(e).__name__+': '+str(e),human_Gold=False))
                print('reviewed',rid,flush=True)
            completed.add(trial['trial_id']);last=time.monotonic()
        if (out/'generation_complete.json').exists() and len(completed)==len(read(out/'trials.jsonl')):
            save(d/'complete.json',dict(trials=len(completed),human_Gold=False));return
        if time.monotonic()-last>3600:raise RuntimeError('no generation progress for one hour')
        time.sleep(10)

if __name__=='__main__':run(OUT)
