"""Five controlled diagnostic views; business facts and virtual links separated."""
from common import *

PAIRS={('causes','diagnosed_by'),('causes','inspected_by'),('causes','mitigated_by'),('causes','prevented_by'),('manifests_as','diagnosed_by'),('indicates','mitigated_by'),('indicates','diagnosed_by'),('occurs_at','inspected_by'),('occurs_at','maintained_by'),('contains','inspected_by'),('contains','maintained_by')}


def concepts(E):
    groups=defaultdict(set);reason={}
    for eid,e in E.items():
        label=I.norm(e['label_zh']);k=('same_lexical_label_across_roles',label);groups[k].add(eid);reason[k]='Exact saved canonical label only; same concept lexeme, NOT entity identity'
        if e['entity_type']=='Component':
            stem=re.sub(r'\(\s*\d{2,5}(?:\s*[,/]\s*\d{2,5})*\s*\)','',label).strip()
            k=('component_numbered_family',stem);groups[k].add(eid);reason[k]='Exact component phrase after removing parenthesized part number; part/model remains on original entity'
    for a in read(PARENT/'kg_structure_cross_document_audit_v1/alias_hypothesis_clusters.jsonl'):
        k=('saved_alias_hypothesis',a['cluster_id']);groups[k].update(x['entity_id'] for x in a['entities'] if x['entity_id'] in E);reason[k]='Previously stored typed alias hypothesis, unconfirmed; no new semantic-neighbor retrieval'
    # Exact component-name mentions in action labels provide a navigational
    # index, NOT proof of an action-object fact or identity between these nodes.
    generic={'泵','电机','设备','轴','阀','轴承','部件','机组','液体','水','油','系统','密封'}
    components=defaultdict(set)
    for eid,e in E.items():
        if e['entity_type']=='Component':
            stem=re.sub(r'\(\s*\d{2,5}\s*\)','',I.norm(e['label_zh'])).strip()
            if len(stem)>=2 and stem not in generic:components[stem].add(eid)
    for stem,member in components.items():
        actions={eid for eid,e in E.items() if e['entity_type'] in ['InspectionAction','MaintenanceAction'] and stem in I.norm(e['label_zh'])}
        if actions:
            k=('literal_component_mention_index',stem);groups[k].update(member|actions);reason[k]='Exact name mention in action label; lexical navigation only, object semantics and scope unresolved'
    nodes={};links=[];membership=defaultdict(set)
    for k,ids in sorted(groups.items()):
        if len(ids)<2:continue
        cid='VCON-'+digest(k)[:22];nodes[cid]=dict(entity_id=cid,node_kind='virtual_concept',name=k[1],mapping_kind=k[0],not_a_business_fact=True)
        for eid in sorted(ids):
            links.append(dict(entity_id=eid,concept_id=cid,mapping_kind=k[0],mapping_basis=reason[k],identity_equivalence_confirmed=False,business_fact=False));membership[eid].add(cid)
    return nodes,links,membership


