#!/usr/bin/env python3
"""Compute the fixed pilot's quantity, source-review and coverage results."""
import csv
import io
import json
from collections import Counter
from validate_rp1_extraction import OUT, ROOT, rows, write, sha, verify, priority


def relation_key(a):
    r=a.get('raw',{})
    if not isinstance(r,dict):return None
    keys=['head_type','head_canonical_zh','relation','tail_type','tail_canonical_zh','polarity']
    if any(not isinstance(r.get(k),str) or not r[k].strip() for k in keys):return None
    return tuple(' '.join(r[k].casefold().split()) for k in keys)


def main():
    verify()
    for p,h in json.loads((OUT/'output_freeze.json').read_text())['sha256'].items():assert sha(ROOT/p)==h
    records=rows(OUT/'candidates.jsonl');by_id={a['candidate_id']:a for a in records}
    sample=rows(OUT/'review_sample.jsonl');reviews=rows(OUT/'source_review.jsonl')
    assert {r['candidate_id'] for r in reviews}=={s['candidate_id'] for s in sample} and len(reviews)==len(sample)
    assert all(r['grade'] in ['S','E','U'] for r in reviews)
    source_grade={r['candidate_id']:r['grade'] for r in reviews}
    structural=json.loads((OUT/'structural_summary.json').read_text())
    inventory=rows(OUT/'source_inventory.jsonl');coverage=rows(OUT/'coverage_review.jsonl')
    assert {r['reference_id'] for r in inventory}=={r['reference_id'] for r in coverage}
    assert all(r['status'] in ['complete','partial','missing','unresolved'] for r in coverage)
    for r in coverage:assert set(r['candidate_ids'])<=set(by_id)
    success=sum(by_id[r['candidate_id']]['automatic_pass'] and r['grade']=='S' for r in reviews)
    fail=sum(by_id[r['candidate_id']]['automatic_pass'] and r['grade']=='E' for r in reviews)
    rejected_supported=sum(not by_id[r['candidate_id']]['automatic_pass'] and r['grade']=='S' for r in reviews)
    result=dict(status='small_API_validation_completed',pages_requested=10,valid_response_pages=structural['valid_response_pages'],
        returned_models=structural['returned_models'],all_output_candidates=len(records),automatic_pass=structural['automatic_pass'],
        automatic_pass_fraction=structural['automatic_fraction'],automatic_distinct_relations=len({relation_key(a) for a in records if a['automatic_pass']}),
        parseable_distinct_relations=len({relation_key(a) for a in records if relation_key(a) is not None}),
        unparseable_relation_records=sum(relation_key(a) is None for a in records),
        duplicate_parseable_occurrences=sum(relation_key(a) is not None for a in records)-len({relation_key(a) for a in records if relation_key(a) is not None}),
        source_review=dict(n=len(reviews),S=sum(r['grade']=='S' for r in reviews),E=sum(r['grade']=='E' for r in reviews),U=sum(r['grade']=='U' for r in reviews),
            joint_source_supported_and_automatic_pass=success,joint_success_fraction=success/len(reviews) if reviews else None,
            defects_automatically_released=fail,source_supported_but_automatically_rejected=rejected_supported),
        coverage=dict(items=len(inventory),statuses=dict(Counter(r['status'] for r in coverage)),
            limitation='65 pre-API source-first AI checklist items; variable granularity and not exhaustive; matching proportion is not formal recall'),
        limitations=['same assistant develops and reviews, unblinded single-AI audit; not independent expert truth',
            'uniform up-to-60 sample of all candidate outputs; unknown quality outside sample',
            'same build documents, possible neighboring previously-reviewed context; not independent document generalization',
            'automatic structural/provenance pass does not prove complete semantics or conditions',
            'relation dedup is exact canonical type/name/relation/polarity; context-qualified assertions remain distinct'])
    result['target_75_percent']=dict(target=.75,automatic_reached=structural['automatic_fraction'] is not None and structural['automatic_fraction']>=.75,
        sample_joint_reached=bool(reviews) and success/len(reviews)>=.75,
        overall='PASS_IN_THIS_PILOT_SAMPLE' if structural['valid_response_pages']==10 and structural['automatic_fraction']>=.75 and success/len(reviews)>=.75 else 'FAIL',
        interpretation='A sample criterion, not certification that at least 75% of all outputs or future pages are usable')
    result['by_stratum']={}
    for kind in ['prose','fault_table','maintenance']:
        group=[a for a in records if a['stratum']==kind];rv=[r for r in reviews if by_id[r['candidate_id']]['stratum']==kind]
        result['by_stratum'][kind]=dict(pages=sum(p.get('stratum')==kind for p in structural['pages']),candidates=len(group),
            automatic_pass=sum(a['automatic_pass'] for a in group),sample_n=len(rv),sample_S=sum(r['grade']=='S' for r in rv),sample_E=sum(r['grade']=='E' for r in rv),sample_U=sum(r['grade']=='U' for r in rv),
            sample_joint_success=sum(r['grade']=='S' and by_id[r['candidate_id']]['automatic_pass'] for r in rv))
    result['by_page']=[dict(p,source_review=dict(Counter(r['grade'] for r in reviews if by_id[r['candidate_id']]['page_key']==p['page_key'])),coverage=dict(Counter(r['status'] for r in coverage if r['page_key']==p['page_key']))) for p in structural['pages']]
    result['network_attempts']=len(list((OUT/'api').glob('*.started.json')))
    result['initial_timeout_attempts']=len([p for p in (OUT/'api').glob('*.failed.json') if json.loads(p.read_text()).get('exception_class')=='TimeoutError'])
    result['successful_response_usage']={k:sum(json.loads(p.read_text()).get('usage',{}).get(k,0) for p in (OUT/'api').glob('*.completed.json')) for k in ['prompt_tokens','completion_tokens','total_tokens']}
    result['usage_note']='Only received successful responses have usage. Initial timeout may have been billed; no exact total cost claim.'
    write(OUT/'metrics.json',result)
    buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=['candidate_id','page_key','head_zh','relation','tail_zh','polarity','conditions_zh','applicability_zh','automatic_pass','AI_sample_grade','failure_flags']);writer.writeheader()
    for a in records:
        r=a.get('raw',{}) if isinstance(a.get('raw'),dict) else {}
        writer.writerow(dict(candidate_id=a['candidate_id'],page_key=a['page_key'],head_zh=r.get('head_canonical_zh'),relation=r.get('relation'),tail_zh=r.get('tail_canonical_zh'),polarity=r.get('polarity'),
            conditions_zh=json.dumps(a.get('inherited_conditions_zh'),ensure_ascii=False),applicability_zh=a.get('applicability_zh'),automatic_pass=a['automatic_pass'],AI_sample_grade=source_grade.get(a['candidate_id'],'not_sampled'),failure_flags=json.dumps(a['flags'],ensure_ascii=False)))
    with (OUT/'extracted_records.csv').open('x') as f:f.write(buf.getvalue())
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
