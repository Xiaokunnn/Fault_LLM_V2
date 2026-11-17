"""Trace 8007 export rows/8003 records and construct an automatic GA pool."""
from common import *


def main():
    if (OUT/'lineage/complete.json').exists():print('REUSE lineage');return
    d,E,C,S=dataset();reg=d['schema']['relation_registry'];A=d['normalized'];rawby=defaultdict(list)
    for j,x in enumerate(d['raw'],1):rawby[x['triple_id']].append((j,x))
    loc={x['triple_id']:x for x in read(PARENT/'post_extraction_feasibility_20261113/candidate_locator_audit.jsonl')}
    audit_ids=defaultdict(list);audit_sources=defaultdict(list)
    for a in d['audit']:
        for ident in identities(a):audit_ids[ident].append(a)
        audit_sources[I.source_identity(a)].append(a)
    pubid=defaultdict(list);pubkey=defaultdict(list)
    for x in d['graph']['source_records']:
        for rid in identities(x):pubid[rid].append(x)
        pubkey[key(x)].append(x)
    dup=defaultdict(list)
    for x in A:dup[key(x)].append(x)
    rowdata=[];complete=[];unpublished=[];representatives=set();ga=[];gaskip=Counter();aidbyraw=defaultdict(list)
    for x in sorted(A,key=lambda x:x['triple_id']):
        rid=x['triple_id'];n=x;rawmatches=[(j,r) for ident in identities(x) for j,r in rawby.get(ident,[])]
        prior={a['triple_id']:a for ident in identities(x) for a in audit_ids[ident]};audit_method='explicit_current_legacy_ID'
        if not prior:prior={a['triple_id']:a for a in audit_sources[I.source_identity(x)]};audit_method='exact_source_signature'
        prior_loc=[loc[z] for z in prior if z in loc]
        lc=prior_loc[0] if len(prior_loc)==1 else dict(locator_contract_pass=False,failed_checks=['ambiguous_or_missing_prior_locator_join'])
        for j,r in rawmatches:aidbyraw[j].append(rid)
        matches={s['expanded_assertion_id']:s for ident in identities(x) for s in pubid[ident]};same=[s for s in matches.values() if key(s)==key(n)];changed=[s for s in matches.values() if key(s)!=key(n)]
        cids=sorted({s['expanded_claim_id'] for s in matches.values()});canonical_cids=sorted({s['expanded_claim_id'] for s in pubkey[key(n)]})
        schema_ok=legal(x,reg);semantic=x.get('relation_entailment_validation',{}).get('status');reasonlist=sorted(set(x.get('rejection_reasons',[])+x.get('review_reasons',[])));conditional=bool(CONDITION.search(x.get('evidence_text','')));structured=bool(x.get('conditions_source') or x.get('conditions'));scope_ok=bool(x.get('doc_id') in I.BUILD and x.get('pump_type') and x.get('applicability_scope'))
        if same:
            cid=sorted({s['expanded_claim_id'] for s in same})[0];main='published_aggregated' if cid in representatives else 'published_representative';representatives.add(cid)
        elif changed:main='published_after_reconstruction'
        elif canonical_cids:main='same_typed_signature_already_published_other_lineage'
        elif not schema_ok:main='schema_excluded'
        elif not lc['locator_contract_pass']:main='location_or_evidence_contract'
        elif semantic=='not_entailed':main='semantic_negative_or_direction'
        elif conditional and not structured:main='condition_modality_or_stage_unresolved'
        elif semantic!='entailed':main='semantic_support_unresolved'
        elif x['decision']=='silver_candidate' and not x.get('eligible_for_chinese_graph'):main='terminology_not_published'
        else:main='other_confidence_or_unresolved'
        dd=dup[key(n)];docs={z['doc_id'] for z in dd};fams={z.get('source_family_id') for z in dd};langs={z.get('source_language') for z in dd};pages={(z['doc_id'],z['pdf_page_number']) for z in dd}
        row=dict(record_id=rid,legacy_record_id=x.get('legacy_triple_id',''),prior_audit_record_ids='|'.join(sorted(prior)),prior_audit_join_method=audit_method if prior else 'unresolved',raw_export_rows='|'.join(str(j) for j,r in rawmatches),raw_export_ids='|'.join(sorted({r['triple_id'] for j,r in rawmatches})),primary_attribution=main,original_status=x['decision'],semantic_status=semantic,stored_locator_contract_pass=lc['locator_contract_pass'],schema_legal=schema_ok,doc_id=x['doc_id'],physical_page=x['pdf_page_number'],source_family=x['source_family_id'],head_type=x['head_type'],head=n['head_canonical_zh'],relation=x['relation'],tail_type=x['tail_type'],tail=n['tail_canonical_zh'],typed_signature=digest(key(n)),condition_aware_signature=signature(n),explicit_condition_cue=conditional,structured_conditions_present=structured,declared_scope_present=scope_ok,published_claim_ids='|'.join(cids),published_same_signature_claim_ids='|'.join(canonical_cids),published_same_value_assertions=len(same),published_changed_value_assertions=len(changed),duplicate_typed_signature_records=len(dd),duplicate_across_pages=len(pages)>1,duplicate_across_documents=len(docs)>1,duplicate_across_family_labels=len(fams)>1,duplicate_language_metadata_variants=len(langs)>1,reasons='|'.join(reasonlist))
        rowdata.append(row)
        complete.append(dict(**row,original_source=pointer(x),published_sources=[dict(claim_id=s['expanded_claim_id'],source=pointer(s),expansion_layer=s['expansion_layer']) for s in matches.values()],old_locator_failed_checks=lc['failed_checks'],old_normalization_actions=x.get('normalization_actions',[]),fact_correctness_confirmed=False))
        if cids or canonical_cids:continue
        if not schema_ok:gaskip['schema']+=1;continue
        if not lc['locator_contract_pass']:gaskip['saved_locator_contract']+=1;continue
        if semantic!='entailed':gaskip['saved_semantic_not_entailed_or_unknown']+=1;continue
        if x.get('rejection_reasons') or x.get('confidence_components',{}).get('hard_veto_reasons'):gaskip['saved_negative_rejection_or_veto']+=1;continue
        if not scope_ok:gaskip['missing_declared_scope']+=1;continue
        if conditional and not structured:gaskip['unbound_condition_modality_stage_cue']+=1;continue
        address=I.address_check(x,d['pages'][x['doc_id'],x['pdf_page_number']])
        located=address['metadata_hashes_match'] and (address['exact_contiguous_offset'] or address['all_provided_cells_match'] or address['all_native_witnesses_match'])
        if not located:gaskip['read_only_native_address_recheck']+=1;continue
        ga.append(dict(record_id=rid,source=pointer(n),original_status=x['decision'],saved_semantic_status=semantic,old_locator_contract=lc,native_address=address,structured_conditions=n.get('conditions_source'),scope_and_conditions_complete_confirmed=False,automatic_proxy_only=True))
    csvsave('CANDIDATE_LINEAGE.csv',rowdata);save('lineage/record_details.jsonl',complete)
    rawrows=[]
    for j,x in enumerate(d['raw'],1):rawrows.append(dict(export_row=j,raw_id=x['triple_id'],normalized_ids='|'.join(sorted(set(aidbyraw[j]))),explicit_ID_link=bool(aidbyraw[j]),doc_id=x['doc_id'],physical_page=x['pdf_page_number'],head=x['head_canonical_zh'],relation=x['relation'],tail=x['tail_canonical_zh'],raw_id_multiplicity=len(rawby[x['triple_id']]),unresolved_not_assumed_lost=not bool(aidbyraw[j])))
    csvsave('lineage/raw_export_links.csv',rawrows)
    groups=defaultdict(list)
    for r in rowdata:groups[r['primary_attribution']].append(r)
    categories=[]
    for category,rows in sorted(groups.items()):categories.append(dict(category=category,records=len(rows),distinct_typed_signatures=len({r['typed_signature'] for r in rows}),condition_aware_signatures=len({r['condition_aware_signature'] for r in rows}),documents=sorted({r['doc_id'] for r in rows}),entity_types=dict(Counter(t for r in rows for t in [r['head_type'],r['tail_type']])),relations=dict(Counter(r['relation'] for r in rows))))
    save('lineage/category_counts.json',categories);save('lineage/GA_eligible_records.jsonl',ga)
    # A1 is a reproducible signal classification; only source-reading cases may
    # claim explicit support. Saved machine states alone do not prove it.
    eligible_ids={r['record_id'] for r in ga};a1=[]
    for r in complete:
        if r['relation'] not in SIX or r['published_claim_ids'] or r['published_same_signature_claim_ids']:continue
        if r['record_id'] in eligible_ids:grade='automatic_strong_traceable_support_not_semantically_confirmed'
        elif r['semantic_status']=='not_entailed':grade='stored_machine_negative_not_independent_contradiction'
        elif r['explicit_condition_cue']:grade='scope_condition_or_modality_required_unverified'
        elif not r['stored_locator_contract_pass']:grade='insufficient_location_or_contract'
        else:grade='undetermined'
        a1.append(dict(record_id=r['record_id'],relation=r['relation'],signal_class=grade,source=r['original_source'],old_status=r['original_status'],old_reasons=r['reasons'],not_new_semantic_label=True))
    save('lineage/unpublished_six_relation_signals.jsonl',a1)
    save('lineage/complete.json',dict(raw_export_rows=len(d['raw']),raw_unique_ids=len(rawby),normalized_records=len(A),raw_rows_linked=sum(r['explicit_ID_link'] for r in rawrows),raw_rows_unresolved=sum(not r['explicit_ID_link'] for r in rawrows),audit_records_with_raw_ID=sum(bool(r['raw_export_rows']) for r in rowdata),base_assertions=len(d['graph']['source_records']),base_claims=len(C),source_layers=dict(Counter(s['expansion_layer'] for s in d['graph']['source_records'])),primary_counts=dict(Counter(r['primary_attribution'] for r in rowdata)),duplicate_typed_groups=sum(len(x)>1 for x in dup.values()),records_in_duplicate_groups=sum(len(x) for x in dup.values() if len(x)>1),duplicate_groups_cross_document=sum(len({r['doc_id'] for r in x})>1 for x in dup.values()),GA_eligible_records=len(ga),GA_skips=dict(gaskip),unpublished_six_relation_records=len(a1),A1_signal_classes=dict(Counter(r['signal_class'] for r in a1)),raw_minus_claims_not_a_loss_count=True))
    # Anonymous source-first reading sheet: all same-page records are available
    # in the packet. Matching against one page never proves global absence.
    units=read(OUT/'source_sample/selected_units.jsonl');packets=[]
    for u in units:
        pagec=[r for r in d['normalized'] if r['doc_id']==u['doc_id'] and r['pdf_page_number']==u['pdf_page_number']]
        pagepub=[s for s in d['graph']['source_records'] if s['doc_id']==u['doc_id'] and s['pdf_page_number']==u['pdf_page_number']]
        lead=[]
        for x in pagec:
            norm=I.norm(u['unit_text']);ht=sum(bool(x.get(z+'_surface')) and I.norm(x[z+'_surface']) in norm for z in ['head','tail']);cell=bool(set(x.get('evidence_unit_ids',[]))&set(u['native_ids']))
            lead.append(dict(record_id=x['triple_id'],head=x['head_canonical_zh'],head_surface=x['head_surface'],head_type=x['head_type'],relation=x['relation'],tail=x['tail_canonical_zh'],tail_surface=x['tail_surface'],tail_type=x['tail_type'],endpoint_literal_overlap=ht,native_cell_overlap=cell,old_status=x.get('decision'),evidence_text=x['evidence_text']))
        packets.append(dict(**u,same_page_candidates=lead,same_page_published=[dict(claim_id=s['expanded_claim_id'],head=s['head_canonical_zh'],relation=s['relation'],tail=s['tail_canonical_zh'],evidence_text=s['evidence_text']) for s in pagepub],no_same_page_match_does_not_prove_global_absence=True))
    save('source_sample/reviewer_packets.jsonl',packets);save('lineage/input_hashes.json',d['inputs'].hashes)
    print(read(OUT/'lineage/complete.json'),flush=True)


if __name__=='__main__':main()
