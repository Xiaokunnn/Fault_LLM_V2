#!/usr/bin/env python3
"""Prepare a compact human review packet from previously read development data."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/experiments/research_point_1'
OUT=BASE/'independent_review_v1'
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def csv_write(name,rs):
    with (OUT/name).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def priority(namespace,value):return hashlib.sha256(f'20261003/{namespace}/{value}'.encode()).hexdigest()
def main():
    OUT.mkdir(exist_ok=False);(OUT/'submissions').mkdir()
    source_path=BASE/'adjudication_targeted_v2_1/pilot_sources.jsonl'
    pages={p['page_key']:p for p in rows(source_path)}
    output_path=BASE/'clause_binding_v1/outputs.jsonl'
    candidates=[d for d in rows(output_path) if d['stage']=='R']
    critical=[d for d in candidates if d['clause_binding']['issues']]
    chosen=critical[:];sampling=[]
    assert len(critical)==10
    for page in sorted(pages):
        pool=[d for d in candidates if d['page_key']==page and d not in critical]
        selected=sorted(pool,key=lambda d:priority('control',d['candidate_review_id']))[:2]
        assert len(selected)==2
        chosen.extend(selected);sampling.append(dict(page_key=page,remaining_population=len(pool),selected=2,conditional_selection_probability=2/len(pool)))
    chosen.sort(key=lambda d:priority('blind_order',d['candidate_review_id']))
    review=[];mapping=[]
    for n,d in enumerate(chosen,1):
        rid=f'IR{n:03d}';a=d['payload']
        review.append(dict(review_id=rid,page_key=d['page_key'],source_page_sha256=d['source_page_sha256'],assertion_json=json.dumps(a,ensure_ascii=False),
            source_support='',condition_complete='',scope_appropriate='',final_verdict='',source_quote_or_locator='',reason=''))
        mapping.append(dict(review_id=rid,candidate_review_id=d['candidate_review_id'],prompt_arm=d['prompt_arm'],sample_kind='targeted_change' if d in critical else 'hash_sample_control'))
    csv_write('03_candidate_review.csv',review)
    csv_write('01_page_inventory.csv',[dict(page_key=k,source_page_sha256=p['page_text_sha256'],inventory_path=f'submissions/{k.replace(":", "_")}.md',source_first_confirmed='',scope_and_coverage_notes='') for k,p in sorted(pages.items())])
    questions=[('operation','哪些运行/启动/恢复使用操作计入核心维护动作，哪些单列？'),('bearing_scope','一般轴承知识可否继承泵手册范围，必须保留哪些限制？'),('negative_maintenance','无需维护、禁止维护/操作、正向维护如何分别表示？'),('causal_direction','原文含中间事件时，直接边与间接作用如何区分；不唯一时如何处理？'),('condition_logic','允许条件与Otherwise风险条件如何对应，怎样保留泵型及阈值范围？')]
    csv_write('02_scope_decisions.csv',[dict(issue_id=k,question=q,decision='',source_basis='',unresolved_policy='') for k,q in questions])
    refs=rows(BASE/'offline_contract_v3/reference_overlay.jsonl')
    csv_write('04_reference_review.csv',[dict(reference_id=r['reference_id'],page_key=r['page_key'],proposed_reference_json=json.dumps(r['v21_reference_unchanged'],ensure_ascii=False),verdict='',corrected_statement_or_inventory_id='',reason='') for r in refs])
    write(OUT/'private_mapping.json',mapping)
    write(OUT/'sampling.json',dict(seed=20261003,total=22,targeted=10,controls=12,strata=sampling,population_accuracy_estimate_allowed=False))
    write(OUT/'reviewer.json',dict(reviewer_name='',professional_background='',reviewer_kind='',independent_of_existing_AI_labels=False,source_first_review_completed=False,completed_at='',method_disposition='',disagreement_resolution_path='submissions/disagreement_resolution.md'))
    holdout=BASE/'scope_repair_v2/holdout_manifest.jsonl'
    held=rows(holdout);assert len(held)==29 and not ({p['page_key'] for p in held}&set(pages))
    write(OUT/'holdout_plan.json',dict(status='NOT_OPENED',pages=held,extraction='one frozen E1 request per page',planned_requests=29,arms=['raw','mechanical_filter','source_constrained_repair'],formal_metrics='require independent source-first reference and output review'))
    requests=rows(BASE/'adjudication_targeted_v2_1_qwen38_timeout180/requests.jsonl')
    item=next(r for r in requests if r['arm']=='E1')
    template={k:v for k,v in item['payload'].items() if k!='messages'}
    template['system_prompt']=item['payload']['messages'][0]['content']
    write(OUT/'extraction_template.json',template)
    runtime=[ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/automatic_contract_v4_1.py',ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/clause_binding_v1.py',ROOT/'scripts/rp1_offline_contract_v3.py',ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json']
    deps=runtime+[holdout,source_path,output_path,BASE/'offline_contract_v3/reference_overlay.jsonl',OUT/'extraction_template.json',ROOT/'docs/research/RP1_INDEPENDENT_REVIEW_AND_HOLDOUT_V1_20261003.md',Path(__file__)]
    write(OUT/'candidate_method_seal.json',dict(status='PENDING_INDEPENDENT_REVIEW',sealed_at=datetime.now(timezone.utc).isoformat(),sha256={str(p.relative_to(ROOT)):sha(p) for p in deps},heldout_contents_opened=0,formal_freeze=False))
    # Freeze source/identity columns while allowing the designated review fields to be filled.
    write(OUT/'review_input_manifest.json',dict(candidate_rows=[{k:r[k] for k in ['review_id','page_key','source_page_sha256','assertion_json']} for r in review],
        reference_ids=[r['reference_id'] for r in refs],page_hashes={k:p['page_text_sha256'] for k,p in pages.items()},scope_issues=[k for k,q in questions]))
    print(json.dumps(dict(candidate_reviews=22,source_pages=6,scope_questions=5,provisional_references=85,holdout_pages=29,holdout_contents_opened=0,review_status='pending')))
if __name__=='__main__':main()
