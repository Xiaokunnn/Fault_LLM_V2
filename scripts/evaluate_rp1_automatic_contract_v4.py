#!/usr/bin/env python3
"""Separate, disclosed AI source review of frozen automatic outputs; not runtime code."""
from collections import Counter
import sys
from rp1_offline_contract_v3 import *
V3=BASE/'offline_contract_v3'

def labels(outputs,corrected=False):
    old={x['candidate_review_id']:x for x in rows(V3/'candidate_adjudications.jsonl')}
    reviewed=[]
    # These are evaluation-only source-review annotations, never imported by inference.
    shared={}
    def assign(v,ns,status,reason):
        for n in ns:shared[f'VR{v:02d}:A{n:03d}']=(status,reason)
    for v in [3,7]:assign(v,range(1,30 if v==3 else 31),'complete','逐行核对原生表；有泵型限定的范围、列模态和更换例外得到保留；范围变化不是新抽取。')
    assign(4,[1,2,3,4,6,7,8,9,10,13,14,15,16,17,19,21,22,23,24,25],'complete','逐条源步骤复核：章节、轴承架/材料、编号、前提和步骤内交叉引用已恢复。')
    assign(12,[1,2,3,4,5,7,8,11,12],'complete','源步骤与章节吻合，动作/条件完整；不把该步骤作为完整维修程序。')
    assign(12,[9,10],'incomplete','从位置关系转为维护动作后仍保留 descriptive/possible，未明确表达条件成立时的程序要求；不能仅凭补足步骤就判完整。v3 C 同样残留此问题，其旧文件保留。')
    for v,ns in [(1,[3,4,5]),(10,[4,5,7,14,16]),(5,[8,9,15]),(6,[12]),(8,[11])]:
        assign(v,ns,'complete','已转入源文支持的负向要求/机理/运行操作/交叉引用旁路，不强计正向核心边。')
    for v,ns in [(1,[6,7,13]),(10,[9,10,18])]:
        assign(v,ns,'complete','保养前停机及润滑段部件范围补全，原条件保持；防冻措施有效但不同关系不强配 maintained_by 参考。')
    assign(11,[11],'complete' if corrected else 'semantic_error',
           '补丁阻止是否检查句变为执行前提；原双项管路检查内容保留。' if corrected else '新增 If ... or not 条件把是否检查误当已满足前提，原本正确核心记录被错误约束。')
    for d in outputs:
        cid=d['candidate_review_id'];prev=old[cid];status=prev['original_contract_status'];reason='未解决的原问题沿用 v3 裁定；原本完整的未变语义保持原标签。'
        if cid in shared:status,reason=shared[cid]
        if d['stage']=='P1':
            role_good={'VR05:A010','VR05:A011','VR05:A012','VR05:A013','VR05:A014','VR06:A014','VR06:A015','VR11:A013','VR10:A025','VR10:A026','VR10:A021'}
            if cid in role_good:status='complete';reason='逐条源文复核：受检对象/方法或维护目的与动作得到正确绑定；排液通道转存辅助程序，不算检查边。'
            if cid in {'VR06:A016','VR08:A014'}:
                status='complete' if corrected else 'incomplete';reason='旋向与箭头一致才继续启动的条件完整保留。' if corrected else 'i.e. 被句点截断，条件仅剩 If the direction is correct (i.，未完整保存箭头一致要求。'
            if cid=='VR08:A012':status='unresolved';reason='引用含两个检查对象，程序不做唯一绑定，已隔离；未计修复成功。'
            if cid=='VR08:A013':status='semantic_error';reason='原本正确的灌液检查被尝试改成轴检查，非唯一绑定屏障已隔离；计原本正确知识误拒，不计放行新损坏。'
            if cid in {'VR01:A014','VR10:A020'}:status='incomplete';reason='排液关系已修正，但尚未补入源段的排液通道和冷热排液安全条件；不计条件完整参考。'
            if cid=='VR10:A024':status='incomplete';reason='已转恢复运行旁路，但继承了面向维护的停机条件，未准确限定前述排液后恢复使用语境；旁路问题另报。'
        reviewed.append({'stage':d['stage'],'candidate_review_id':cid,'prompt_arm':d['prompt_arm'],'page_key':d['page_key'],
          'AI_contract_status':status,'reason_zh':reason,'output_sha256':object_sha(d['payload']),
          'original_contract_status':prev['original_contract_status'],'reviewer':'same_assistant_not_blinded_not_independent_expert',
          'expert_review':'pending','evaluation_only_never_runtime_input':True})
    return reviewed

