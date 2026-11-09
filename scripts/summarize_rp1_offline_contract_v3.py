#!/usr/bin/env python3
"""Readable audit views and declared post-hoc scope sensitivity; no rule tuning."""
from collections import Counter
from rp1_offline_contract_v3 import *

def put_text(path, text):
    if path.exists():assert path.read_text()==text,('refuse overwrite',path)
    else:
        with path.open('x') as f:f.write(text)

def main():
    ledger=rows(OUT/'candidate_adjudications.jsonl');lookup={x['candidate_review_id']:x for x in ledger}
    matches=rows(OUT/'reference_matches_510.jsonl');packets={p['review_id']:p for p in rows(REVIEW/'arm_masked_review_packets.jsonl')}
    decisions=rows(OUT/'arm_decisions.jsonl')
    sensitivity=[]
    for arm in ['E0','E1']:
        mm=[m for m in matches if m['stage']=='C_source_edit' and m['prompt_arm']==arm and m['reference_channel']=='core']
        edges={m['reference_id']:[cid for cid in m['eligible_full_candidates'] if lookup[cid]['original']['scope']=='primary'] for m in mm}
        assign=maximum_matching(edges)
        ds=[d for d in decisions if d['stage']=='C_source_edit' and d['prompt_arm']==arm and d['included'] and channel(d['payload'])=='core']
        sensitivity.append({'prompt_arm':arm,'analysis_type':'posthoc descriptive contribution separation, no model/rule selection',
            'C_full_matches_if_original_scope_is_held_fixed':len(assign),'denominator':79,
            'C_complete_core_records_if_original_scope_is_held_fixed':sum(lookup[d['candidate_review_id']]['original']['scope']=='primary' for d in ds),
            'C_complete_core_records_excluding_MP018':sum(d['page_key']!='MP018:p0026' for d in ds),
            'scope_promotions':sum(lookup[d['candidate_review_id']]['original']['scope']=='background' for d in ds)})
    write(OUT/'scope_sensitivity.json',sensitivity)
    # Match the original 18 auxiliary/source-reference entries to saved response positions.
    aux_map={
      'MP004:p0010':[
        (['VR08:A003','VR08:A004','VR08:A005'],['VR06:A003','VR06:A004','VR06:A005','VR06:A006']),
        (['VR08:A009','VR08:A010','VR08:auxiliary:001','VR08:auxiliary:002'],['VR06:A010','VR06:A011','VR06:A013','VR06:auxiliary:001']),
        (['VR08:A027','VR08:auxiliary:004'],['VR06:A028','VR06:auxiliary:003'])],
      'MP007:p0012':[
        (['VR05:A001'],['VR11:A001']),
        (['VR05:A007','VR05:A008','VR05:A009','VR05:auxiliary:002'],['VR11:A006','VR11:A007','VR11:auxiliary:002','VR11:auxiliary:003']),
        (['VR05:auxiliary:003'],['VR11:A014']),
        (['VR05:A016','VR05:A017'],['VR11:auxiliary:004'])],
      'MP007:p0015':[
        (['VR01:A003'],['VR10:A004']),(['VR01:A004'],['VR10:A005']),(['VR01:A005'],['VR10:A007']),
        (['VR01:auxiliary:001'],['VR10:A003']),
        (['VR01:A008','VR01:A009','VR01:A010','VR01:A011'],['VR10:A014','VR10:A016']),
        (['VR01:A017'],['VR10:A001','VR10:A002','VR10:auxiliary:001'])],
      'MP018:p0026':[(['VR07:A023'],['VR03:auxiliary:002'])],
      'MP002:p0089':[
        (['VR09:auxiliary:001'],[f'VR02:A{i:03d}' for i in range(1,6)]),
        (['VR09:auxiliary:002'],['VR02:A006']),(['VR09:auxiliary:003'],['VR02:A007']),(['VR09:auxiliary:004'],['VR02:A008'])]
    }
    auxiliary=[]
    for r in rows(SOURCE/'auxiliary_and_unresolved.jsonl'):
        i=int(r['item_id'][-3:])-1
        for arm,ls in zip(['E0','E1'],aux_map[r['page_key']][i]):
            state='content_present_requires_semantic_review'
            if r['page_key']=='MP007:p0015' and i==4 and arm=='E0':state='partial_structural_edges_only_mechanism_not_encoded'
            if r['page_key']=='MP007:p0015' and i==5 and arm=='E0':state='partial_60Hz_permission_only_parameter_change_not_encoded'
            if r['page_key']=='MP007:p0012' and i==2:state='unresolved_source_method'
            for loc in ls:
                if ':A' in loc:assert loc in lookup
                else:
                    v,k,n=loc.split(':');assert 1<=int(n)<=len(packets[v][k])
            auxiliary.append({'auxiliary_reference_id':r['item_id'],'prompt_arm':arm,'response_locations':ls,'technical_match_state':state,
              'counted_in_core_denominator':False,'expert_review':'pending','not_complete_exhaustive_reference':True})
    assert len(auxiliary)==36
    write(OUT/'auxiliary_reference_matches_36.jsonl',auxiliary)
    # All edited fields, source offset witnesses and alternatives remain in the JSON ledger.
    lines=['# 233 条源文技术裁定与修复账本\n\n同一助手、非盲技术编修；不是专家准确率标签。完整字段与原生定位见 `candidate_adjudications.jsonl`。\n']
    for a in ledger:
        o=a['original'];p=a['proposal']
        lines.append(f"\n## {a['candidate_review_id']} · {a['prompt_arm']} · {a['page_key']}\n\n原始：{flat(o['head_surface'])} — {o['relation']} → {flat(o['tail_surface'])}\n\n裁定：{a['original_contract_status']}。{a['reason_zh']}\n")
        if p is None:lines.append('\n修复：未决隔离；原文和记录保留。\n')
        elif p.get('record_kind'):lines.append(f"\n修复：转 `{p['record_kind']}` 旁路；要求={p.get('requirement','见原文及条件')}。\n")
        else:lines.append(f"\n修复：{flat(p['head_surface'])} — {p['relation']} → {flat(p['tail_surface'])}\n\n条件：{json.dumps(p['conditions'],ensure_ascii=False)}\n")
        lines.append('\n证据：\n\n')
        for w in a['source_witnesses']:
            basis=w.get('cell_id','page_text');lines.append(f"- `{basis}[{w['start']}:{w['end']}]`：{flat(w['text'])}\n")
    put_text(OUT/'candidate_review.md',''.join(lines))
    ref_lines=['# 原 85 项参考的六列离线匹配\n\n保留全部原始参考；3项操作、3项未决，核心分母79。full为技术匹配，非正式召回。\n\n| 参考 | 通道 | A E0 | B E0 | C E0 | A E1 | B E1 | C E1 |\n|---|---|---|---|---|---|---|---|\n']
    for ref in rows(OUT/'reference_overlay.jsonl'):
        states=[]
        for arm in ['E0','E1']:
            for stage in ['A_raw','B_filter','C_source_edit']:
                m=next(x for x in matches if x['reference_id']==ref['reference_id'] and x['prompt_arm']==arm and x['stage']==stage)
                states.append(m['state']+((' '+m['allocated_candidate_id']) if m['state']=='full' else ''))
        ref_lines.append('| '+ref['reference_id']+' | '+ref['v3_evaluation_channel']+' | '+' | '.join(states)+' |\n')
    put_text(OUT/'reference_review.md',''.join(ref_lines))
    meta={'edited_candidate_records':sum(bool(x['changes']) for x in ledger),'unchanged_candidate_records':sum(not x['changes'] and x['proposal'] is not None for x in ledger),
          'unresolved_candidate_records':sum(x['proposal'] is None for x in ledger),
          'status_counts_all_233':dict(Counter(x['original_contract_status'] for x in ledger)),
          'scope_sensitivity':sensitivity,'auxiliary_reference_pairs':36,
          'formal_accuracy_recall':'not_computed','expert_review':'pending'}
    write(OUT/'review_completion.json',meta)
    print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
