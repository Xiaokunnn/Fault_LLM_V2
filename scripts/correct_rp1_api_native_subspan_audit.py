#!/usr/bin/env python3
"""Correct native-cell subspan binding only; retain the original mechanical audit."""
import hashlib
import json
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/experiments/research_point_1'
OUT=BASE/'targeted_api_review_v2_1'


def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
 data=''.join(json.dumps(a,ensure_ascii=False)+'\n' for a in x) if p.suffix=='.jsonl' else json.dumps(x,ensure_ascii=False,indent=2)+'\n'
 if p.exists():
  assert p.read_text()==data,('Refuse overwrite',p)
 else:
  with p.open('x',encoding='utf-8') as f:f.write(data)


def source_subspan(source,quote):
    if not quote or not quote.strip():return None
    pos=[i for i,c in enumerate(source) if not c.isspace()]
    flat=''.join(source[i] for i in pos);q=''.join(quote.split());i=flat.find(q)
    if i<0:return None
    start,end=pos[i],pos[i+len(q)-1]+1
    return {'start':start,'end':end,'source_text':source[start:end],'only_whitespace_normalized':source[start:end]!=quote}


def main():
 sources={x['page_key']:x for x in rows(BASE/'adjudication_targeted_v2_1/pilot_sources.jsonl')}
 candidates={a['candidate_review_id']:a for p in rows(OUT/'arm_masked_review_packets.jsonl') for a in p['assertions']}
 checks=rows(OUT/'mechanical_checks.jsonl');changes=[]
 for x in checks:
  if x['quote_binding']!='not_single_verbatim_span_or_cell':continue
  a=candidates[x['candidate_review_id']];p=sources[x['page_key']];cells={c['cell_id']:c for t in p['tables'] for row in t['rows'] for c in row['cells']}
  for cid in a['evidence_unit_ids']:
   if cid not in cells:continue
   match=source_subspan(cells[cid]['text'],a['evidence_text'])
   if match:
    changes.append({'candidate_review_id':x['candidate_review_id'],'before':x['quote_binding'],'after':'whitespace_only_native_subspan' if match['only_whitespace_normalized'] else 'exact_native_subspan','cell_id':cid,'cell_relative_witness':match,'reason':'Initial checker incorrectly required the quote to equal the whole native cell, while an unchanged source subspan is locatable.'})
    x['quote_binding']=changes[-1]['after'];break
 assert {x['candidate_review_id'] for x in changes}=={'VR07:A004','VR07:A016'}
 # Negative checks: no removal of punctuation, word edits, or concatenation across disjoint source text.
 assert source_subspan('alpha beta gamma','alpha gamma') is None
 assert source_subspan('misalignment.','alignment!') is None
 assert source_subspan('Poor\nlubrication.','Poor lubrication.') is not None
 summary=rows(OUT/'mechanical_summary.jsonl')
 for s in summary:
  own=[x for x in checks if x['review_id']==s['review_id']]
  s['quote_binding_all_assertions']=dict(Counter(x['quote_binding'] for x in own))
  s['primary_core_unbound_quote']=sum(x['quote_binding']=='not_single_verbatim_span_or_cell' and x['scope']=='primary' and x['core_diagnostic_relation'] for x in own)
 write(OUT/'mechanical_checks_corrected.jsonl',checks);write(OUT/'mechanical_summary_corrected.jsonl',summary)
 write(OUT/'native_subspan_correction.json',{'correction_scope':'source binding statistics only; no model output/reference/gate change','changes':changes,'code_sha256':digest(Path(__file__)),'prior_audit_preserved':True,'semantic_support_not_inferred':True,'extra_api_calls':0})
 print(json.dumps({'corrected_records':len(changes),'remaining_nonverbatim_quotes':sum(x['quote_binding']=='not_single_verbatim_span_or_cell' for x in checks),'negative_checks':'passed'},ensure_ascii=False))


if __name__=='__main__':main()
