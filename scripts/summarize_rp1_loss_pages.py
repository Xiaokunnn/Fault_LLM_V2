"""Aggregate the additive RP1 single-AI audit without modifying upstream assets."""
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_rp1_loss_pages as a

P=a.OUT
read=lambda f: a.read_rows(P/f)

def csv_file(name, rows):
    if not rows:return
    with (P/name).open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    seal=json.loads((P/'page_reference_seal.json').read_text())
    assert a.sha(P/'page_reference_annotations.jsonl')==seal['sha256']
    memberships={r['triple_id']:r['membership'] for r in read('corrected_publication_membership.jsonl')}
    jud={r['audit_id']:r for r in read('record_semantic_annotations.jsonl')}
    for r in read('record_visual_followup.jsonl'):
        jud[r['audit_id']]={**jud[r['audit_id']],**r}
    reviewed=[]
    for s in read('record_review_packets.jsonl'):
        r=s['record'];j=jud[s['audit_id']];g=a.group(r)
        ev=r.get('evidence_validation',{});scope=j.get('scope_assessment','no_specific_scope_violation_identified')
        if j['semantic_support']=='unresolved':cause='unresolved'
        elif j['semantic_support']=='unsupported':cause='semantic_or_relation_error'
        elif scope=='out_of_scope':cause='scope_mismatch'
        elif g=='qualified':cause='valid_retained_source_relative'
        elif not r.get('relation_type_valid'):cause='representation_schema_mismatch'
        elif not ev.get('valid') or r.get('evidence_level') not in ['E1','E2']:cause='localization_or_reconstruction_failure'
        else:cause='possible_rule_false_rejection'
        reviewed.append(dict(audit_id=s['audit_id'],triple_id=r['triple_id'],doc_id=r['doc_id'],pdf_page_number=r['pdf_page_number'],
            sample_kind=s['sample_kind'],weight=s['weight'],original_decision=g,layout_proxy=a.layout(r),relation=r['relation'],
            head_surface=r['head_surface'],tail_surface=r['tail_surface'],semantic_support=j['semantic_support'],
            scope_assessment=scope,primary_audit_explanation=cause,review_note=j['review_note'],
            original_failure_flags=a.flags(r),published=memberships[r['triple_id']],
            strict_terminology_block=(g=='qualified' and not memberships[r['triple_id']]['strict']),
            standard_terminology_block=(g=='qualified' and not memberships[r['triple_id']]['standard']),
            confirmed_false_rejection=False,human_expert_reviewed=False))
    assert len(reviewed)==97 and len({r['audit_id'] for r in reviewed})==97
    a.write_rows('record_findings.jsonl',reviewed)
    csv_file('record_findings.csv',[{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in reviewed])
    groups=[]
    for kind in ['probability','coverage_supplement']:
        for g in ['qualified','quarantined','rejected']:
            rs=[r for r in reviewed if r['sample_kind']==kind and r['original_decision']==g]
            groups.append(dict(sample_kind=kind,original_decision=g,n=len(rs),**{v:sum(r['semantic_support']==v for r in rs) for v in ['supported','unsupported','unresolved']},
                **{t:sum(r['published'][t] for r in rs) for t in ['strict','conservative','standard']}))
    csv_file('record_summary_by_decision.csv',groups)
    # Descriptive sampling-weight totals; explicitly not factual precision estimates.
    weighted={}
    for g in ['qualified','quarantined','rejected']:
        rs=[r for r in reviewed if r['sample_kind']=='probability' and r['original_decision']==g]
        weighted[g]={'population_n':sum(r['weight'] for r in rs),
                     'ai_label_weighted_counts':{v:sum(r['weight'] for r in rs if r['semantic_support']==v) for v in ['supported','unsupported','unresolved']},
                     'not_expert_accuracy':True,'confidence_interval':None}
    a.write_json('descriptive_sampling_weight_totals.json',weighted)
    byaxis=[]
    for axis in ['doc_id','layout_proxy','relation','primary_audit_explanation']:
        for kind in ['probability','coverage_supplement']:
            rs=[r for r in reviewed if r['sample_kind']==kind]
            for value in sorted({r[axis] for r in rs}):
                sub=[r for r in rs if r[axis]==value]
                byaxis.append(dict(axis=axis,value=value,sample_kind=kind,n=len(sub),**{v:sum(r['semantic_support']==v for r in sub) for v in ['supported','unsupported','unresolved']}))
    csv_file('record_breakdowns.csv',byaxis)

    candidates={r['triple_id']:r for r in read('page_candidate_comparison_packets.jsonl')}
    index={r['candidate_id']:r for r in read('page_candidate_index.jsonl')}
    q=read('page_candidate_semantic_annotations.jsonl')
    quality=[]
    for r in q:
        c=candidates[r['triple_id']]
        quality.append({**r,'original_decision':a.group(c),'page_key':f"{c['doc_id']}:p{c['pdf_page_number']:04d}",'published':memberships[c['triple_id']]})
    a.write_rows('page_candidate_findings.jsonl',quality)
    quality_summary=[]
    for g in ['qualified','quarantined','rejected']:
        rs=[r for r in quality if r['original_decision']==g]
        quality_summary.append(dict(original_decision=g,n=len(rs),**{v:sum(r['semantic_support']==v for r in rs) for v in ['supported','unsupported','unresolved']}))

    raw={r['triple_id']:r for r in read('page_raw_comparison_packets.jsonl')}
    enriched=[]
    for r in read('page_reference_matches.jsonl'):
        cs=[candidates[index[c]['triple_id']] for c in r['candidate_ids']]
        g=r['match_status']
        strict_match=g=='matched'
        matched_qualified=strict_match and any(a.group(c)=='qualified' for c in cs)
        pub={t:strict_match and any(memberships[c['triple_id']][t] for c in cs) for t in ['strict','conservative','standard']}
        if g=='not_found_in_audited_candidates':loss='no_identified_audited_representation'
        elif g=='partial_or_related':loss='partial_or_related_representation'
        elif not matched_qualified:loss='candidate_present_but_evidence_gate_not_passed'
        elif not pub['strict']:loss='qualified_but_not_strict_published'
        else:loss='strict_published'
        enriched.append({**r,'matched_in_full_run_saved_candidates':strict_match and any(c.get('legacy_triple_id') in raw for c in cs),
                         'matched_qualified':matched_qualified,'matched_publication':pub,'strict_path_stage':loss,
                         'candidate_gate_decisions':{index[c]['triple_id']:a.group(candidates[index[c]['triple_id']]) for c in r['candidate_ids']}})
    a.write_rows('page_match_findings.jsonl',enriched)
    page_refs={r['page_key']:r for r in read('page_reference_annotations.jsonl')}
    responses={r['page_key']:r for r in read('selected_raw_responses.jsonl')}
    page_rows=[]
    for s in read('page_sample_manifest.jsonl'):
        key=s['page_key'];rs=[r for r in enriched if r['page_key']==key];qs=[r for r in quality if r['page_key']==key]
        ref=page_refs[key]
        page_rows.append(dict(page_key=key,sampling_stratum='/'.join(s['stratum']),page_stratum_population=s['population_n'],
            source_reference_atoms=len(rs),reference_page_status='provisional_target_inventory' if rs else ('unresolved_not_negative' if ref['unresolved_items'] else 'no_target_within_declared_scope'),
            saved_audit_candidates=len(qs),source_supported_candidates=sum(r['semantic_support']=='supported' for r in qs),
            source_unsupported_candidates=sum(r['semantic_support']=='unsupported' for r in qs),unresolved_candidates=sum(r['semantic_support']=='unresolved' for r in qs),
            matched=sum(r['match_status']=='matched' for r in rs),partial_or_related=sum(r['match_status']=='partial_or_related' for r in rs),
            not_found=sum(r['match_status']=='not_found_in_audited_candidates' for r in rs),matched_qualified=sum(r['matched_qualified'] for r in rs),
            **{f'matched_{t}':sum(r['matched_publication'][t] for r in rs) for t in ['strict','conservative','standard']},
            original_full_run_cache_present=bool(responses[key].get('cache')),
            original_model_warning=json.dumps(responses[key].get('response_json',{}).get('warnings',[]),ensure_ascii=False)))
    csv_file('page_summary.csv',page_rows)

    # Inspect lineage without assuming the normalized pool is a simple subset.
    all_raw=a.read_rows(a.RAW);all_audit=a.read_rows(a.SOURCE)
    raw_ids={r['triple_id'] for r in all_raw};legacy=Counter(r.get('legacy_triple_id') for r in all_audit)
    lineage={'full_run_saved_rows':len(all_raw),'full_run_unique_ids':len(raw_ids),
             'audit_rows_with_legacy_not_in_full_run':sum(r.get('legacy_triple_id') not in raw_ids for r in all_audit),
             'full_run_rows_without_audit_legacy_link':sum(r['triple_id'] not in legacy for r in all_raw),
             'excess_audit_rows_sharing_legacy_id':sum(v-1 for v in legacy.values() if v>1),
             'audit_extraction_run_counts':dict(Counter(r.get('extraction_run_id','MISSING') for r in all_audit)),
             'selected_pages_saved_full_run_rows':len(raw),'selected_pages_audit_rows':len(candidates),
             'selected_pages_full_run_rows_without_legacy_link':sum(r['triple_id'] not in {c.get('legacy_triple_id') for c in candidates.values()} for r in raw.values()),
             'selected_pages_extra_audit_records':[{'triple_id':c['triple_id'],'extraction_run_id':c.get('extraction_run_id'),'extractor':c.get('extractor')} for c in candidates.values() if c.get('legacy_triple_id') not in raw],
             'interpretation':'Raw file contains normalized retained candidates, not every generated proposal. Legacy mismatch is not proof of discarded knowledge. Additional selected-page records carry older targeted extraction provenance.'}
    a.write_json('candidate_lineage_audit.json',lineage)
    rejected_path=a.ROOT/'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/rejected_model_proposals.jsonl'
    keys=set(page_refs);rejected=[r for r in a.read_rows(rejected_path) if r['page_key'] in keys]
    a.write_rows('selected_pre_audit_rejections.jsonl',rejected)
    summary=dict(version='rp1_loss_page_audit_v1',reviewer='single Codex assistant',human_expert_reviewed=False,new_teacher_or_extractor_calls=0,
        record_summary=groups,record_primary_explanations=dict(Counter(r['primary_audit_explanation'] for r in reviewed if r['sample_kind']=='probability')),
        page_count=30,page_reference_atom_count=len(enriched),page_status_counts=dict(Counter(r['reference_page_status'] for r in page_rows)),
        page_candidate_count=len(quality),page_candidate_quality=quality_summary,
        reference_match_counts=dict(Counter(r['match_status'] for r in enriched)),
        complete_reference_matches_in_saved_full_run_candidates=sum(r['matched_in_full_run_saved_candidates'] for r in enriched),
        complete_reference_matches_qualified=sum(r['matched_qualified'] for r in enriched),
        complete_reference_matches_published={t:sum(r['matched_publication'][t] for r in enriched) for t in ['strict','conservative','standard']},
        strict_path_stage_counts=dict(Counter(r['strict_path_stage'] for r in enriched)),selected_pre_audit_rejections=len(rejected),
        known_scope_disagreement_reference_atoms=7,
        limitation='Provisional source-first inventory, not exhaustive gold. 7 generic-reliability atoms conflict with original model task interpretation; 75 partials are not total misses; no population recall/accuracy or confidence interval.',
        source_first_inventory_incompleteness_examples=['C059','C064','C067','C069','C075','C078','C184','C187','C189','C200'])
    a.write_json('summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
