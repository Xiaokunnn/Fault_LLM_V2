#!/usr/bin/env python3
"""Post-generation AI source adjudication; never imported by the runtime."""
from collections import Counter
from rp1_offline_contract_v3 import *
from run_rp1_clause_binding_v1 import OUT, PARENT
V3=BASE/'offline_contract_v3'
# These six statements were inspected after the frozen generation. They are
# disclosed same-assistant development annotations, not independent experts.
VERDICTS={
 'VR06:A007':('complete','Otherwise在同段唯一绑定许可范围；两个上界与标准泵限定完整保存，风险使用possible，不把上界当正向触发条件。'),
 'VR06:A008':('complete','原超限OR条件已正确，本轮保留并附整段许可范围的否定；语义仍完整。F会误拒此本来正确记录，必须计入损失。'),
 'VR08:A006':('complete','完整原句支持关阀运行超出许可范围时的损坏风险，限制及标准泵条件未弱化；模态改为possible。'),
 'VR08:A007':('complete','Otherwise通过相邻唯一源段补回许可范围；爆炸保持风险模态，没有改成必然发生或双条件同时超限。'),
 'VR08:A012':('complete','原候选的完整检查宾语唯一对应轴检查项；原错误relief valve改为shaft；启动前语境保留。'),
 'VR08:A013':('complete','原检查宾语唯一对应灌液检查项，恢复pump casing；解除旧多对象屏障，没有误绑定到shaft。'),
}

