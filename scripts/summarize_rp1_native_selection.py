#!/usr/bin/env python3
"""Reconstruct the two-page trial, source judgments and complete denominator."""
import csv
import io
import json
from collections import Counter
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from try_rp1_native_selection import OUT,OLD,verify_inputs
from rp1_offline_contract_v3 import REGISTRY,rows,sha,write
from research_point_1_graph_evidence.stage02_triple_extraction.native_evidence_selection import catalog,compile_selection


def main():
    requests=verify_inputs();sources={s['page_key']:s for s in rows(OUT/'sources.jsonl')}
    decisions=rows(OUT/'selection_decisions.jsonl');reviews=rows(OUT/'source_review.jsonl')
    assert len({a['candidate_id'] for a in reviews})==len(reviews)==len(decisions)
    reviewed={a['candidate_id']:a for a in reviews};usage=Counter();rebuilt=[];roundtrips=0
    for req in requests:
        prefix=OUT/'api'/req['request_id'];raw=Path(str(prefix)+'.response.bin')
        meta=json.loads(Path(str(prefix)+'.completed.json').read_text());envelope=json.loads(raw.read_bytes())
        assert sha(raw)==meta['response_sha256'] and meta['payload_sha256']==req['payload_sha256']
        assert meta['returned_model']=='qwen3.8-max' and meta['finish_reason']=='stop'
        content=json.loads(envelope['choices'][0]['message']['content'])
        assert content==json.loads(Path(str(prefix)+'.parsed.json').read_text())
        usage.update({k:v for k,v in meta['usage'].items() if isinstance(v,int)})
        s=sources[req['page_key']]
        batch=compile_selection(content,s['target'],s['context_pages'],REGISTRY)
        rebuilt += [dict(page_key=s['page_key'],candidate_id=f'{req["request_id"]}:{a["index"]:03d}',**a) for a in batch]
        native={u['native_id']:u for u in catalog(s['target'],s['context_pages']).values()}
        for a in batch:
            ws=a.get('source_witnesses',[])+a.get('negation_witnesses',[])
            for side in ['head','tail']:ws+=a.get(side,{}).get('source_spans',[])
            for c in a.get('conditions',[]):ws+=c['source_spans']+c['binding_spans']
            for w in ws:
                u=native[w['unit_id']]
                assert u['text'][w['start']:w['end']]==w['text'] and u['bbox']==w['bbox']
                assert u['text_sha256']==w['unit_text_sha256'];roundtrips+=1
    assert rebuilt==decisions
    assert set(reviewed)=={a['candidate_id'] for a in decisions}
    for a in reviews:
        assert a['decision_sha256']==sha(OUT/'selection_decisions.jsonl')
        expected='E' if 'E' in [a['core_grade'],a['condition_grade']] else 'S' if a['core_grade']==a['condition_grade']=='S' else 'U'
        assert a['overall_grade']==expected
    def key(a):return tuple(a[s]['canonical_zh'].strip() for s in ['head'])+(a['relation'],a['tail']['canonical_zh'].strip(),a['polarity'])
    def summary(items):
        supported=[a for a in items if reviewed[a['candidate_id']]['overall_grade']=='S']
        joint=[a for a in supported if a['automatic_pass']]
        return dict(candidates=len(items),automatic_pass=sum(a['automatic_pass'] for a in items),
            automatic_fraction=sum(a['automatic_pass'] for a in items)/len(items),
            source_AI_grades=dict(Counter(reviewed[a['candidate_id']]['overall_grade'] for a in items)),
            source_AI_supported=len(supported),source_AI_supported_fraction=len(supported)/len(items),
            jointly_supported_and_automatic=len(joint),joint_fraction=len(joint)/len(items),
            automatic_but_source_defective=sum(a['automatic_pass'] and reviewed[a['candidate_id']]['overall_grade']=='E' for a in items),
            source_supported_primary_but_contract_rejected=sum(not a['automatic_pass'] and a['raw'].get('scope')=='primary' for a in supported),
            source_supported_background_excluded=sum(a['raw'].get('scope')=='background' for a in supported),
            distinct_automatic_relations=len({key(a) for a in items if a['automatic_pass']}),
            distinct_source_AI_supported_relations=len({key(a) for a in supported}),
            distinct_joint_relations=len({key(a) for a in joint}),
            failure_flags=dict(Counter(f for a in items for f in a['flags'])))
    old=[a for a in rows(OLD/'candidates.jsonl') if a['page_key'] in sources]
    coverage=rows(OUT/'coverage_review.jsonl')
    frozen_refs={a['reference_id'] for a in rows(OLD/'source_inventory.jsonl') if a['page_key'] in sources}
    assert frozen_refs=={a['reference_id'] for a in coverage}
    assert all(cid in reviewed for r in coverage for cid in r['candidate_ids'])
    result=dict(status='development_trial_FAIL',overall=summary(decisions),
        by_page={k:summary([a for a in decisions if a['page_key']==k]) for k in sources},
        old_same_page_outputs=dict(candidates=len(old),automatic_pass=sum(a['automatic_pass'] for a in old),
            meaning='69 versus 33 is output quantity only; compiler/prompt differ, not a controlled accuracy comparison'),
        coverage=dict(items=len(coverage),status_counts=dict(Counter(a['status'] for a in coverage)),
            meaning='Existing source-first AI checklist, nonexhaustive and variable granularity; not formal recall'),
        API=dict(actual_requests=2,complete_responses=2,returned_model='qwen3.8-max',usage=dict(usage),automatic_retries=0),
        source_span_roundtrips=roundtrips,review='Codex full-population source-reading AI, development and nonblind; no extra review API',
        goal_75_percent_met=False,graph_promoted=False,post_response_compiler_changes=False)
    write(OUT/'quality_metrics.json',result)
    stream=io.StringIO();writer=csv.writer(stream)
    writer.writerow(['candidate_id','page_key','head_zh','head_surface','relation','tail_zh','tail_surface','polarity','modality','condition_ids','conditions_zh','automatic_pass','flags','source_AI_grade','core_grade','condition_grade','reason'])
    for a in decisions:
        r=reviewed[a['candidate_id']]
        writer.writerow([a['candidate_id'],a['page_key'],a['head']['canonical_zh'],a['head']['surface'],a['relation'],a['tail']['canonical_zh'],a['tail']['surface'],a['polarity'],a['modality'],
            '|'.join(c['condition_id'] for c in a['conditions']),'|'.join(c['canonical_zh'] for c in a['conditions']),a['automatic_pass'],'|'.join(a['flags']),r['overall_grade'],r['core_grade'],r['condition_grade'],r['reason']])
    path=OUT/'records.csv';data=stream.getvalue().encode('utf-8-sig')
    if path.exists():assert path.read_bytes()==data
    else:path.write_bytes(data)
    write(OUT/'verification_after_API.json',dict(status='PASS',raw_responses_reconstructed=2,
        all_candidates_recompiled=len(decisions),native_positions_reconstructed=roundtrips,
        all_source_AI_judgments_recounted=len(reviews),coverage_items_recounted=len(coverage),
        semantic_truth_not_proven_by_reconstruction=True,API_calls=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
