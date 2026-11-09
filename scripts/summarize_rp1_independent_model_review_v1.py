#!/usr/bin/env python3
"""Join model second opinions with prior AI labels only AFTER inference ends."""
from collections import Counter
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/experiments/research_point_1'
PACKAGE=BASE/'independent_review_v1'
OUT=PACKAGE/'local_model_second_opinion'
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def write(p,value):
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    completed=json.loads((OUT/'completion.json').read_text());assert completed['n']==22
    mapping={r['review_id']:r for r in json.loads((PACKAGE/'private_mapping.json').read_text())}
    prior={r['candidate_review_id']:r for r in rows(BASE/'clause_binding_v1/AI_review.jsonl') if r['stage']=='R'}
    inputs={r['review_id']:r for r in rows(OUT/'blind_inputs.jsonl')}
    joined=[]
    for rid,identity in mapping.items():
        result=json.loads((OUT/(rid+'.json')).read_text());old=prior[identity['candidate_review_id']]
        equivalent='S' if old['AI_contract_status']=='complete' else 'U' if old['AI_contract_status']=='unresolved' else 'N'
        assert result['source_page_sha256']==inputs[rid]['source_page_sha256']
        joined.append(dict(**identity,page_key=old['page_key'],prior_AI_contract_status=old['AI_contract_status'],prior_AI_SNU=equivalent,
                           local_model_label=result['label'],model_assessed=result['status']=='assessed',agreement=result['label']==equivalent if result['status']=='assessed' else None,
                           unrestricted_next_token_in_choices=result.get('unrestricted_next_token_in_choices'),input_tokens=result['input_tokens'],
                           independent_human_adjudication='pending'))
    with (OUT/'operator_only_comparison.jsonl').open('x',encoding='utf-8') as f:
        for r in joined:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    assessed=[r for r in joined if r['model_assessed']]
    confusion=Counter((r['prior_AI_SNU'],r['local_model_label']) for r in assessed)
    summary=dict(sample=22,assessed=len(assessed),unassessed_context_limit=22-len(assessed),local_model_labels=dict(Counter(r['local_model_label'] for r in assessed)),
                 agreement_with_prior_AI=sum(r['agreement'] for r in assessed),disagreement_with_prior_AI=sum(not r['agreement'] for r in assessed),
                 confusion=[dict(prior_AI=a,local_model=b,count=n) for (a,b),n in sorted(confusion.items())],
                 by_sample_kind={kind:dict(n=sum(r['sample_kind']==kind for r in joined),assessed=sum(r['sample_kind']==kind for r in assessed),disagreements=sum(r['sample_kind']==kind and not r['agreement'] for r in assessed)) for kind in ['targeted_change','hash_sample_control']},
                 unrestricted_next_token_outside_SNU=sum(r['unrestricted_next_token_in_choices'] is False for r in assessed),
                 wall_seconds=completed['wall_seconds'],formal_accuracy_recall='not_computed',expert_review='pending',
                 interpretation='Blind independent model call, not independent human evidence; same Qwen family can share errors; agreement is not accuracy.',
                 heldout_pages_opened=0,new_external_API_calls=0)
    write(OUT/'summary.json',summary)
    disagreements=[r for r in joined if r['agreement'] is False or not r['model_assessed']]
    write(OUT/'operator_only_disagreements.json',disagreements)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