def main():
    if (OUT/'summary.json').exists():raise SystemExit('Existing evaluation preserved; no overwrite.')
    outputs=[dict(d,stage='B') for d in rows(PARENT/'automatic_outputs.jsonl') if d['stage']=='P1']+rows(OUT/'outputs.jsonl')
    prior={r['candidate_review_id']:r for r in rows(PARENT/'AI_source_review_466.jsonl') if r['stage']=='P1'}
    parent={d['candidate_review_id']:d for d in outputs if d['stage']=='B'}
    old={r['candidate_review_id']:r for r in rows(V3/'candidate_adjudications.jsonl')}
    review=[];events=[]
    for d in outputs:
        cid=d['candidate_review_id']; prev=prior[cid]
        status=prev['AI_contract_status']; reason='未改语义，复用冻结v4.1技术标签。'
        if d['stage']=='R' and d['clause_binding']['outcome']=='repaired':
            assert cid in VERDICTS,'New changed output requires explicit source review'
            status,reason=VERDICTS[cid]
        elif d['stage']!='B' and d['clause_binding']['issues']:
            assert d['payload']==parent[cid]['payload'],'A changed payload needs its own adjudication'
            reason='仅改变是否保留，语义标签不变；原文及候选全部保存。'
        else:
            assert d['payload']==parent[cid]['payload']
        r=dict(stage=d['stage'],candidate_review_id=cid,prompt_arm=d['prompt_arm'],page_key=d['page_key'],
               AI_contract_status=status,reason_zh=reason,output_sha256=object_sha(d['payload']),
               reviewer='same_assistant_not_blinded_not_independent_expert',expert_review='pending',evaluation_only=True)
        review.append(r)
        if d['stage']!='B' and d['clause_binding']['issues']:
            events.append(dict(**r,before_included=parent[cid]['included'],after_included=d['included'],
                               before=parent[cid]['payload'],after=d['payload'],source_witnesses=d['source_witnesses']))
    write(OUT/'AI_review.jsonl',review);write(OUT/'changed_record_review.jsonl',events)
    write(OUT/'evaluation_freeze.json',dict(stage='source review frozen before aggregate quality metrics',
        sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),OUT/'outputs.jsonl',OUT/'AI_review.jsonl',
            PARENT/'AI_source_review_466.jsonl',V3/'reference_overlay.jsonl',V3/'reference_match_annotations.jsonl',V3/'candidate_adjudications.jsonl']},
        expert_review='pending'))
    rr={(r['stage'],r['candidate_review_id']):r for r in review}
    ds={(d['stage'],d['candidate_review_id']):d for d in outputs}
    refs={r['reference_id']:r for r in rows(V3/'reference_overlay.jsonl')}
    matches=[]
    for stage in ['B','F','R']:
        group=[]
        for seed in rows(V3/'reference_match_annotations.jsonl'):
            ref=refs[seed['reference_id']]; expected=ref['v21_reference_unchanged']; eligible=[]
            for cid in seed['candidate_review_ids']:
                d=ds[(stage,cid)];a=d['payload']
                same=a['relation']==expected['relation']
                if seed['relation_equivalence']=='risk_causes_equivalent_increases_risk_of':same=a['relation'] in ['causes','increases_risk_of']
                partial=seed['relation_equivalence'] in ['generic_replacement_only_partial','embedded_text_only_partial']
                if d['included'] and channel(a)=='core' and rr[(stage,cid)]['AI_contract_status']=='complete' and same and not partial:eligible.append(cid)
            group.append(dict(stage=stage,reference_id=seed['reference_id'],prompt_arm=seed['prompt_arm'],page_key=expected['page_key'],
                              reference_channel=ref['v3_evaluation_channel'],eligible_full_candidates=eligible,state='not_full'))
        for arm in ['E0','E1']:
            subset=[m for m in group if m['prompt_arm']==arm and m['reference_channel']=='core']
            allocation=maximum_matching({m['reference_id']:m['eligible_full_candidates'] for m in subset})
            for m in subset:
                if m['reference_id'] in allocation:m.update(state='full',allocated_candidate_id=allocation[m['reference_id']])
        matches.extend(group)
    summaries=[];pages=[]
    for stage in ['B','F','R']:
        for arm in ['E0','E1']:
            subset=[d for d in outputs if d['stage']==stage and d['prompt_arm']==arm]
            selected=[d for d in subset if d['included']]
            core_records=[d for d in selected if channel(d['payload'])=='core']
            status=lambda d:rr[(stage,d['candidate_review_id'])]['AI_contract_status']
            good=[d for d in core_records if status(d)=='complete']
            problems=[d for d in core_records if status(d) not in ['complete','unresolved']]
            unknown=[d for d in core_records if status(d)=='unresolved']
            original_good=[d for d in subset if channel(old[d['candidate_review_id']]['original'])=='core' and old[d['candidate_review_id']]['original_contract_status']=='complete']
            lost=[d for d in original_good if d not in good]
            newly_corrupted=[d for d in lost if d['included'] and status(d) not in ['complete','unresolved']]
            mm=[m for m in matches if m['stage']==stage and m['prompt_arm']==arm and m['reference_channel']=='core']
            s=dict(stage=stage,prompt_arm=arm,inputs=len(subset),included_all_channels=len(selected),complete_core_records=len(good),
                   complete_core_exact_unique=len({exact_key(d['payload']) for d in good}),problem_core_released=len(problems),
                   unresolved_core_released=len(unknown),correct_core_lost=len(lost),correct_core_lost_ids=[d['candidate_review_id'] for d in lost],
                   newly_corrupted_correct_core_released=len(newly_corrupted),full_reference_matches=sum(m['state']=='full' for m in mm),
                   reference_denominator=len(mm),problem_outside_core_released=sum(channel(d['payload'])!='core' and status(d) not in ['complete','unresolved'] for d in selected),
                   formal_accuracy_recall='not_computed')
            assert s['reference_denominator']==79
            summaries.append(s)
            for page in sorted({r['page_key'] for r in refs.values()}):
                pm=[m for m in mm if m['page_key']==page]
                pages.append(dict(stage=stage,prompt_arm=arm,page_key=page,full_reference_matches=sum(m['state']=='full' for m in pm),
                                  reference_denominator=len(pm),complete_core_records=sum(d['page_key']==page for d in good)))
    old_summary={s['prompt_arm']:s for s in json.loads((PARENT/'summary.json').read_text()) if s['stage']=='P1'}
    for s in summaries:
        if s['stage']=='B':
            for key in ['complete_core_records','problem_core_released','unresolved_core_released','correct_core_lost','full_reference_matches']:
                assert s[key]==old_summary[s['prompt_arm']][key],key
    by={(s['stage'],s['prompt_arm']):s for s in summaries};gates=[]
    for arm in ['E0','E1']:
        b,f,r=(by[(stage,arm)] for stage in ['B','F','R'])
        errors=lambda s:s['problem_core_released']+s['unresolved_core_released']
        checks=dict(quantity_vs_B=r['complete_core_exact_unique']>=b['complete_core_exact_unique'],coverage_vs_B=r['full_reference_matches']>=b['full_reference_matches'],
                    errors_vs_B=errors(r)<=errors(b),correct_loss_vs_B=r['correct_core_lost']<=b['correct_core_lost'],
                    no_new_correct_corruption=r['newly_corrupted_correct_core_released']==0,
                    quantity_vs_F=r['complete_core_exact_unique']>f['complete_core_exact_unique'],errors_vs_F=errors(r)<=errors(f))
        gates.append(dict(prompt_arm=arm,checks=checks,status='PASS' if all(checks.values()) else 'FAIL'))
    write(OUT/'summary.json',summaries);write(OUT/'page_summary.jsonl',pages);write(OUT/'reference_matches.jsonl',matches)
    write(OUT/'development_gate.json',dict(arms=gates,formal_promotion='NOT_ESTABLISHED',independent_expert_review='pending',heldout_pages_opened=0))
    print(json.dumps(dict(summary=summaries,development_gate=gates),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
