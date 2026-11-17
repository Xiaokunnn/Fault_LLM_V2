"""Complete-vs-masked structure, exact counterfactual coldness and provenance."""
from common_audit import *


def main():
    if (OUT/'structure_complete.json').exists():print('REUSE complete structure audit');return
    d,entities,E,S,C,src=dataset();registry=d['schema']['relation_registry'];cat=read(STUDY/'data/catalogue.json');alias=read(STUDY/'data/entity_alias_closure.json')[:len(E)];a={e['entity_id']:alias[j] for j,e in enumerate(entities)}
    tests={c for c,x in S.items() if x['fold']=='test'};testgroups={S[c]['group_id'] for c in tests};pairs={tuple(sorted([a[C[c]['head_entity_id']],a[C[c]['tail_entity_id']]])) for c in tests};removed=[]
    for cid,c in sorted(C.items()):
        reasons=[]
        if S[cid]['group_id'] in testgroups:reasons.append('test_fact_evidence_group')
        if tuple(sorted([a[c['head_entity_id']],a[c['tail_entity_id']]])) in pairs:reasons.append('test_alias_unordered_pair_any_relation_conservative_block')
        if reasons:removed.append(dict(claim_id=cid,fold=S[cid]['fold'],reasons=reasons))
    views={'G_full':set(C),'G_train':{c for c,x in S.items() if x['fold']=='train'},'G_masked':set(C)-{x['claim_id'] for x in removed}}
    assert len(views['G_train'])==989 and len(tests)==224
    summary=[];node_rows=[];component_rows=[];doc_rows=[];rel_rows=[];pattern_rows=[];gs={};degrees={};component_map={}
    schema_bad=[]
    for cid,c in C.items():
        r=registry[c['relation']]
        if E[c['head_entity_id']]['entity_type'] not in r['domain'] or E[c['tail_entity_id']]['entity_type'] not in r['range']:schema_bad.append(cid)
    for view,cids in views.items():
        row,g,dg,cc,degree,patterns=metric(E,C,cids,d['graph']['evidence_assertions'],view,paths=True);row['domain_range_flagged_claims']=len(cids&set(schema_bad));summary.append(row);gs[view]=g;degrees[view]=degree
        cmp={e:j for j,comp in enumerate(cc) for e in comp};component_map[view]=cmp
        for eid in sorted(E):
            node_rows.append(dict(view=view,entity_id=eid,label=E[eid]['label_zh'],entity_type=E[eid]['entity_type'],neighbor_degree=degree[eid],directed_in=dg.in_degree(eid),directed_out=dg.out_degree(eid),component_id=cmp[eid],component_size=len(cc[cmp[eid]])))
        for j,comp in enumerate(cc):
            sub=g.subgraph(comp);ids=sorted({cid for u,v,attrs in sub.edges(data=True) for cid in attrs['claims']})
            component_rows.append(dict(view=view,component_id=j,entities=len(comp),neighbor_pairs=sub.number_of_edges(),claims=len(ids),assertion_records=sum(x['claim_id'] in ids for x in d['graph']['evidence_assertions']),documents=sorted({x['doc_id'] for cid in ids for x in src[cid]}),entity_ids=sorted(comp),claim_ids=ids))
        for r in sorted(registry):
            ids={cid for cid in cids if C[cid]['relation']==r};ends={C[cid][s+'_entity_id'] for cid in ids for s in ['head','tail']}
            rel_rows.append(dict(view=view,relation=r,claims=len(ids),assertion_records=sum(x['claim_id'] in ids for x in d['graph']['evidence_assertions']),unique_head_entities=len({C[cid]['head_entity_id'] for cid in ids}),unique_tail_entities=len({C[cid]['tail_entity_id'] for cid in ids}),active_entities=len(ends),leaf_entities_in_view=sum(degree[e]==1 for e in ends),strict_one_claim_components=sum(len(c)==2 and g.subgraph(c).number_of_edges()==1 and len(next(iter(g.subgraph(c).edges(data=True)))[2]['claims'])==1 and next(iter(g.subgraph(c).edges(data=True)))[2]['claims'][0] in ids for c in cc),cross_document_claims=sum(len({x['doc_id'] for x in src[cid]})>=2 for cid in ids)))
        for doc in sorted(I.BUILD):
            ids={cid for cid in cids if any(x['doc_id']==doc for x in src[cid])};ee={C[cid][s+'_entity_id'] for cid in ids for s in ['head','tail']};sub=g.edge_subgraph([(C[cid]['head_entity_id'],C[cid]['tail_entity_id']) for cid in ids]).copy()
            doc_rows.append(dict(view=view,document=doc,claims=len(ids),assertion_records=sum(x['claim_id'] in ids and x['doc_id']==doc for x in d['graph']['evidence_assertions']),entities=len(ee),unique_neighbor_pairs=sub.number_of_edges(),components_active=len(list(nx.connected_components(sub))),largest_document_component=max([len(z) for z in nx.connected_components(sub)]+[0]),shared_cross_document_entities=sum(len({x['doc_id'] for cid in cids if e in [C[cid]['head_entity_id'],C[cid]['tail_entity_id']] for x in src[cid]})>=2 for e in ee)))
        pattern_rows += [dict(view=view,hops=k,relations=' → '.join(pat),paths=n) for (k,pat),n in sorted(patterns.items())]
    csvsave('graph_statistics.csv',summary);csvsave('node_degrees.csv',node_rows);save(OUT/'components.jsonl',component_rows);csvsave('relation_structure.csv',rel_rows);csvsave('document_structure.csv',doc_rows);csvsave('directed_path_patterns.csv',pattern_rows);save(OUT/'mask_removals.jsonl',removed)
    # Every endpoint of a full valid target is incident to that target by
    # construction. Classify its zero-degree after removal at each exact stage.
    incident=defaultdict(set);group_claims=defaultdict(set)
    for cid,c in C.items():
        for e in [c['head_entity_id'],c['tail_entity_id']]:incident[e].add(cid)
        group_claims[S[cid]['group_id']].add(cid)
    cold=[];fact_rows=[];stages=Counter();cause_count=Counter();seen_stages=defaultdict(set)
    for cid in sorted(tests):
        c=C[cid];status={};reasonlist=[]
        for side in ['head','tail']:
            e=c[side+'_entity_id'];own=group_claims[S[cid]['group_id']]
            single=len(incident[e]-{cid});group=len(incident[e]-own);masked=degrees['G_masked'][e];train=degrees['G_train'][e]
            reason='warm_in_G_train'
            if train==0:
                if single==0:reason='only_this_target_claim_in_full_graph'
                elif group==0:reason='other_full_claims_all_within_own_fact_group'
                elif masked==0:reason='other_test_groups_jointly_remove_remaining_incidence'
                else:reason='validation_groups_remove_remaining_incidence'
                cause_count[reason]+=1;reasonlist.append(reason)
            row=dict(claim_id=cid,side=side,entity_id=e,label=E[e]['label_zh'],entity_type=E[e]['entity_type'],full_neighbor_degree=degrees['G_full'][e],full_incident_claims=len(incident[e]),other_claims_after_single_target_remove=single,other_claims_after_own_group_remove=group,masked_neighbor_degree=masked,train_neighbor_degree=train,reason=reason,full_component_size=next(len(z) for z in nx.connected_components(gs['G_full']) if e in z))
            cold.append(row);status[side]=dict(single=single,group=group,masked=masked,train=train)
        item=dict(claim_id=cid,full_component=component_map['G_full'][c['head_entity_id']],full_same_component=True)
        for stage in ['single','group','masked','train']:
            zeros=sum(status[s][stage]==0 for s in ['head','tail']);tag='both_cold' if zeros==2 else 'one_cold' if zeros==1 else 'warm';stages[stage,tag]+=1;item[stage+'_status']=tag
            for side in ['head','tail']:
                if status[side][stage]==0:seen_stages[stage].add(c[side+'_entity_id'])
        item['cold_reasons']=reasonlist;fact_rows.append(item)
    assert stages['train','both_cold']==147 and stages['train','one_cold']==72 and stages['train','warm']==5
    save(OUT/'cold_endpoint_ledger.jsonl',cold);save(OUT/'cold_fact_ledger.jsonl',fact_rows)
    csvsave('cold_by_removal_stage.csv',[dict(stage=stage,warm=stages[stage,'warm'],one_cold=stages[stage,'one_cold'],both_cold=stages[stage,'both_cold'],unique_cold_endpoint_ids=len(seen_stages[stage])) for stage in ['single','group','masked','train']])
    csvsave('cold_endpoint_causes.csv',[dict(reason=k,endpoint_occurrences=n,share_of_366_cold_occurrences=n/366) for k,n in sorted(cause_count.items())])
    # Describe actual learner inputs as well as the base graph used to define
    # coldness. Candidate contexts are not upgraded to confirmed graph facts.
    extra=[e for e in read(STUDY/'data/training_candidate_edges.jsonl') if e['conservative'] and e['legal'] and not e['already_base_train']]
    base_degree=Counter()
    for x in S.values():
        if x['fold']=='train':base_degree.update([x['triple'][0],x['triple'][2]])
    aux_degree=base_degree.copy()
    for x in extra:aux_degree.update([x['triple'][0],x['triple'][2]])
    aux_stats=Counter()
    for cid in tests:
        h,r,t=S[cid]['triple'];z=sum(aux_degree[i]==0 for i in [h,t]);aux_stats['both_cold' if z==2 else 'one_cold' if z else 'warm']+=1
    save(OUT/'actual_model_inputs.json',dict(base_train_claims=989,G2_auxiliary_directed_candidate_triples=len(extra),G2_auxiliary_endpoints_outside_base=len({i for e in extra for i in [e['triple'][0],e['triple'][2]] if i>=2150}),G2_training_appearance_test_status=aux_stats,context_legal_candidates=3671,total_index_edges=4660,caution='G_train is the base graph underlying reported coldness. G2 auxiliary positives and uncertain retrieval contexts differ; base-cold is not complete model-input invisibility.'))
    # Same alias identity in all secondary views, never merged into primary KG.
    mapping={eid:canonical([E[eid]['entity_type'],a[eid]]) for eid in E};AE={v:dict(entity_id=v,label_zh=v,entity_type=json.loads(v)[0]) for v in mapping.values()};AC={cid:dict(c,head_entity_id=mapping[c['head_entity_id']],tail_entity_id=mapping[c['tail_entity_id']]) for cid,c in C.items()};alias_stats=[]
    for view,cids in views.items():
        row,*_=metric(AE,AC,cids,d['graph']['evidence_assertions'],view+'_typed_alias_sensitivity',paths=False);alias_stats.append(row)
    csvsave('typed_alias_sensitivity.csv',alias_stats)
    save(OUT/'definitions.json',dict(primary_entity_identity='Original expanded1456 stable entity_id, identical 2150 inventory in all three primary views',degree='Number of distinct OTHER semantic entity neighbors in undirected simple projection; no assertion multiplicity',components='Include zero-degree inventory nodes; active-only components also reported',single_pair='2 nodes, 1 unordered neighbor pair; may have >1 Claim',strict_single_relation='2 nodes, 1 unordered pair and exactly 1 Claim; evidence rows never multiply it',paths='Node-simple paths with no repeated vertices, exact length2/3. Undirected reversal counted once; directed paths follow recorded arrows. Relation-labelled paths separately expand distinct predicates; no causal transitive edges added.',mask='Remove all test fact/evidence groups plus any unordered saved-alias endpoint pair; a conservative superset of known inverse/equivalent relations, not an equivalence theorem. Validation restored in G_masked; not text-source-page removal.',G_train='989 base Claims actually defining historical coldness; G2 auxiliary/context inputs separately documented',typed_alias_sensitivity='Same type + saved source alias root, same mapping across views. Diagnostic hypothetical quotient, may merge subtype/model contexts; not a corrected graph or verified alignment.',schema_flagged_claims=schema_bad,condition_boundary='Claims are families; assertion conditions and modality remain source-linked. Connectivity does not prove conditions jointly compatible.'))
    save(OUT/'source_manifest.json',dict(domain_object=I.REV,domain_inputs=d['inputs'].hashes,study_inputs={str(p.relative_to(ROOT)):sha(p) for p in [STUDY/'data/base_split.jsonl',STUDY/'data/catalogue.json',STUDY/'data/entity_alias_closure.json',STUDY/'data/training_candidate_edges.jsonl',STUDY/'verification/delivery_manifest.json']}))
    save(OUT/'structure_complete.json',dict(graphs=summary,cold_causes=cause_count,cold_occurrences=sum(cause_count.values()),views={k:len(v) for k,v in views.items()},schema_flags=len(schema_bad),additional_masked_outside_test=sum(x['fold']!='test' for x in removed)))
    print('STRUCTURE',summary,'COLD',dict(cause_count),flush=True)


if __name__=='__main__':main()
