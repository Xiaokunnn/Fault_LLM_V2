#!/usr/bin/env python3
"""Check real review deliveries; optional freeze and source-only holdout export.

This validates completeness and provenance, not reviewer identity or expertise.
Model-only reviews cannot satisfy the independent-human gate.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/experiments/research_point_1/independent_review_v1'
DOCS={f'MP{i:03d}' for i in [*range(1,8),*range(15,23)]}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def submission(out,value):
    p=(out/value).resolve()
    if not p.is_relative_to((out/'submissions').resolve()):return None
    return p if p.is_file() and p.read_text().strip() else None

def reviewer_issues(reviewer):
    problems=[]
    if reviewer.get('reviewer_kind') not in {'independent_technical_reviewer','domain_expert'}:problems.append('independent human reviewer not identified')
    for key in ['reviewer_name','professional_background','completed_at']:
        if not reviewer.get(key):problems.append('reviewer metadata missing: '+key)
    if reviewer.get('completed_at'):
        try:datetime.fromisoformat(reviewer['completed_at'])
        except ValueError:problems.append('invalid review completion timestamp')
    for key in ['independent_of_existing_AI_labels','source_first_review_completed']:
        if reviewer.get(key) is not True:problems.append('reviewer attestation missing: '+key)
    if reviewer.get('method_disposition')!='evaluate_current_method':problems.append('method disposition not ready for current frozen implementation')
    return problems

def check(out=OUT,root=ROOT):
    manifest=json.loads((out/'review_input_manifest.json').read_text())
    seal=json.loads((out/'candidate_method_seal.json').read_text())
    issues=[];evidence=[]
    for name,h in seal['sha256'].items():
        p=root/name
        if not p.is_file() or sha(p)!=h:issues.append('sealed dependency changed: '+name)
    reviewer=json.loads((out/'reviewer.json').read_text());issues.extend(reviewer_issues(reviewer))
    path=submission(out,reviewer.get('disagreement_resolution_path',''))
    if path is None:issues.append('disagreement resolution note missing')
    else:evidence.append(path)
    pages=read_csv(out/'01_page_inventory.csv')
    if len(pages)!=6 or {r.get('page_key') for r in pages}!=set(manifest['page_hashes']):issues.append('page review identities changed')
    complete_pages=0
    for r in pages:
        if r.get('source_page_sha256')!=manifest['page_hashes'].get(r.get('page_key')):issues.append('page hash changed')
        p=submission(out,r.get('inventory_path',''))
        if p and r.get('source_first_confirmed')=='yes' and r.get('scope_and_coverage_notes'):
            complete_pages+=1;evidence.append(p)
    if complete_pages!=6:issues.append('source-first page inventories pending')
    scope=read_csv(out/'02_scope_decisions.csv')
    if len(scope)!=5 or {r.get('issue_id') for r in scope}!=set(manifest['scope_issues']):issues.append('scope question identities changed')
    complete_scope=sum(all(r.get(k) for k in ['decision','source_basis','unresolved_policy']) for r in scope)
    if complete_scope!=5:issues.append('scope decisions pending')
    candidates=read_csv(out/'03_candidate_review.csv')
    ids={r['review_id']:r for r in manifest['candidate_rows']}
    if len(candidates)!=22 or {r.get('review_id') for r in candidates}!=set(ids):issues.append('candidate review identities changed')
    complete_candidates=0
    for r in candidates:
        expected=ids.get(r.get('review_id'),{})
        if any(r.get(k)!=v for k,v in expected.items()):issues.append('candidate input modified: '+r.get('review_id',''))
        quality=['source_support','condition_complete','scope_appropriate']
        done=all(r.get(k) in {'yes','no','uncertain'} for k in quality) and r.get('final_verdict') in {'supported','unsupported','unresolved'} and r.get('source_quote_or_locator') and r.get('reason')
        if done and r['final_verdict']=='supported' and any(r[k]!='yes' for k in quality):issues.append('inconsistent supported verdict: '+r['review_id']);done=False
        complete_candidates+=bool(done)
    if complete_candidates!=22:issues.append('candidate reviews pending')
    references=read_csv(out/'04_reference_review.csv')
    if len(references)!=85 or {r.get('reference_id') for r in references}!=set(manifest['reference_ids']):issues.append('reference review identities changed')
    source_refs_path=root/'results/experiments/research_point_1/offline_contract_v3/reference_overlay.jsonl'
    source_refs={r['reference_id']:r for r in (json.loads(line) for line in source_refs_path.read_text().splitlines())}
    complete_references=0
    for r in references:
        expected=source_refs.get(r.get('reference_id'))
        if expected and (r.get('page_key')!=expected['page_key'] or r.get('proposed_reference_json')!=json.dumps(expected['v21_reference_unchanged'],ensure_ascii=False)):
            issues.append('reference input modified: '+r['reference_id'])
        done=r.get('verdict') in {'valid','invalid','needs_revision','unresolved'} and bool(r.get('reason'))
        if r.get('verdict') in {'valid','needs_revision'} and not r.get('corrected_statement_or_inventory_id'):done=False
        complete_references+=bool(done)
    if complete_references!=85:issues.append('reference comparison pending')
    counts=dict(source_pages=complete_pages,scope_decisions=complete_scope,candidates=complete_candidates,references=complete_references)
    return dict(status='READY_FOR_METHOD_FREEZE' if not issues else 'PENDING_INDEPENDENT_REVIEW',counts=counts,issues=issues,reviewer_identity_independently_verified=False,heldout_contents_opened_by_this_check=0),evidence

def load_selected(corpus,manifest):
    """Called only after the freeze gate, never by check()."""
    wanted={r['page_key']:r for r in manifest};found={}
    if len(wanted)!=len(manifest):raise ValueError('duplicate holdout identity')
    docs={key.split(':p')[0] for key in wanted}
    if not docs<=DOCS:raise ValueError('outside build corpus')
    for doc in sorted(docs):
        with (corpus/(doc+'.pages.v2.jsonl')).open() as stream:
            for line in stream:
                p=json.loads(line);key=f"{p['doc_id']}:p{p['pdf_page_number']:04d}"
                if key not in wanted:continue
                digest=hashlib.sha256(p['page_text'].encode()).hexdigest()
                if p['document_split']!='build_train' or p['doc_id']!=doc or digest!=wanted[key]['page_text_sha256'] or digest!=p['page_text_sha256']:raise ValueError('source hash/split mismatch: '+key)
                if key in found:raise ValueError('duplicate source page')
                found[key]=dict(p,page_key=key)
    if set(found)!=set(wanted):raise ValueError('missing frozen page')
    return [found[r['page_key']] for r in manifest]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--freeze',action='store_true');ap.add_argument('--prepare-heldout-sources',action='store_true');args=ap.parse_args()
    report,evidence=check();print(json.dumps(report,ensure_ascii=False,indent=2))
    if report['issues']:raise SystemExit(2)
    freeze=OUT/'formal_method_freeze.json'
    if args.freeze:
        paths=[OUT/name for name in ['reviewer.json','01_page_inventory.csv','02_scope_decisions.csv','03_candidate_review.csv','04_reference_review.csv','candidate_method_seal.json','holdout_plan.json','extraction_template.json']]+evidence+[Path(__file__)]
        save(freeze,dict(status='FROZEN_FOR_HELDOUT_EVALUATION_NOT_PUBLICATION',frozen_at=datetime.now(timezone.utc).isoformat(),sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},review_completeness=report,heldout_contents_opened=0))
    if args.prepare_holdout_sources:
        if not freeze.exists():raise SystemExit('Formal method freeze is missing; source contents remain unopened.')
        for name,digest in json.loads(freeze.read_text())['sha256'].items():
            if sha(ROOT/name)!=digest:raise SystemExit('Formal freeze changed: '+name)
        plan=json.loads((OUT/'holdout_plan.json').read_text());assert len(plan['pages'])==29
        target=OUT/'heldout_sources';target.mkdir(exist_ok=False)
        pages=load_selected(ROOT/'data/interim/parsed_pages/corpus_v2',plan['pages'])
        with (target/'source_only.jsonl').open('x',encoding='utf-8') as f:
            for p in pages:f.write(json.dumps(p,ensure_ascii=False)+'\n')
        save(target/'opening_record.json',dict(opened_at=datetime.now(timezone.utc).isoformat(),pages=29,formal_method_freeze_sha256=sha(freeze),purpose='independent source-first reference before candidate extraction',model_calls=0))
        print('Prepared 29 source-only pages. References and evaluation are still pending.')
if __name__=='__main__':main()
