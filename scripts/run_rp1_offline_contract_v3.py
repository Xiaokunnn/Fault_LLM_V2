#!/usr/bin/env python3
"""Replay three offline arms; C is an explicitly authored AI edit ledger, not learned inference."""
from collections import Counter
from rp1_offline_contract_v3 import *

def evaluate():
    freeze=json.loads((OUT/'adjudication_freeze.json').read_text())
    for name,digest in freeze['sha256'].items():assert sha(ROOT/name)==digest,name
    pages={p['page_key']:p for p in rows(SOURCE/'pilot_sources.jsonl')}
    annotations=rows(OUT/'candidate_adjudications.jsonl');lookup={a['candidate_review_id']:a for a in annotations}
    refs={r['reference_id']:r for r in rows(OUT/'reference_overlay.jsonl')}
    decisions=[];index={}
    for stage in ['A_raw','B_filter','C_source_edit']:
        for a in annotations:
            cid=a['candidate_review_id'];original=a['original'];flags=[];included=True
            if stage=='B_filter': flags=filter_flags(original,pages[a['page_key']]);included=not flags
            payload=a['proposal'] if stage=='C_source_edit' else original
            if payload is None:included=False
            status=a['proposal_status'] if stage=='C_source_edit' else a['original_contract_status']
            d={'stage':stage,'prompt_arm':a['prompt_arm'],'page_key':a['page_key'],'candidate_review_id':cid,
               'included':included,'filter_flags':flags,'payload':payload,'AI_contract_status':status,
               'expert_review':'pending','source_original_sha256':a['original_sha256']}
            decisions.append(d);index[(stage,cid)]=d
    matches=[]
    for stage in ['A_raw','B_filter','C_source_edit']:
        prelim=[]
        for seed in rows(OUT/'reference_match_annotations.jsonl'):
            r=refs[seed['reference_id']];kind=r['v3_evaluation_channel'];rr=r['v21_reference_unchanged']
            eligible=[];failures={}
            for cid in seed['candidate_review_ids']:
                d=index[(stage,cid)];a=d['payload'];why=[]
                if not d['included']:why.append('filtered_or_unresolved')
                elif a is None:why.append('unresolved')
                else:
                    if d['AI_contract_status']!='complete':why.append(d['AI_contract_status'])
                    if a['scope']!='primary':why.append('scope_not_primary_but_text_may_be_present')
                    if a.get('record_kind'):why.append('sidecar_not_core_edge')
                    eq=seed['relation_equivalence']
                    same=a['relation']==rr['relation']
                    if eq=='risk_causes_equivalent_increases_risk_of':same=a['relation'] in ['causes','increases_risk_of']
                    if not same:why.append('relation_not_equivalent')
                    if eq in ['generic_replacement_only_partial','embedded_text_only_partial']:why.append(eq)
                if not why:eligible.append(cid)
                failures[cid]=why
            state='candidate_for_full' if eligible else 'partial' if seed['candidate_review_ids'] else 'present_in_auxiliary' if seed['auxiliary_locations'] else 'not_found'
            if kind!='core':state=kind
            prelim.append({'stage':stage,'reference_id':rr['reference_id'],'page_key':rr['page_key'],'prompt_arm':seed['prompt_arm'],
              'reference_channel':kind,'state':state,'candidate_review_ids':seed['candidate_review_ids'],
              'eligible_full_candidates':eligible,'candidate_limitations':failures,'auxiliary_locations':seed['auxiliary_locations'],
              'review_kind':'AI_technical_not_formal_recall','reason_zh':r['v3_note_zh']})
        for prompt in ['E0','E1']:
            for page in pages:
                group=[m for m in prelim if m['prompt_arm']==prompt and m['page_key']==page and m['reference_channel']=='core']
                assignment=maximum_matching({m['reference_id']:m['eligible_full_candidates'] for m in group})
                for m in group:
                    if m['reference_id'] in assignment:m.update(state='full',allocated_candidate_id=assignment[m['reference_id']])
                    elif m['eligible_full_candidates']:m.update(state='partial_composite_capacity',reason_zh=m['reason_zh']+' 同一复合候选已分配另一参考，本项不能重复计完整覆盖。')
        matches.extend(prelim)
    summaries=[];page_summaries=[]
    for stage in ['A_raw','B_filter','C_source_edit']:
        for prompt in ['E0','E1']:
            ds=[d for d in decisions if d['stage']==stage and d['prompt_arm']==prompt]
            selected=[d for d in ds if d['included']]
            pcs=[d for d in selected if channel(d['payload'])=='core' and d['payload']['scope']=='primary']
            good=[d for d in pcs if d['AI_contract_status']=='complete']
            problem=[d for d in pcs if d['AI_contract_status'] not in ['complete','unresolved']]
            original_good=[d for d in ds if channel(lookup[d['candidate_review_id']]['original'])=='core' and lookup[d['candidate_review_id']]['original_contract_status']=='complete']
            lost=[d for d in original_good if not d['included'] or channel(d['payload'])!='core' or d['AI_contract_status']!='complete']
            mm=[m for m in matches if m['stage']==stage and m['prompt_arm']==prompt]
            macro=[]
            for page in pages:
                pm=[m for m in mm if m['page_key']==page and m['reference_channel']=='core'];n=len(pm);k=sum(m['state']=='full' for m in pm)
                if n:macro.append(k/n)
                page_summaries.append({'stage':stage,'prompt_arm':prompt,'page_key':page,'core_reference_denominator':n,'full':k,
                    'fraction':k/n if n else None,'state_counts':dict(Counter(m['state'] for m in mm if m['page_key']==page)),
                    'AI_complete_core_records':sum(d['page_key']==page for d in good)})
            summaries.append({'stage':stage,'prompt_arm':prompt,'input_records':len(ds),'included_records_all_channels':len(selected),
                'primary_core_records_released':len(pcs),'AI_complete_core_records':len(good),
                'AI_complete_core_exact_text_unique':len({exact_key(d['payload']) for d in good}),
                'known_problem_core_records_released':len(problem),'known_problem_breakdown':dict(Counter(d['AI_contract_status'] for d in problem)),
                'unresolved_core_records_released':sum(d['AI_contract_status']=='unresolved' for d in pcs),
                'correct_complete_core_rejected_or_lost':len(lost),'correct_complete_core_lost_ids':[d['candidate_review_id'] for d in lost],
                'source_kernel_records_withheld':sum(not d['included'] and lookup[d['candidate_review_id']]['source_supported_knowledge_kernel'] for d in ds),
                'included_channel_counts':dict(Counter(channel(d['payload']) for d in selected)),
                'scope_reclassified_background_to_primary':sum(d['payload']['scope']=='primary' and lookup[d['candidate_review_id']]['original']['scope']=='background' for d in selected),
                'core_from_original_noncore':sum(not core(lookup[d['candidate_review_id']]['original']) for d in good),
                'core_full_reference_matches':sum(m['state']=='full' for m in mm),'core_reference_denominator':79,
                'five_positive_page_macro_fraction':sum(macro)/len(macro),'pages_with_full_core_match':sum(any(m['state']=='full' and m['page_key']==p for m in mm) for p in pages),
                'reference_state_counts_all_85':dict(Counter(m['state'] for m in mm)),
                'formal_accuracy_recall':'not_computed','independent_C_error_rate':'unknown'})
    return decisions,matches,summaries,page_summaries

