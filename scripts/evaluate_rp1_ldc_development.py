#!/usr/bin/env python3
"""Source-reviewed incremental development evaluation; never imported by runtime."""
import json
from collections import Counter,defaultdict
from rp1_offline_contract_v3 import *
OUT=BASE/'layout_direction_context_v1/development'


def main():
    outputs=rows(OUT/'outputs.jsonl')
    prior={r['candidate_review_id']:r for r in rows(BASE/'clause_binding_v1/AI_review.jsonl') if r['stage']=='R'}
    bs={r['candidate_review_id']:r for r in outputs if r['stage']=='B'}
    supplemental={object_sha(r['assertion']):r for r in rows(BASE/'ai_review_v1/candidate_adjudications.jsonl')}
    refs={r['reference_id']:r for r in rows(BASE/'ai_review_v1/reference_review.jsonl') if r['evaluation_channel']=='core'}
    assert len(refs)==77
    annotations=[]
    for d in outputs:
        cid=d['candidate_review_id'];a=d['payload'];p=prior[cid]
        verdict='S' if p['AI_contract_status']=='complete' else 'U' if p['AI_contract_status']=='unresolved' else 'E'
        reason='语义未变，复用既有开发源文标签；不是新增独立评价。'
        overlay=supplemental.get(object_sha(bs[cid]['payload']))
        if overlay:verdict=overlay['verdict'];reason=overlay['reason_zh']
        if a!=bs[cid]['payload']:
            delta={k for k in set(a)|set(bs[cid]['payload']) if a.get(k)!=bs[cid]['payload'].get(k)}
            if cid in ['VR05:A016','VR05:A017']:
                verdict='S';reason='完整热水警告给出排气工况，风险关系方向修正且possible保留；非无条件风险。'
            elif cid=='VR08:A019':
                verdict='S';reason='源句caused by直接支持汽蚀到侵蚀；may恢复为possible，不再表示必然。'
            else:
                assert delta=={'conditions'},(cid,delta)
                reason='源文局部条件补入；未删旧条件，其余角色问题不因补条件改判。'
        annotations.append(dict(stage=d['stage'],candidate_review_id=cid,payload_sha256=object_sha(a),verdict=verdict,reason_zh=reason))
    write(OUT/'source_review.jsonl',annotations)
    rv={(r['stage'],r['candidate_review_id']):r for r in annotations}
    match_seed=rows(BASE/'offline_contract_v3/reference_match_annotations.jsonl')
    summary=[];allocations=[]
    for stage in ['B','L','D','C']:
        for arm in ['E0','E1']:
            group=[d for d in outputs if d['stage']==stage and d['prompt_arm']==arm]
            kept=[d for d in group if d['included'] and channel(d['payload'])=='core']
            grade=lambda d:rv[(stage,d['candidate_review_id'])]['verdict']
            count=Counter(grade(d) for d in kept)
            eligible={d['candidate_review_id']:d for d in kept if grade(d)=='S'}
            edges={}
            for seed in match_seed:
                rid=seed['reference_id']
                if rid not in refs or seed['prompt_arm']!=arm:continue
                candidates=[]
                for cid in seed['candidate_review_ids']:
                    if cid not in eligible:continue
                    rel=eligible[cid]['payload']['relation'];expected=refs[rid]['revised_reference']['relation']
                    compatible=rel==expected or seed['relation_equivalence']=='risk_causes_equivalent_increases_risk_of' and rel in ['causes','increases_risk_of']
                    if compatible and seed['relation_equivalence'] not in ['generic_replacement_only_partial','embedded_text_only_partial']:candidates.append(cid)
                edges[rid]=candidates
            mapping=maximum_matching(edges)
            allocations.append(dict(stage=stage,prompt_arm=arm,allocations=mapping))
            original_good=[d for d in group if channel(bs[d['candidate_review_id']]['payload'])=='core' and rv[('B',d['candidate_review_id'])]['verdict']=='S' and bs[d['candidate_review_id']]['included']]
            lost=sum(not d['included'] or grade(d)!='S' or channel(d['payload'])!='core' for d in original_good)
            summary.append(dict(stage=stage,prompt_arm=arm,total_retained=sum(d['included'] for d in group),core_S=count['S'],core_E=count['E'],core_U=count['U'],baseline_supported_lost=lost,full_matches=len(mapping),references=77))
    write(OUT/'summary.json',summary);write(OUT/'reference_allocations.json',allocations)
    write(OUT/'evaluation_note.json',dict(reference_total=85,eligible_core=77,unresolved=5,operating_sidecar=3,old_79_denominator_not_overwritten=True,changed_positive_source_reviews=['VR05:A016','VR05:A017','VR08:A019'],layout_only_development_recovery=0,reviewer='Codex AI source review',new_API_calls=0))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
