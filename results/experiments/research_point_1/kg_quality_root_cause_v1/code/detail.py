"""Evidence-strength details and post-hoc decomposition of virtual organization."""
from common import *


def main():
    if (OUT/'details/complete.json').exists():print('REUSE details');return
    d,E,C,S=dataset();N=d['normalized'];overlap=[]
    for name,fun in [
        ('stored_relation_type_invalid',lambda r:not r.get('relation_type_valid',False)),
        ('stored_evidence_invalid_reason',lambda r:'evidence_invalid' in r.get('rejection_reasons',[])),
        ('stored_semantic_not_entailed',lambda r:r.get('relation_entailment_validation',{}).get('status')=='not_entailed'),
        ('stored_dual_model_negative',lambda r:'dual_qwen_relation_not_entailed' in r.get('rejection_reasons',[])),
        ('saved_semantic_undetermined',lambda r:r.get('relation_entailment_validation',{}).get('status')=='undetermined'),
        ('condition_or_stage_cue',lambda r:bool(CONDITION.search(r.get('evidence_text','')))),
    ]:
        rr=[r for r in N if fun(r)];overlap.append(dict(signal=name,records=len(rr),distinct_typed_signatures=len({key(r) for r in rr}),relation_counts=canon(Counter(r['relation'] for r in rr)),head_type_counts=canon(Counter(r['head_type'] for r in rr)),tail_type_counts=canon(Counter(r['tail_type'] for r in rr)),overlapping_not_additive=True,not_independent_factual_errors=True))
    csvsave('lineage/overlapping_signals.csv',overlap)
    pubgroups=Counter(s['expanded_claim_id'] for s in d['graph']['source_records'])
    # Explain how much the apparent GB connectivity comes from a weak lexical
    # mention index, without changing the frozen main view or questions.
    decomposed=[]
    oldcomp={r['entity_id']:int(r['component_id']) for r in csv.DictReader((PARENT/'kg_structure_cross_document_audit_v1/node_degrees.csv').open()) if r['view']=='G_full'}
    for view in ['GB','GAB']:
        vc=read(OUT/'counterfactual'/f'{view}_business_claims.jsonl');links=read(OUT/'counterfactual'/f'virtual_mappings_{view}.jsonl')
        business_nodes={c[s+'_entity_id'] for c in vc for s in ['head','tail']}
        for name,kept in [('all_frozen_mappings',links),('without_component_mention_index',[l for l in links if l['mapping_kind']!='literal_component_mention_index'])]:
            g=nx.Graph();g.add_nodes_from(business_nodes)
            for c in vc:g.add_edge(c['head_entity_id'],c['tail_entity_id'])
            for l in kept:g.add_edge(l['entity_id'],l['concept_id'])
            cc=list(nx.connected_components(g));largest=max(cc,key=len);oc=[{oldcomp[e] for e in z if e in oldcomp} for z in cc]
            decomposed.append(dict(view=view,subview=name,posthoc_explanatory_ablation=True,business_claims=len(vc),virtual_links=len(kept),heterogeneous_components=len(cc),largest_heterogeneous_nodes=len(largest),largest_semantic_entities=sum(e in business_nodes for e in largest),largest_virtual_concepts=sum(e not in business_nodes for e in largest),original_component_merger_reductions=sum(len(z)-1 for z in oc if len(z)>1),not_a_correct_fact_improvement=True))
    csvsave('counterfactual/concept_layer_decomposition.csv',decomposed)
    bridge_notes={
        'AQC-e80377f7fc73fe96418eba64':('scope_not_established','一般压力容器水压见证检验，源文本身清楚；但不证明与当前泵本体具有同一设备实例或试验条件。'),
        'AQC-477bb46e29b8cc423aa190f8':('explicit_pump_test_condition_required','泵水压试验及至少1.5P有直接原文；仍需保留具体章节设备范围和试验压力，不能只有泛化泵—液压试验。'),
        'AQC-4daba054bba2b0068ecebbb7':('component_identity_scope_risk','shaft liners与中文轴套的类名可能相同，源页为推进轴系规则语境；不能自动当成另一手册泵轴套的同一实例。'),
        'AQC-e14f234b1537eb10bdb362a4':('explicit_conditional_pump_statement','长期停机时液体冻结可能损坏泵有直接原句；条件部分在头实体文字中，may/could不能解释为必然因果。'),
        'AQC-91e30ab8cc9d99a2adf21a8b':('generic_definition_not_specific_diagnosis','通用状态监测定义说采取action防故障，语义非常抽象；即使连接了实体，也没有提供一个具体可执行维修措施。'),
    }
    bridge_reviews=[]
    for b in read(OUT/'counterfactual/GA_structure_ledger.jsonl'):
        if b['kind']!='direct_old_component_bridge':continue
        tag,note=bridge_notes[b['claim_id']];bridge_reviews.append(dict(**b,source_reading_category=tag,source_reading_note=note,evaluator='Codex assistant source reading, not independent expert Gold',confirmed_new_fact=False))
    save('details/direct_bridge_source_reviews.jsonl',bridge_reviews)
    # C means absence of the focal CLAIM in retained exports, not that all of
    # its words were absent from evidence/auxiliary material in those exports.
    cchecks=[]
    for u in read(OUT/'SOURCE_UNIT_AUDIT.jsonl'):
        if u['primary_source_judgment']!='C':continue
        r=u['reference'];needles=[I.norm(r['head_surface']),I.norm(r['tail_surface'])]
        exporthits=[]
        for rowno,x in enumerate(d['raw'],1):
            if x['doc_id']!=u['doc_id']:continue
            if all(v in I.norm(x.get('evidence_text','')) for v in needles):exporthits.append(dict(raw_export_row=rowno,record_id=x['triple_id'],head=x['head_canonical_zh'],relation=x['relation'],tail=x['tail_canonical_zh'],physical_page=x['pdf_page_number']))
        cchecks.append(dict(sample_id=u['sample_id'],source_reference=r,exact_typed_normalized_claim_matches=u['exact_typed_candidate_matches'],same_document_export_quotes_containing_endpoint_fragments=exporthits,claim_absence_under_finite_mapping=True,all_original_API_outputs_audited=False,complete_information_loss_not_established=True))
    save('details/C_export_scope_checks.jsonl',cchecks)
    save('details/cross_document_pattern_leads.jsonl',read(PARENT/'kg_enhancement_document_gap_v1/support_limits/scope_unresolved_pattern_attempts.jsonl'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in [PARENT/'kg_structure_cross_document_audit_v1/graph_statistics.csv',PARENT/'kg_structure_cross_document_audit_v1/node_degrees.csv',PARENT/'kg_structure_cross_document_audit_v1/alias_hypothesis_clusters.jsonl',PARENT/'kg_structure_cross_document_audit_v1/cross_document_shared_claims.jsonl',PARENT/'kg_enhancement_document_gap_v1/support_limits/scope_unresolved_pattern_attempts.jsonl',PARENT/'kg_enhancement_document_gap_v1/gaps/document_requests.jsonl',PARENT/'post_extraction_feasibility_20261113/candidate_locator_audit.jsonl']}
    save('details/parent_input_hashes.json',hashes)
    save('details/complete.json',dict(published_multirecord_claims=sum(n>1 for n in pubgroups.values()),assertions_above_claim_count=sum(pubgroups.values())-len(pubgroups),raw_unique_ids=len({r['triple_id'] for r in d['raw']}),normalized_signature_count=len({key(r) for r in N}),published_provenance_IDs_linked_to_candidates=len({r['record_id'] for r in read(OUT/'lineage/record_details.jsonl') if r['published_claim_ids']}),bridge_AI_review_count=len(bridge_reviews),bridge_confirmed_correct_facts=0,C_claim_absence_not_API_absence=True,independent_Gold_available=False))
    print(read(OUT/'details/complete.json'),flush=True)


if __name__=='__main__':main()