def main():
    # Freeze the runner before computing any arm effects. Metrics do not select a new epoch/rule.
    write(OUT/'arm_execution_freeze.json',{'runner_sha256':sha(Path(__file__)),'adjudication_freeze_sha256':sha(OUT/'adjudication_freeze.json'),
        'C_arm':'AI editorial source repair replay, not autonomous algorithm','independent_postrepair_validation':'pending','new_API_calls':0})
    d,m,s,p=evaluate()
    assert len(d)==699 and len(m)==510 and len(s)==6 and len(p)==36
    write(OUT/'arm_decisions.jsonl',d);write(OUT/'reference_matches_510.jsonl',m)
    write(OUT/'summary.json',s);write(OUT/'page_summary.jsonl',p)
    write(OUT/'unresolved_candidates.jsonl',[a for a in rows(OUT/'candidate_adjudications.jsonl') if a['original_contract_status']=='unresolved'])
    write(OUT/'stage_gate.json',{'decision':'NOT_READY_FOR_HOLDOUT_OR_SCALING','offline_three_arm_development_audit':'completed',
        'operational_dispute_convention':'v3 technical convention fixed, independent expert approval pending',
        'independent_expert_review':'pending','source_reference_exhaustiveness':'not_confirmed','automated_general_source_repair':'not_implemented',
        'heldout_page_contents_opened':0,'new_API_calls':0,'new_published_graph_records':0,
        'next':'Automate bounded source-context/role repair without candidate-ID or annotation lookup; freeze joint quantity-quality gates and independent source-first review before reserved-page evaluation.'})
    print(json.dumps(s,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
