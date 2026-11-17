#!/usr/bin/env python3
"""Offline parser equivalence replay; never call or alter a generator.

Use the EXISTING frozen client decoder, including its Markdown fence handling.
The model text, seeds, token usage and underlying semantic rules stay fixed.
Strict-JSON frontend decisions remain preserved in formal/runs/.
"""
import shutil
from run_rp1_complex_binding_baselines import *
from run_rp1_complex_binding_prompt_baselines import FORMAL
from research_point_1_graph_evidence.stage02_triple_extraction.bailian_client import _decode_json_content
from jsonschema import Draft202012Validator

ALIGNED=FORMAL/'pipeline_aligned'

def prepare():
    verify(FORMAL)
    for name in ['sources.jsonl','targets.jsonl','trials.jsonl','methods.json','output_schema.json','resources.json','runtime_environment.json']:
        save(ALIGNED/name,read(FORMAL/name))
    for directory in ['inputs','trace','independent']:
        for p in (FORMAL/directory).rglob('*'):
            if p.is_file():save(ALIGNED/p.relative_to(FORMAL),p.read_text())
    cfg=read(FORMAL/'protocol.json');cfg['response_decoder']='existing bailian_client._decode_json_content; offline exact-response replay, not new generation or semantic correction';cfg['source_generation_directory']=str(FORMAL.relative_to(ROOT));save(ALIGNED/'protocol.json',cfg)
    f=read(FORMAL/'freeze.json');paths=[p for p in ALIGNED.rglob('*') if p.is_file() and p.name!='freeze.json']
    code=[ROOT/p for p in f['sha256'] if p.startswith(('scripts/','src/','tests/'))]+[Path(__file__)]
    save(ALIGNED/'freeze.json',dict(git_head=f['git_head'],sha256={str(p.relative_to(ROOT)):sha(p) for p in paths+code},old_result_sha256=f['old_result_sha256'],teacher_sha256=f['teacher_sha256'],generator_reused_not_rerun=True))

def run():
    if not (ALIGNED/'freeze.json').exists():prepare()
    verify(ALIGNED);cfg=read(ALIGNED/'protocol.json');schema=read(ALIGNED/'output_schema.json')
    pages={s['page_key']:s['target'] for s in read(ALIGNED/'sources.jsonl')};screen=screen_from_archive(Archive());trials=read(ALIGNED/'trials.jsonl');done=set();last=time.monotonic()
    while True:
        for t in trials:
            src=FORMAL/'runs'/t['trial_id']/'result.json';dest=ALIGNED/'runs'/t['trial_id']/'result.json'
            if dest.exists():done.add(t['trial_id']);continue
            if not src.exists():continue
            original=read(src);result=copy.deepcopy(original);result['interface_alignment']=dict(decoder='existing _decode_json_content',source_result_sha256=sha(src),new_generator_calls=0,meaning_text_not_edited=True)
            stages=original['stages']
            if stages and stages[-1]['finish_reason']=='stop':
                response=FORMAL/'runs'/t['trial_id']/f'stage{len(stages)}.response.json';content=read(response)['content'];parsed=None;validation=[];errors=[];failure=None
                try:
                    parsed=_decode_json_content(content);errors=[e.message for e in Draft202012Validator(schema).iter_errors(parsed)]
                    if len(parsed.get('triples',[]))>cfg['candidate_cap']:raise ValueError('candidate_cap_exceeded_no_drop')
                    for i,r in enumerate(parsed.get('triples',[]),1):
                        try:
                            normalized=normalize_model_candidate(r,page=pages[t['page_key']]);adapter={**normalized,**{k:r[k] for k in ['conditions','polarity','modality'] if k in r}}
                            for k,v in dict(conditions=[],polarity='unspecified',modality='unspecified',scope='primary',applicability=pages[t['page_key']]['applicability_scope']).items():adapter.setdefault(k,v)
                            v=legacy_rules(adapter,pages[t['page_key']],screen.REGISTRY,screen.filter_flags)
                            validation.append(dict(index=i,normalized=normalized,legacy_result=v,raw_metadata_preserved_in_response=True))
                        except Exception as e:validation.append(dict(index=i,normalization_error=type(e).__name__+': '+str(e),included=False))
                except Exception as e:failure=str(e)
                result.update(output=parsed,validation=validation,schema_errors=errors,failure=failure)
                if original['output'] is not None and not original['failure']:
                    assert canonical(original['output'])==canonical(parsed)
                    assert canonical(original['validation'])==canonical(validation),t['trial_id']
                result['interface_alignment'].update(parse_status_changed=original['failure']!=failure,candidate_payload_same_when_old_decoder_succeeded=original['output']==parsed,source_response_sha256=sha(response))
            save(dest,result);done.add(t['trial_id']);last=time.monotonic()
            print('aligned',len(done),'/',len(trials),t['trial_id'],result['failure'],flush=True)
        if (FORMAL/'generation_complete.json').exists() and len(done)==len(trials):
            save(ALIGNED/'generation_complete.json',dict(trials=len(done),all_completed=True,new_generator_calls=0,source_generator_calls=read(FORMAL/'generation_complete.json')['new_generator_calls'],offline_decoder_replay=True));return
        if time.monotonic()-last>3600:raise RuntimeError('No source result progress for one hour')
        time.sleep(10)

def reuse_reviews():
    """Reuse only finished, exactly content-addressed same-model reviews."""
    original=FORMAL/'cross_evaluation';target=ALIGNED/'cross_evaluation';reused={}
    from rp1_complex_binding_cross_evaluation import AUDITOR
    for p in original.glob('E*.json'):
        if p.name.endswith(('.raw.json','.started.json')):continue
        i=original/'inputs'/p.name
        if not i.exists():continue
        v=read(i)
        if p.stem!='E'+digest([digest(AUDITOR),v['body']])[:24]:raise ValueError('review address mismatch')
        for source in [p,original/(p.stem+'.raw.json'),original/(p.stem+'.started.json')]:
            if source.exists():save(target/source.name,read(source));reused[str(source.relative_to(ROOT))]=sha(source)
    for p in (original/'preflight').glob('*.json'):save(target/'preflight'/p.name,read(p));reused[str(p.relative_to(ROOT))]=sha(p)
    save(target/'cache_reuse.json',dict(model_digest=read(ALIGNED/'resources.json')['judge']['digest'],prompt_sha256=digest(AUDITOR),source_sha256=reused,no_independent_votes_claim=True))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','run','reuse_reviews']);args=ap.parse_args();globals()[args.stage]()
