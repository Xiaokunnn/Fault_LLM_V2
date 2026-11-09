#!/usr/bin/env python3
"""Reconstruct all fixed fragment-trial outputs and source-AI evaluations."""
import csv
import io
import json
from collections import Counter
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from validate_rp1_fragments import RUN,verify_inputs
from rp1_offline_contract_v3 import rows,sha,write,REGISTRY
from research_point_1_graph_evidence.stage02_triple_extraction.source_fragment_extraction import compile_records,object_hash


def main():
    requests=verify_inputs();decisions=rows(RUN/'decisions.jsonl');reviews=rows(RUN/'source_review.jsonl')
    coverage=rows(RUN/'coverage_review.jsonl');refs=rows(RUN/'source_reference.jsonl')
    assert len(reviews)==len(decisions)==len({r['candidate_id'] for r in reviews})
    reviewed={r['candidate_id']:r for r in reviews};sources={s['page_key']:s for s in rows(RUN/'sources.jsonl')}
    rebuilt=[];checks=0;usage=Counter();catalog_count=0
    for req in requests:
        rid=req['request_id'];raw=RUN/'api'/f'{rid}.response.bin';meta=json.load(open(RUN/'api'/f'{rid}.completed.json'))
        assert meta['response_sha256']==sha(raw) and meta['payload_sha256']==req['payload_sha256']
        assert meta['returned_model']=='qwen3.8-max' and meta['finish_reason']=='stop'
        content=json.loads(json.loads(raw.read_bytes())['choices'][0]['message']['content'])
        assert content==json.load(open(RUN/'api'/f'{rid}.parsed.json'))
        cat=json.load(open(RUN/'catalogs'/f'{rid}.json'));test=dict(cat);test.pop('catalog_sha256')
        assert object_hash(test)==cat['catalog_sha256']==req['catalog_sha256']
        assert cat['coverage']['source_character_coverage']==1 and not cat['coverage']['missing'];catalog_count+=1
        compiled=compile_records(content,cat,REGISTRY)
        rebuilt += [dict(candidate_id=f'{rid}:{a["index"]:03d}',page_key=req['page_key'],**a) for a in compiled]
        native={};s=sources[req['page_key']]
        for p in [s['target'],*s['context_pages']]:
            native.update({b['block_id']:b for b in p['text_blocks']})
            native.update({c['cell_id']:c for t in p['tables'] for row in t['rows'] for c in row['cells']})
        for part in [*cat['paragraphs'].values(),*cat['candidates'].values()]:
            for w in part['source_spans']:
                assert native[w['unit_id']]['text'][w['start']:w['end']]==w['text']
                assert native[w['unit_id']]['bbox']==w['bbox'];checks+=1
        usage.update({k:v for k,v in meta['usage'].items() if isinstance(v,int)})
    assert rebuilt==decisions
    assert {r['reference_id'] for r in refs}=={r['reference_id'] for r in coverage}
    for r in reviews:
        assert r['decision_sha256']==sha(RUN/'decisions.jsonl')
        grades=[r['core_grade'],r['condition_grade'],r['primary_target_scope_grade']]
        assert r['overall_grade']==('E' if 'E' in grades else 'S' if all(g=='S' for g in grades) else 'U')
    def exact_key(a):
        # Exact text including conditions; not full semantic deduplication.
        r=a['raw']
        return object_hash(dict(head=r.get('head'),relation=r.get('relation'),tail=r.get('tail'),
            modality=r.get('mode'),polarity=r.get('polarity'),
            conditions=[(c['category'],c['kind'],c['canonical_zh'],c['text']) for c in a.get('conditions',[])]))
    def count(items):
        support=[a for a in items if reviewed[a['candidate_id']]['overall_grade']=='S']
        joint=[a for a in support if a['automatic_pass']]
        # Use names/types rather than location IDs for claim-text dedup.
        def claim_key(a):
            r=a['raw'];h=r.get('head',[]);t=r.get('tail',[])
            return object_hash(dict(head=h[1:] if isinstance(h,list) else h,relation=r.get('relation'),
                tail=t[1:] if isinstance(t,list) else t,mode=r.get('mode'),polarity=r.get('polarity'),
                conditions=[(c['category'],c['kind'],c['canonical_zh'],c['text']) for c in a.get('conditions',[])]))
        flags=Counter(f for a in items for f in a['flags'])
        return dict(candidates=len(items),automatic_pass=sum(a['automatic_pass'] for a in items),
            source_task_AI_grades=dict(Counter(reviewed[a['candidate_id']]['overall_grade'] for a in items)),
            full_condition_primary_target_AI_support=len(support),jointly_supported_automatic=len(joint),
            automatic_fraction=sum(a['automatic_pass'] for a in items)/len(items) if items else None,
            source_support_fraction=len(support)/len(items) if items else None,joint_fraction=len(joint)/len(items) if items else None,
            distinct_automatic_claim_texts=len({claim_key(a) for a in items if a['automatic_pass']}),
            distinct_supported_claim_texts=len({claim_key(a) for a in support}),distinct_joint_claim_texts=len({claim_key(a) for a in joint}),
            source_supported_but_contract_rejected=sum(not a['automatic_pass'] for a in support),
            automatic_but_source_defective=sum(a['automatic_pass'] and reviewed[a['candidate_id']]['overall_grade']=='E' for a in items),
            any_Chinese_name_failure=sum(bool(set(a['flags'])&{'head_not_chinese','tail_not_chinese','condition_not_chinese'}) for a in items),
            endpoint_namespace_or_ID_failure=sum(bool(set(a['flags'])&{'head_unknown_endpoint','tail_unknown_endpoint'}) for a in items),
            no_target_evidence=sum('no_target_page_evidence' in a['flags'] for a in items),failure_flags=dict(flags))
    eligible=[r for r in coverage if r['eligible_for_primary_graph']];complete=sum(r['status']=='complete' for r in eligible)
    joint_complete=sum(r['complete_joint_application_coverage'] for r in eligible)
    overall=count(decisions);by_page={k:count([a for a in decisions if a['page_key']==k]) for k in sources}
    eligible_pages={r['page_key'] for r in eligible}
    served=sum(by_page[p]['jointly_supported_automatic']>0 for p in eligible_pages)
    criteria=dict(joint_fraction_at_least_75_percent=overall['joint_fraction'] is not None and overall['joint_fraction']>=.75,
        complete_AI_reference_coverage_at_least_75_percent=complete/len(eligible)>=.75,
        every_prespecified_in_scope_page_has_joint_relation=served==len(eligible_pages))
    result=dict(status='FAIL' if not all(criteria.values()) else 'PASS',overall=overall,by_page=by_page,
        coverage=dict(total_reference_items=len(refs),in_scope_reference_items=len(eligible),status_counts=dict(Counter(r['status'] for r in coverage)),
            complete_source_representation=complete,complete_fraction=complete/len(eligible),complete_joint_application=joint_complete,
            joint_complete_fraction=joint_complete/len(eligible),prespecified_in_scope_pages=len(eligible_pages),joint_served_pages=served,
            meaning='Nonexhaustive pre-API AI checklist, variable granularity; not formal recall'),
        gate=criteria,API=dict(requests=10,completed=10,automatic_retries=0,usage=dict(usage)),
        native_span_roundtrips=checks,catalogs_verified=catalog_count,
        dedup_meaning='exact normalized record text/type/condition dedup, not full semantic identity or net addition against existing graphs',
        review_meaning='All 138 received outputs checked by Codex against source; nonblind AI judgment, not expert factual accuracy. Scope/protocol failures are separated from core/condition judgments.',
        code_or_prompt_changed_after_outputs=False,graph_promoted=False)
    write(RUN/'quality_metrics.json',result)
    stream=io.StringIO();writer=csv.writer(stream)
    writer.writerow(['candidate_id','page_key','head','relation','tail','mode','polarity','conditions','automatic_pass','flags','core_grade','condition_grade','target_scope_grade','overall_grade','reason'])
    for a in decisions:
        r=reviewed[a['candidate_id']]
        writer.writerow([a['candidate_id'],a['page_key'],json.dumps(a['raw'].get('head'),ensure_ascii=False),a['raw'].get('relation'),
            json.dumps(a['raw'].get('tail'),ensure_ascii=False),a['raw'].get('mode'),a['raw'].get('polarity'),
            json.dumps(a.get('conditions',[]),ensure_ascii=False),a['automatic_pass'],'|'.join(a['flags']),
            r['core_grade'],r['condition_grade'],r['primary_target_scope_grade'],r['overall_grade'],r['reason']])
    dest=RUN/'records.csv';data=stream.getvalue().encode('utf-8-sig')
    if dest.exists():assert dest.read_bytes()==data
    else:dest.write_bytes(data)
    write(RUN/'verification.json',dict(status='PASS',complete_response_reconstructions=10,all_candidates_recompiled=len(decisions),
        all_AI_judgments_recounted=len(reviews),reference_items_recounted=len(refs),native_span_roundtrips=checks,
        code_and_source_freezes_verified=True,semantic_truth_not_proven_by_verification=True))
    print(json.dumps({k:v for k,v in result.items() if k!='by_page'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
