#!/usr/bin/env python3
"""Mechanical source/schema checks and arm-masked review export; not accuracy or recall."""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/experiments/research_point_1'
PACKAGE=BASE/'adjudication_targeted_v2_1_qwen38_timeout180'
OUT=BASE/'targeted_api_review_v2_1'


def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
def sha(b):return hashlib.sha256(b).hexdigest()
def compact(s):return ''.join(s.split())
def dump(p,data):
 content=''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in data) if p.suffix=='.jsonl' else json.dumps(data,ensure_ascii=False,indent=2)+'\n'
 if p.exists():
  if p.read_text()!=content:raise ValueError(f'Refuse overwrite: {p}')
 else:
  with p.open('x',encoding='utf-8') as f:f.write(content)


def main():
 spec=importlib.util.spec_from_file_location('runner',ROOT/'scripts/run_rp1_targeted_v2_1.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
 protocol,requests=runner.check_package(PACKAGE)
 sources={x['page_key']:x for x in rows(PACKAGE/'pilot_sources.jsonl')}
 registry=json.loads((ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json').read_text())['relation_registry']
 outputs=[]
 for r in requests:
  meta=runner.request_state(PACKAGE/'api_run_001',r)
  if meta is None:raise ValueError('All twelve archived responses required before comparison')
  parsed=json.loads((PACKAGE/'api_run_001'/f"{r['request_id']}.parsed.json").read_text())
  outputs.append((r,meta,parsed))
 OUT.mkdir(exist_ok=True)
 # Mask arm identifiers in the review packet. This assistant has already seen execution counts;
 # this is not a fully blinded independent human review.
 outputs.sort(key=lambda x:sha(('RP1-v21-review-order-20261002:'+x[0]['payload_sha256']).encode()))
 checks=[];private=[];packets=[];summary=[]
 for n,(r,meta,parsed) in enumerate(outputs,1):
  bid=f'VR{n:02d}';p=sources[r['page_key']];cells={c['cell_id']:c for t in p['tables'] for row in t['rows'] for c in row['cells']}
  private.append({'review_id':bid,'request_id':r['request_id'],'arm':r['arm'],'page_key':r['page_key'],'response_sha256':sha((PACKAGE/'api_run_001'/f"{r['request_id']}.response.bin").read_bytes())})
  pc=[]
  for i,a in enumerate(parsed['assertions'],1):
   cid=f'{bid}:A{i:03d}';rel=registry.get(a['relation']);valid_type=bool(rel and a['head_type'] in rel['domain'] and a['tail_type'] in rel['range'])
   ids=a['evidence_unit_ids'];valid_ids=all(x in cells for x in ids)
   e=a['evidence_text'];exact=bool(e and e in p['page_text']);space=bool(e and compact(e) in compact(p['page_text']))
   native_exact=bool(ids and valid_ids and any(e==cells[x]['text'] for x in ids));native_space=bool(ids and valid_ids and any(compact(e)==compact(cells[x]['text']) for x in ids))
   binding='exact_page_span' if exact else 'whitespace_only_page_span' if space else 'exact_native_cell' if native_exact else 'whitespace_only_native_cell' if native_space else 'not_single_verbatim_span_or_cell'
   same_row=len({cells[x]['row_id'] for x in ids if x in cells and cells[x]['row_index']!=0})<=1
   row={'candidate_review_id':cid,'review_id':bid,'page_key':r['page_key'],'scope':a['scope'],'relation':a['relation'],'core_diagnostic_relation':bool(rel and rel['core_diagnostic_relation']),'type_direction_valid':valid_type,'quote_binding':binding,'evidence_unit_ids_valid':valid_ids,'native_cells_same_nonheader_row':same_row,'semantic_support':'not_inferred_from_mechanical_checks','expert_review':'pending'}
   checks.append(row);pc.append({'candidate_review_id':cid,**a,'mechanical':{k:v for k,v in row.items() if k not in ['candidate_review_id','review_id','page_key']}})
  packets.append({'review_id':bid,'page_key':r['page_key'],'source_page_sha256':p['page_text_sha256'],'source_file':'../adjudication_targeted_v2_1/pilot_sources.jsonl','assertions':pc,'auxiliary':parsed['auxiliary'],'unresolved':parsed['unresolved'],'review_status':'pending_ai_technical_review_and_independent_expert_review'})
  own=[x for x in checks if x['review_id']==bid]
  primary=[x for x in own if x['scope']=='primary'];core=[x for x in primary if x['core_diagnostic_relation']]
  summary.append({'review_id':bid,'request_id':r['request_id'],'arm':r['arm'],'page_key':r['page_key'],'assertions':len(own),'scope_counts':dict(Counter(x['scope'] for x in own)),'primary_core':len(core),'primary_core_type_valid':sum(x['type_direction_valid'] for x in core),'primary_core_type_invalid':sum(not x['type_direction_valid'] for x in core),'quote_binding_all_assertions':dict(Counter(x['quote_binding'] for x in own)),'primary_core_unbound_quote':sum(x['quote_binding']=='not_single_verbatim_span_or_cell' for x in core),'invalid_cell_references':sum(not x['evidence_unit_ids_valid'] for x in own),'auxiliary':len(parsed['auxiliary']),'unresolved':len(parsed['unresolved']),'model':meta['returned_model'],'finish_reason':meta['finish_reason'],'usage':meta['usage']})
 dump(OUT/'private_arm_mapping.jsonl',private);dump(OUT/'mechanical_checks.jsonl',checks);dump(OUT/'arm_masked_review_packets.jsonl',packets);dump(OUT/'mechanical_summary.jsonl',summary)
 dump(OUT/'freeze.json',{'stage':'after_response_archive_before_AI_semantic_review','script_sha256':sha(Path(__file__).read_bytes()),'source_request_freeze_sha256':sha((PACKAGE/'request_freeze.json').read_bytes()),'all_twelve_responses_archived':True,'review_limit':'arm labels masked; operational counts already seen by same assistant; not independent expert review','expert_review':'pending','formal_accuracy_recall':'not_computed','sha256':{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in OUT.iterdir() if p.is_file() and p.name!='freeze.json'}})
 print(json.dumps({'responses':len(outputs),'assertions':len(checks),'type_invalid':sum(not x['type_direction_valid'] for x in checks),'single_quote_not_bound':sum(x['quote_binding']=='not_single_verbatim_span_or_cell' for x in checks),'formal_accuracy_recall':'not_computed'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