def compute(out,outputs,review):
    old={x['candidate_review_id']:x for x in rows(V3/'candidate_adjudications.jsonl')}
    rr={(x['stage'],x['candidate_review_id']):x for x in review}
    ds={(x['stage'],x['candidate_review_id']):x for x in outputs}
    refs={x['reference_id']:x for x in rows(V3/'reference_overlay.jsonl')}
    matches=[]
    for stage in ['P0','P1']:
        group=[]
        for seed in rows(V3/'reference_match_annotations.jsonl'):
            r=refs[seed['reference_id']];ref=r['v21_reference_unchanged'];eligible=[];limits={}
            for cid in seed['candidate_review_ids']:
                d=ds[(stage,cid)];a=d['payload'];why=[]
                if not d['included']:why.append('withheld')
                if rr[(stage,cid)]['AI_contract_status']!='complete':why.append(rr[(stage,cid)]['AI_contract_status'])
                if a['scope']!='primary':why.append('scope_not_primary')
                if a.get('record_kind'):why.append('sidecar_not_core')
                same=a['relation']==ref['relation']
                if seed['relation_equivalence']=='risk_causes_equivalent_increases_risk_of':same=a['relation'] in ['causes','increases_risk_of']
                if not same:why.append('relation_not_equivalent')
                if seed['relation_equivalence'] in ['generic_replacement_only_partial','embedded_text_only_partial']:why.append(seed['relation_equivalence'])
                if not why:eligible.append(cid)
                limits[cid]=why
            kind=r['v3_evaluation_channel'];state=kind if kind!='core' else 'partial' if seed['candidate_review_ids'] else 'present_in_auxiliary' if seed['auxiliary_locations'] else 'not_found'
            group.append({'stage':stage,'reference_id':ref['reference_id'],'prompt_arm':seed['prompt_arm'],'page_key':ref['page_key'],'reference_channel':kind,
              'eligible_full_candidates':eligible,'candidate_limitations':limits,'state':state,'auxiliary_locations':seed['auxiliary_locations']})
        for arm in ['E0','E1']:
            mm=[x for x in group if x['prompt_arm']==arm and x['reference_channel']=='core']
            assignment=maximum_matching({x['reference_id']:x['eligible_full_candidates'] for x in mm})
            for x in mm:
                if x['reference_id'] in assignment:x.update(state='full',allocated_candidate_id=assignment[x['reference_id']])
                elif x['eligible_full_candidates']:x['state']='partial_composite_capacity'
        matches.extend(group)
    summaries=[];pages=[]
    for stage in ['P0','P1']:
        for arm in ['E0','E1']:
            subset=[d for d in outputs if d['stage']==stage and d['prompt_arm']==arm];selected=[d for d in subset if d['included']]
            primary=[d for d in selected if channel(d['payload'])=='core'];good=[d for d in primary if rr[(stage,d['candidate_review_id'])]['AI_contract_status']=='complete']
            problem=[d for d in primary if rr[(stage,d['candidate_review_id'])]['AI_contract_status'] not in ['complete','unresolved']]
            unknown=[d for d in primary if rr[(stage,d['candidate_review_id'])]['AI_contract_status']=='unresolved']
            before_good=[d for d in subset if channel(old[d['candidate_review_id']]['original'])=='core' and old[d['candidate_review_id']]['original_contract_status']=='complete']
            lost=[d for d in before_good if not d['included'] or channel(d['payload'])!='core' or rr[(stage,d['candidate_review_id'])]['AI_contract_status']!='complete']
            new_bad=[d for d in lost if d['included'] and rr[(stage,d['candidate_review_id'])]['AI_contract_status'] in ['semantic_error','representation_error','incomplete']]
            mm=[x for x in matches if x['stage']==stage and x['prompt_arm']==arm];corematches=[x for x in mm if x['reference_channel']=='core']
            same_scope=maximum_matching({x['reference_id']:[cid for cid in x['eligible_full_candidates'] if old[cid]['original']['scope']=='primary'] for x in corematches})
            for page in sorted({d['page_key'] for d in subset}):
                pm=[x for x in corematches if x['page_key']==page]
                pages.append({'stage':stage,'prompt_arm':arm,'page_key':page,'full_matches':sum(x['state']=='full' for x in pm),'denominator':len(pm),
                              'complete_core_records':sum(d['page_key']==page for d in good)})
            summaries.append({'stage':stage,'prompt_arm':arm,'inputs':len(subset),'included_all_channels':len(selected),
              'complete_core_records':len(good),'complete_core_exact_unique':len({exact_key(d['payload']) for d in good}),
              'problem_core_released':len(problem),'problem_core_breakdown':dict(Counter(rr[(stage,d['candidate_review_id'])]['AI_contract_status'] for d in problem)),
              'unresolved_core_released':len(unknown),'correct_core_lost':len(lost),'correct_core_lost_ids':[d['candidate_review_id'] for d in lost],
              'newly_corrupted_correct_core_released':len(new_bad),'newly_corrupted_ids':[d['candidate_review_id'] for d in new_bad],
              'full_reference_matches':sum(x['state']=='full' for x in mm),'reference_denominator':79,'full_matches_holding_original_scope':len(same_scope),
              'background_to_primary':sum(old[d['candidate_review_id']]['original']['scope']=='background' and d['payload']['scope']=='primary' for d in selected),
              'sidecar_records':sum(bool(d['payload'].get('record_kind')) for d in selected),
              'problem_outside_core_released':sum(channel(d['payload'])!='core' and rr[(stage,d['candidate_review_id'])]['AI_contract_status'] not in ['complete','unresolved'] for d in selected),
              'background_control_primary_fill':sum(d['page_key']=='MP002:p0089' for d in primary),
              'formal_accuracy_recall':'not_computed'})
    baseline={x['prompt_arm']:x for x in json.loads((V3/'summary.json').read_text()) if x['stage']=='B_filter'}
    gates=[]
    for s in summaries:
        if s['stage']!='P1':continue
        b=baseline[s['prompt_arm']]
        checks={'complete_quantity_nondecreasing':s['complete_core_exact_unique']>=b['AI_complete_core_exact_text_unique'],
          'coverage_strictly_increases':s['full_reference_matches']>b['core_full_reference_matches'],
          'problem_plus_unknown_nondecreasing_safety':s['problem_core_released']+s['unresolved_core_released']<=b['known_problem_core_records_released']+b['unresolved_core_records_released'],
          'correct_knowledge_loss_not_worse':s['correct_core_lost']<=b['correct_complete_core_rejected_or_lost'],
          'no_newly_corrupted_correct_core_released':s['newly_corrupted_correct_core_released']==0,
          'coverage_gain_without_scope_promotion':s['full_matches_holding_original_scope']>b['core_full_reference_matches'],
          'background_control_no_primary_fill':s['background_control_primary_fill']==0}
        gates.append({'prompt_arm':s['prompt_arm'],'checks':checks,'semantic_development_gate':'PASS' if all(checks.values()) else 'FAIL','implementation_checks':'see verification.json; required separately'})
    write(out/'reference_matches_340.jsonl',matches);write(out/'summary.json',summaries);write(out/'page_summary.jsonl',pages);write(out/'development_gate.json',gates)
    print(json.dumps({'summary':summaries,'development_gate':gates},ensure_ascii=False,indent=2))

def main():
    corrected='--corrected' in sys.argv
    out=BASE/('automatic_contract_v4_1' if corrected else 'automatic_contract_v4')
    outputs=rows(out/'automatic_outputs.jsonl');review=labels(outputs,corrected)
    write(out/'AI_source_review_466.jsonl',review)
    write(out/'evaluation_freeze.json',{'evaluator_sha256':sha(Path(__file__)),'output_sha256':sha(out/'automatic_outputs.jsonl'),
       'review_sha256':sha(out/'AI_source_review_466.jsonl'),'reference_overlay_sha256':sha(V3/'reference_overlay.jsonl'),
       'stage':'post-generation technical source review frozen before aggregate effect calculation','independent_expert_review':'pending'})
    compute(out,outputs,review)
if __name__=='__main__':main()
