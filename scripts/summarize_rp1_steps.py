#!/usr/bin/env python3
"""Reconstruct response/position counts and one-layer source-AI judgments."""
import csv
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from rp1_offline_contract_v3 import rows,write,sha,REGISTRY
from validate_rp1_steps import OUT,RUN,verify_inputs
from research_point_1_graph_evidence.stage02_triple_extraction.step_fragment_extraction import compile_local_records,object_hash


def key(d):
    return json.dumps([d.get('head',{}).get('type'),d.get('head',{}).get('canonical_zh'),d.get('relation'),d.get('tail',{}).get('type'),d.get('tail',{}).get('canonical_zh'),d.get('modality'),d.get('polarity'),sorted((c['category'],c['canonical_zh']) for c in d.get('conditions',[]))],ensure_ascii=False,sort_keys=True)


def main():
    requests=verify_inputs();saved=rows(RUN/'decisions.jsonl');rebuilt=[];roundtrips=0;usage=Counter()
    sources={s['page_key']:s for s in rows(RUN/'sources.jsonl')}
    for req in requests:
        rid=req['request_id'];cat=json.load(open(RUN/'catalogs'/f'{rid}.json'))
        assert cat['catalog_sha256']==object_hash({k:v for k,v in cat.items() if k!='catalog_sha256'})
        raw=RUN/'api'/f'{rid}.response.bin';envelope=json.loads(raw.read_bytes())
        completed=json.load(open(RUN/'api'/f'{rid}.completed.json'))
        assert completed['response_sha256']==sha(raw) and envelope['choices'][0]['finish_reason']=='stop'
        response=json.loads(envelope['choices'][0]['message']['content']);assert response==json.load(open(RUN/'api'/f'{rid}.parsed.json'))
        compiled=compile_local_records(response,cat,REGISTRY)
        rebuilt.extend(dict(candidate_id=f'{rid}:{d["index"]:03d}',page_key=req['page_key'],**d) for d in compiled)
        usage.update({k:v for k,v in completed.get('usage',{}).items() if isinstance(v,int)})
        s=sources[req['page_key']];native={}
        for p in [s['target'],*s['context_pages']]:
            native.update({b['block_id']:b for b in p['text_blocks']})
            native.update({c['cell_id']:c for t in p['tables'] for r in t['rows'] for c in r['cells']})
        for obj in [*cat['headings'].values(),*[v for u in cat['units'].values() for v in [u,*u['choices'].values()]]]:
            for w in obj['source_spans']:
                assert native[w['unit_id']]['text'][w['start']:w['end']]==w['text']
                assert native[w['unit_id']]['bbox']==w['bbox'];roundtrips+=1
        for uid,proof in cat['duplicate_native_units'].items():
            assert native[uid]['text']==proof['original_text'] and native[uid]['bbox']==proof['bbox']
    assert saved==rebuilt
    review=rows(RUN/'source_review.jsonl');by={r['candidate_id']:r for r in review}
    assert len(review)==len(saved)==len(by) and set(by)=={d['candidate_id'] for d in saved}
    for d in saved:
        r=by[d['candidate_id']];assert r['decision_sha256']==object_hash(d)
        assert r['overall_grade'] in ['S','E','U'] and r['reason']
    refs=rows(RUN/'source_reference.jsonl');coverage=rows(RUN/'coverage_review.jsonl');cov={r['reference_id']:r for r in coverage}
    assert len(coverage)==len(refs)==len(cov) and set(cov)=={r['reference_id'] for r in refs}
    for r in coverage:
        assert r['status'] in ['complete','partial','missing','scope_control']
        for cid in r['matched_candidates']:assert cid in by
        if r['status']=='complete':assert r['supported_candidates'] and all(by[c]['overall_grade']=='S' for c in r['supported_candidates'])
    supported=[d for d in saved if by[d['candidate_id']]['overall_grade']=='S']
    automatic=[d for d in saved if d['automatic_pass']];joint=[d for d in supported if d['automatic_pass']]
    eligible=[r for r in refs if r['eligible_for_primary_graph']]
    complete=sum(cov[r['reference_id']]['status']=='complete' for r in eligible)
    pages=[dict(page_key=q['page_key'],candidates=sum(d['page_key']==q['page_key'] for d in saved),automatic_pass=sum(d['page_key']==q['page_key'] for d in automatic),source_AI_supported=sum(d['page_key']==q['page_key'] for d in supported),joint_supported=sum(d['page_key']==q['page_key'] for d in joint)) for q in requests]
    expected={r['page_key'] for r in eligible};counts=Counter(d['page_key'] for d in joint)
    gate=json.load(open(RUN/'method.json'))['expansion_gate']
    rules=dict(joint_fraction=len(joint)/len(saved)>=gate['joint_supported_fraction'] if saved else False,
        reference_fraction=complete/len(eligible)>=gate['complete_reference_fraction'] if eligible else False,
        minimum_distinct=len({key(d) for d in joint})>=gate['minimum_joint_distinct_relations'],
        all_in_scope_pages=all(counts[k]>0 for k in expected))
    result=dict(actual_requests=10,complete_responses=10,candidates=len(saved),automatic_pass=len(automatic),
        source_AI_supported=len(supported),source_AI_grades=dict(Counter(r['overall_grade'] for r in review)),
        jointly_supported=len(joint),joint_fraction=len(joint)/len(saved) if saved else 0,
        distinct_exact={'automatic':len({key(d) for d in automatic}),'supported':len({key(d) for d in supported}),'joint':len({key(d) for d in joint})},
        supported_but_interface_rejected=len(supported)-len(joint),automatic_not_AI_supported=len(automatic)-len(joint),
        reference_items=len(refs),eligible_reference_items=len(eligible),eligible_reference_status=dict(Counter(cov[r['reference_id']]['status'] for r in eligible)),
        complete_reference_fraction=complete/len(eligible),in_scope_pages=len(expected),in_scope_pages_with_joint=sum(counts[k]>0 for k in expected),
        expansion_rules=rules,expansion_gate='PASS' if all(rules.values()) else 'FAIL',pages=pages,
        flags=dict(Counter(f for d in saved for f in d['flags'])),usage=dict(usage),
        source_review='Codex nonblind full-population source reading; one AI layer, not expert truth',
        reference_limit='nonexhaustive heterogeneous source checklist, not formal recall',
        distinct_limit='exact Chinese text/type/condition keys, not semantic dedup or net new graph additions',graph_promoted=False)
    write(RUN/'quality_metrics.json',result)
    omission=dict(automatically_passed_source_AI_grades=dict(Counter(by[d['candidate_id']]['overall_grade'] for d in automatic)),
        references_without_any_supported_relation_component=sum(not cov[r['reference_id']]['supported_candidates'] for r in eligible),
        complete_joint_application_reference_items=sum(cov[r['reference_id']]['complete_joint_application_coverage'] for r in eligible),
        coverage_status_limit='partial includes incomplete or incorrectly expressed output, not evidence that each partial item has correct graph knowledge',
        missing_source_components=[
            dict(page='MP022 p27',component='Failed swab test: repeat steps 2-6 / 3-7 until passed; missing action proposal for repeat'),
            dict(page='MP005 p57',component='Explosion-proof motor start frequency from manufacturer documents'),
            dict(page='MP001 p48',component='Nearby random noise interference, FFT transform/baseline comparison and detection limitations'),
            dict(page='MP005 p6',component='Single-stage vertical in-line pump type; proper geometry relation for aligned inlet/outlet')],
        scope_or_binding_issues_not_counted_as_literal_zero_output=['LKH Prime10/20 shaft-cleaning restrictions','Column-specific seal/bearing replacement intervals','Selected physical parameter as Component','these cases anaphoric oil-condition binding'])
    write(RUN/'error_and_omission_summary.json',omission)
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=['candidate_id','page_key','head','relation','tail','conditions','automatic_pass','flags','source_AI_grade','reason']);writer.writeheader()
    for d in saved:
        writer.writerow(dict(candidate_id=d['candidate_id'],page_key=d['page_key'],head=json.dumps(d.get('head'),ensure_ascii=False),relation=d.get('relation'),tail=json.dumps(d.get('tail'),ensure_ascii=False),conditions=json.dumps(d.get('conditions'),ensure_ascii=False),automatic_pass=d['automatic_pass'],flags='|'.join(d['flags']),source_AI_grade=by[d['candidate_id']]['overall_grade'],reason=by[d['candidate_id']]['reason']))
    path=RUN/'records.csv';content=stream.getvalue()
    if path.exists() and path.read_bytes()!=content.encode():raise ValueError('refuse overwrite CSV')
    if not path.exists():path.write_bytes(content.encode())
    for name,h in json.load(open(OUT/'preservation.json')).items():assert sha(ROOT/name)==h,name
    write(RUN/'verification.json',dict(status='PASS',requests=10,candidates=len(saved),source_AI_rows=len(review),reference_rows=len(refs),native_position_roundtrips=roundtrips,old_assets_preserved=True,network_attempts=10,source_semantic_truth_not_proven=True))
    print(json.dumps({k:v for k,v in result.items() if k not in ['pages','flags']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
