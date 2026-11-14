"""Separate historical publication/terminology blocks from true evidence loss."""
from collections import Counter,defaultdict
import json
import sys

from inputs import load,save,norm,core_tuple,record_ids
from selection_screen import OUT,OLD,read
from selection_overlay import SANDBOX


def main():
    sys.stdout.reconfigure(encoding='utf-8');d=load()
    dictionary=defaultdict(set)
    for r in d['graph']['source_records']:
        for side in ['head','tail']:
            dictionary[r[side+'_type'],norm(r[side+'_surface'])].add(norm(r[side+'_canonical_zh']))
            dictionary[r[side+'_type'],norm(r[side+'_canonical_zh'])].add(norm(r[side+'_canonical_zh']))
    current={core_tuple(r) for r in d['graph']['source_records']}
    rows=[]
    for m in read(OLD/'mapping/raw_occurrence_mapping.jsonl'):
        if m['candidate_category']=='current_graph_lineage_present':continue
        r=m['normalized_source'];ends={side:sorted(dictionary[r[side+'_type'],norm(r[side+'_surface'])]) for side in ['head','tail']}
        if all(len(v)==1 for v in ends.values()):
            k=(r['head_type'],ends['head'][0],r['relation'],r['tail_type'],ends['tail'][0])
            status='existing_core_under_typed_dictionary' if k in current else 'known_terms_potentially_unpublished_relation'
        else:status='dictionary_insufficient_or_ambiguous'
        rows.append({'raw_occurrence_id':m['raw_occurrence_id'],'historical_statuses':m['historical_audit_statuses'],
                     'typed_dictionary_candidates':ends,'result':status,'semantic_identity_and_scope_certified':False})
    save(OUT/'evaluation/typed_dictionary_full_unpublished.jsonl',rows)
    restored=read(SANDBOX/'original_candidate_provenance.jsonl');cases=[]
    for r in restored:
        m=r['normalization_mapping_unchanged'];records=r['normalized_candidate_records_unchanged']
        cases.append({'case_id':r['case_id'],'historical_statuses':m['historical_audit_statuses'],
            'historical_reasons':m['historical_reasons'],
            'terminology_release_states':[{k:n.get(k) for k in ['triple_id','eligible_for_chinese_graph','graph_release_status','chinese_canonicalization_reasons','head_translation_status','tail_translation_status']} for n in records],
            'historically_evidence_qualified_but_term_blocked':bool('silver_candidate' in m['historical_audit_statuses'] and any(not n.get('eligible_for_chinese_graph') for n in records)),
            'dictionary_control':next(x for x in rows if x['raw_occurrence_id']==m['raw_occurrence_id'])})
    save(OUT/'evaluation/restoration_original_loss_causes.jsonl',cases)
    qualified=[r for r in rows if 'silver_candidate' in r['historical_statuses'] and r['result']!='existing_core_under_typed_dictionary']
    summary={'all_unpublished_occurrences_including_duplicate_controls':len(rows),
        'typed_dictionary_result_counts':dict(Counter(r['result'] for r in rows)),
        'historically_evidence_qualified_unpublished_occurrences':sum('silver_candidate' in r['historical_statuses'] for r in rows),
        'A_restored_assertion_candidates':len(cases),
        'A_restored_previously_evidence_qualified_but_term_blocked':sum(r['historically_evidence_qualified_but_term_blocked'] for r in cases),
        'A_restored_previously_evidence_quarantined':sum('candidate_needs_review' in r['historical_statuses'] for r in cases),
        'A_restored_previously_evidence_rejected':sum('rejected' in r['historical_statuses'] for r in cases),
        'restored_candidates_typed_dictionary_results':dict(Counter(r['dictionary_control']['result'] for r in cases)),
        'not_global_correct_fact_counts':True,
        'a_missing_dictionary_entry_is_not_itself_algorithmic_novelty':True,
        'repaired_candidates_have_not_passed_original_chinese_publication_gate':True}
    save(OUT/'evaluation/publication_loss_summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