def main():
    if (OUT/'counterfactual/complete.json').exists():print('REUSE counterfactual views');return
    assert (OUT/'source_sample/REFERENCE_FREEZE.json').exists(),'Freeze source references before view metrics'
    d,E,C,S=dataset();baseE=dict(E);baseC=dict(C);baseS={k:list(v) for k,v in S.items()};reg=d['schema']['relation_registry']
    bylabel={(e['entity_type'],I.norm(e['label_zh'])):eid for eid,e in E.items()}
    def entity(ht,label):
        k=(ht,I.norm(label))
        if k not in bylabel:
            eid='AQE-'+digest(k)[:24];bylabel[k]=eid;E[eid]=dict(entity_id=eid,entity_type=ht,label_zh=label)
        return bylabel[k]
    extraC={};extraS=defaultdict(list);basekeys={(c['head_entity_id'],c['relation'],c['tail_entity_id']) for c in C.values()}
    for x in read(OUT/'lineage/GA_eligible_records.jsonl'):
        s=x['source'];h=entity(s['head_type'],s['head_canonical_zh']);t=entity(s['tail_type'],s['tail_canonical_zh']);k=(h,s['relation'],t)
        if k in basekeys:continue
        cid='AQC-'+digest(k)[:24];extraC[cid]=dict(claim_id=cid,head_entity_id=h,relation=s['relation'],tail_entity_id=t,automatic_proxy=True,published=False);extraS[cid].append(dict(s,diagnostic_record_id=x['record_id'],automatic_proxy=True))
    allC={**C,**extraC};allS={**baseS,**extraS};allE=dict(E)
    # GC is an independently scoped SOURCE-READING REFERENCE SUBGRAPH, not G0
    # plus invented answers and never fed to GA/GB or a completion learner.
    gcC={};gcS=defaultdict(list)
    for r in read(OUT/'source_sample/reference_relations.jsonl'):
        h=entity(r['head_type'],r['head_canonical_zh']);t=entity(r['tail_type'],r['tail_canonical_zh']);cid='SRCREF-'+r['sample_id']
        gcC[cid]=dict(claim_id=cid,head_entity_id=h,relation=r['relation'],tail_entity_id=t,source_AI_reference=True,published=False)
        gcS[cid].append(dict(r,evidence_text=r['source_unit_text'],conditions_source=[r['required_condition']] if r['required_condition'] else [],source_AI_reference=True))
    gcE={eid:E[eid] for c in gcC.values() for eid in [c['head_entity_id'],c['tail_entity_id']]}
    g0E=baseE;gaE={eid:allE[eid] for c in allC.values() for eid in [c['head_entity_id'],c['tail_entity_id']]}
    concepts0,links0,member0=concepts(g0E);conceptsa,linksa,membera=concepts(gaE)
    save('counterfactual/concept_nodes_GB.jsonl',list(concepts0.values()));save('counterfactual/virtual_mappings_GB.jsonl',links0)
    save('counterfactual/concept_nodes_GAB.jsonl',list(conceptsa.values()));save('counterfactual/virtual_mappings_GAB.jsonl',linksa)
    scopes=[]
    for cid,c in allC.items():
        for s in allS[cid]:
            for side in ['head','tail']:
                eid=c[side+'_entity_id'];scopes.append(dict(occurrence_id='OCC-'+digest([eid,cid,s['doc_id'],s.get('pdf_page_number'),s.get('diagnostic_record_id'),s.get('triple_id')])[:24],entity_id=eid,claim_id=cid,doc_id=s['doc_id'],physical_page=s['pdf_page_number'],pump_type=s.get('pump_type'),applicability_scope=s.get('applicability_scope'),conditions_source=s.get('conditions_source'),modality=s.get('modality'),instance_kind='source_scoped_occurrence_not_confirmed_physical_instance',explicit_model_tokens=re.findall(r'(?<![A-Za-z0-9])[A-Z]{1,}[- ]?\d+[A-Za-z0-9/-]*',E.get(eid,allE.get(eid))['label_zh']),source=pointer(s)))
    save('counterfactual/scoped_occurrences.jsonl',scopes)
    save('counterfactual/GC_complex_source_records.jsonl',[u for u in read(OUT/'SOURCE_UNIT_AUDIT.jsonl') if u['complex_semantics']])
    views={'G0':(g0E,baseC,baseS,{},[]),'GA':(gaE,allC,allS,{},[]),'GB':(g0E,baseC,baseS,concepts0,links0),'GAB':(gaE,allC,allS,conceptsa,linksa),'GC':(gcE,gcC,gcS,{},[])}
    metrics=[];summaries=[];navigation=[];bridges=[];role_rows=[];question_rows=[];basecomponents={x['entity_id']:int(x['component_id']) for x in csv.DictReader((PARENT/'kg_structure_cross_document_audit_v1/node_degrees.csv').open()) if x['view']=='G_full'}
    baseline=next(r for r in csv.DictReader((PARENT/'kg_structure_cross_document_audit_v1/graph_statistics.csv').open()) if r['view']=='G_full')
    questions=read(OUT/'source_sample/fixed_questions.jsonl');sourceunits={u['sample_id']:u for u in read(OUT/'SOURCE_UNIT_AUDIT.jsonl')}
    def emit(view,projection,k,v,unit,level='exact_automatic_count',limit='Not factual accuracy or confirmed condition compatibility',den=None):metrics.append(dict(view=view,projection=projection,metric=k,value=v,denominator='' if den is None else den,unit=unit,evidence_level=level,interpretation_limit=limit))
    for view,(ve,vc,vs,vn,vl) in views.items():
        save('counterfactual/'+view+'_business_claims.jsonl',list(vc.values()))
        if view in ['GA','GC']:save('counterfactual/'+view+'_business_sources.jsonl',[dict(claim_id=cid,source=s) for cid in vc for s in vs[cid]])
        graph=nx.Graph();graph.add_nodes_from(ve);directed=defaultdict(list);rolemap=defaultdict(set)
        for cid,c in vc.items():
            h,t=c['head_entity_id'],c['tail_entity_id'];graph.add_edge(h,t);directed[h].append(cid)
            for eid,role in roles(c,ve):rolemap[eid].add(role)
        components=list(nx.connected_components(graph));degrees=dict(graph.degree());one=[cc for cc in components if len(cc)==2 and graph.subgraph(cc).number_of_edges()==1];single=sum(sum(c['head_entity_id'] in cc and c['tail_entity_id'] in cc for c in vc.values())==1 for cc in one)
        scalar=dict(semantic_entities=len(ve),business_claims=len(vc),business_source_records=sum(len(vs[cid]) for cid in vc),unique_neighbor_pairs=graph.number_of_edges(),components=len(components),strict_single_claim_components=single,largest_component=max(map(len,components)),degree1=sum(v==1 for v in degrees.values()),degree0=sum(v==0 for v in degrees.values()),entities_with_two_diagnostic_roles=sum(len(rr&{'cause','inspection','remedy'})>=2 for rr in rolemap.values()),entities_with_cause_inspection_remedy=sum({'cause','inspection','remedy'}<=rr for rr in rolemap.values()))
        if view=='G0':
            assert scalar['semantic_entities']==int(baseline['inventory_entities']) and scalar['components']==int(baseline['components_including_zero']) and scalar['strict_single_claim_components']==int(baseline['two_node_exactly_one_claim_components'])
        for k,v in scalar.items():emit(view,'semantic_business_only',k,v,'claim' if k=='business_claims' else 'count')
        knownmerged=[]
        for cc in components:
            old={basecomponents[e] for e in cc if e in basecomponents}
            if len(old)>1:knownmerged.append(old)
        merged_reductions=sum(len(z)-1 for z in knownmerged);merged_participants=sum(len(z) for z in knownmerged)
        if view!='GC':
            emit(view,'semantic_business_only','old_component_merger_reductions',merged_reductions,'original_components',level='automatic_hypothetical_count' if view in ['GA','GAB'] else 'exact_automatic_count')
            emit(view,'semantic_business_only','old_components_participating_in_mergers',merged_participants,'original_components')
        patterns=Counter();fine=Counter()
        for cid,c in vc.items():
            mid=c['tail_entity_id']
            for cid2 in directed[mid]:
                z=vc[cid2];pair=(c['relation'],z['relation'])
                if pair not in PAIRS or c['head_entity_id']==z['tail_entity_id']:continue
                patterns[pair]+=1
                samepages={(s['doc_id'],s['pdf_page_number']) for s in vs[cid]}&{(s['doc_id'],s['pdf_page_number']) for s in vs[cid2]}
                samepump={s.get('pump_type') for s in vs[cid] if s.get('pump_type')}&{s.get('pump_type') for s in vs[cid2] if s.get('pump_type')}
                if samepages:fine[pair]+=1
                navigation.append(dict(view=view,claim1=cid,claim2=cid2,pattern=' -> '.join(pair),same_source_page=bool(samepages),same_declared_pump_type=bool(samepump),conditions_jointly_verified=False,not_transitive_fact=True))
        emit(view,'semantic_business_only','diagnostic_2hop_navigation_patterns',sum(patterns.values()),'relation_paths');emit(view,'semantic_business_only','diagnostic_2hop_same_page',sum(fine.values()),'relation_paths',limit='Shared source page still does not prove matching table branch or conditions')
        for eid,rr in sorted(rolemap.items()):role_rows.append(dict(view=view,entity_id=eid,entity_type=ve[eid]['entity_type'],label=ve[eid]['label_zh'],diagnostic_roles=sorted(rr)))
        # Heterogeneous concept projection never changes semantic degrees or
        # Claim counts. Document/scope/Evidence hubs are excluded from it.
        hg=graph.copy();hg.add_nodes_from(vn)
        for l in vl:hg.add_edge(l['entity_id'],l['concept_id'])
        hc=list(nx.connected_components(hg));conceptmergers=[{basecomponents[e] for e in cc if e in basecomponents} for cc in hc];conceptmergers=[z for z in conceptmergers if len(z)>1]
        if vl:
            for k,v in dict(heterogeneous_nodes=hg.number_of_nodes(),virtual_concept_nodes=len(vn),virtual_mapping_edges=len(vl),heterogeneous_components=len(hc),heterogeneous_largest_component=max(map(len,hc)),organization_old_component_merger_reductions=sum(len(z)-1 for z in conceptmergers)).items():emit(view,'concept_navigation_not_business_facts',k,v,'count',level='lexical_mapping_hypothesis',limit='Organization via lexical/category links; not entity equivalence, extra business facts or factual accuracy')
        membership=member0 if view=='GB' else membera if view=='GAB' else {}
        # Fixed questions were frozen before view results. Exact source-scoped
        # atomic retrieval and weaker concept navigation are separate metrics.
        exact_count=0;nav_count=0;context_count=0;structured_count=0
        for q in questions:
            if q['kind']=='atomic_relation_retrieval':
                r=q['reference'];exact=[];organized=[]
                for cid,c in vc.items():
                    if c['relation']!=r['relation']:continue
                    if not any(s['doc_id']==r['doc_id'] for s in vs[cid]):continue
                    h,t=ve[c['head_entity_id']],ve[c['tail_entity_id']]
                    sameh=(h['entity_type'],I.norm(h['label_zh']))==(r['head_type'],I.norm(r['head_canonical_zh']));samet=(t['entity_type'],I.norm(t['label_zh']))==(r['tail_type'],I.norm(r['tail_canonical_zh']))
                    if sameh and samet:exact.append(cid)
                    rh=bylabel.get((r['head_type'],I.norm(r['head_canonical_zh'])));rt=bylabel.get((r['tail_type'],I.norm(r['tail_canonical_zh'])))
                    ch=bool(rh and membership.get(rh,set())&membership.get(c['head_entity_id'],set()));ct=bool(rt and membership.get(rt,set())&membership.get(c['tail_entity_id'],set()))
                    if (sameh or ch) and (samet or ct):organized.append(cid)
                exact_count+=bool(exact);nav_count+=bool(organized or exact)
                question_rows.append(dict(view=view,question_id=q['question_id'],sample_id=q['sample_id'],kind=q['kind'],atomic_exact_source_scoped_answer=bool(exact),concept_navigation_candidate=bool(organized or exact),claim_ids=exact,concept_candidate_ids=organized,condition_complete_confirmed=False,not_diagnostic_accuracy=True))
            else:
                u=sourceunits[q['sample_id']];related=[s for cid in vc for s in vs[cid] if s['doc_id']==u['doc_id'] and s['pdf_page_number']==u['pdf_page_number']]
                def normalize(z):return I.norm(re.sub(r'(?<=\w)-\s+(?=\w)','',z))
                required=q['reference']['required'];text_available=any(all(normalize(v) in normalize(s.get('evidence_text',s.get('source_unit_text',''))) for v in required) for s in related)
                structured=any(s.get('conditions_source') for s in related)
                if view=='GC':text_available=True;structured=True  # by construction: frozen source reference records, not learned recovery
                context_count+=text_available;structured_count+=structured
                if view=='GC':question_rows.append(dict(view=view,question_id=q['question_id'],sample_id=q['sample_id'],kind=q['kind'],reference_unit_available=True,structured_reference_spec_available=True,complete_semantic_binding_verified=False,reference_ceiling_by_construction=True))
                else:question_rows.append(dict(view=view,question_id=q['question_id'],sample_id=q['sample_id'],kind=q['kind'],required_text_fragments_attached_to_same_assertion=bool(text_available),some_structured_context_on_source_page=bool(structured),complete_semantic_binding_verified=False,reference_ceiling_by_construction=False))
        emit(view,'fixed_source_reference_questions','atomic_exact_retrieval',exact_count,'questions',level='source_AI_reference_proxy',limit='18 selected AI source references, exact typed tuple + same document; not diagnosis accuracy or full conditional support',den=18)
        emit(view,'fixed_source_reference_questions','concept_navigation_candidates',nav_count,'questions',level='lexical_navigation_proxy',limit='Concept-linked possible answer is not an affirmed relation',den=18)
        if view=='GC':
            emit(view,'source_reference_auxiliary','required_reference_units_available',context_count,'questions',level='source_reference_by_construction',limit='Frozen source reference units, NOT newly recovered assertion fields or algorithm accuracy',den=16)
            emit(view,'source_reference_auxiliary','structured_reference_specs_available',structured_count,'questions',level='source_reference_by_construction',limit='Reference target specifications only, not inferred semantic bindings',den=16)
        else:
            emit(view,'complex_source_access','required_text_fragments_on_assertion',context_count,'questions',level='literal_source_access_proxy',limit='Lack of dedicated fields alone is not semantic loss; text access is not structured binding',den=16)
            emit(view,'complex_source_access','any_structured_context_on_page',structured_count,'questions',level='field_presence_proxy',limit='Condition fields may concern another relation; not complete binding accuracy',den=16)
        scalar.update(view=view,GA_uncertain_claims=len(extraC) if view in ['GA','GAB'] else 0,virtual_concepts=len(vn),virtual_links=len(vl),heterogeneous_components=len(hc),heterogeneous_largest_component=max(map(len,hc)),old_component_merger_reductions=merged_reductions if view!='GC' else None,organization_merger_reductions=sum(len(z)-1 for z in conceptmergers) if vl else None,atomic_questions_answered=exact_count,atomic_questions_denominator=18,concept_question_candidates=nav_count,complex_text_attached=context_count,complex_question_denominator=16)
        summaries.append(scalar)
        if view=='GA':
            for cid,c in extraC.items():
                h,t=c['head_entity_id'],c['tail_entity_id'];both=h in baseE and t in baseE
                if both:kind='direct_old_component_bridge' if basecomponents[h]!=basecomponents[t] else 'within_old_component'
                elif h in baseE or t in baseE:kind='new_leaf_attached' if degrees[h if h not in baseE else t]==1 else 'new_hub_attached'
                else:kind='new_nodes_only'
                bridges.append(dict(claim_id=cid,head=allE[h],relation=c['relation'],tail=allE[t],kind=kind,old_head_component=basecomponents.get(h),old_tail_component=basecomponents.get(t),candidate_records=len(extraS[cid]),sources=[pointer(s) for s in extraS[cid]],automatic_support_unconfirmed=True))
    csvsave('QUALITY_METRICS.csv',metrics);save('counterfactual/view_summary.json',summaries);save('counterfactual/diagnostic_navigation_paths.jsonl',navigation);save('counterfactual/diagnostic_roles.jsonl',role_rows);save('counterfactual/question_results.jsonl',question_rows);save('counterfactual/GA_structure_ledger.jsonl',bridges)
    save('counterfactual/complete.json',dict(GA_candidate_records=sum(len(x) for x in extraS.values()),GA_new_claim_families=len(extraC),GA_added_entities=len(gaE)-len(baseE),GA_edge_kinds=dict(Counter(x['kind'] for x in bridges)),GB_original_business_claims_unchanged=views['GB'][1]==baseC,GAB_business_equals_GA=views['GAB'][1]==allC,GB_concept_mapping_kinds=dict(Counter(l['mapping_kind'] for l in links0)),view_summary=summaries,source_reference_not_Gold=True,independent_factor_percentages_identifiable=False,formal_graph_changed=False))
    print(read(OUT/'counterfactual/complete.json'),flush=True)


if __name__=='__main__':main()
