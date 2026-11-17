"""Read saved ranks/retrieval only; no training or new completion scores."""
from common_audit import *
from collections import Counter,defaultdict


def main():
    if (OUT/'implications_complete.json').exists():return
    d,entities,E,S,C,src=dataset();g,_,_=graphs(E,C,set(C));comps=sorted(nx.connected_components(g),key=lambda x:(-len(x),min(x)));component={e:j for j,cc in enumerate(comps) for e in cc};degrees=dict(g.degree());struct=[];bridge=[]
    incident=defaultdict(set)
    for cid,c in C.items():
        incident[c['head_entity_id']].add(cid);incident[c['tail_entity_id']].add(cid)
    docs={cid:{r['doc_id'] for r in rr} for cid,rr in src.items()};fams={cid:{r['source_family_id'] for r in rr} for cid,rr in src.items()};models={cid:{I.norm(r.get('pump_type')) for r in rr if r.get('pump_type')} for cid,rr in src.items()}
    for eid in sorted(E):
        ids=sorted(incident[eid]);ed=set().union(*(docs[c] for c in ids));ef=set().union(*(fams[c] for c in ids))
        cross=any(len(docs[a]|docs[b])>=2 for a,b in itertools.combinations(ids,2));ind=any(len(fams[a]|fams[b])>=2 for a,b in itertools.combinations(ids,2))
        if len(ed)>=2:bridge.append(dict(entity=E[eid],documents=sorted(ed),source_families=sorted(ef),incident_claims=ids,distinct_claims_can_join_different_docs=cross,distinct_claims_can_join_different_declared_families=ind,condition_compatibility_not_established=True))
    save(OUT/'cross_document_bridge_entities.jsonl',bridge)
    cm=[]
    for j,cc in enumerate(comps):
        ids={cid for e in cc for cid in incident[e]};doc=set().union(*(docs[c] for c in ids));fam=set().union(*(fams[c] for c in ids));sub=g.subgraph(cc)
        cm.append(dict(component_id=j,entities=len(cc),claims=len(ids),neighbor_pairs=sub.number_of_edges(),documents=sorted(doc),source_families=sorted(fam),tree=sub.number_of_edges()==len(cc)-1,independent_undirected_cycles=sub.number_of_edges()-len(cc)+1))
    save(OUT/'component_provenance_summary.jsonl',cm)
    pathrows=[]
    for view in ['G_full','G_train','G_masked']:
        counts=defaultdict(Counter)
        for p in read(OUT/f'paths/{view}_paths.jsonl'):
            key=(p['directed'],p['hops']);ds=[set().union(*(docs[c] for c in step)) for step in p['claim_choices']];fs=[set().union(*(fams[c] for c in step)) for step in p['claim_choices']];ms=[set().union(*(models[c] for c in step)) for step in p['claim_choices']]
            counts[key]['paths']+=1
            counts[key]['possible_multi_document']+=len(set().union(*ds))>=2
            counts[key]['requires_multi_document_no_common_document']+=not bool(set.intersection(*ds))
            counts[key]['requires_multi_declared_family_no_common_family']+=not bool(set.intersection(*fs))
            counts[key]['common_literal_pump_type_signature']+=bool(set.intersection(*ms))
        pathrows += [dict(view=view,directed=k[0],hops=k[1],**{name:n.get(name,0) for name in ['paths','possible_multi_document','requires_multi_document_no_common_document','requires_multi_declared_family_no_common_family','common_literal_pump_type_signature']}) for k,n in sorted(counts.items())]
    csvsave('path_source_distribution.csv',pathrows)
    # Graph shape groups are diagnostic, not newly selected benchmarks.
    tests=sorted(c for c,x in S.items() if x['fold']=='test');tags={};tagcounts=Counter()
    for cid in tests:
        c=C[cid];h,t=c['head_entity_id'],c['tail_entity_id'];comp=comps[component[h]];ids={z for e in comp for z in incident[e]};tt=[]
        if len(comp)==2 and len(ids)==1:tt.append('full_single_claim_pair_component')
        elif degrees[h]==1 or degrees[t]==1:tt.append('full_larger_component_with_leaf_endpoint')
        else:tt.append('full_both_endpoints_degree_ge2')
        tt.append('train_'+read(STUDY/'audit_only/test_targets.jsonl')[[x['id'] for x in read(STUDY/'audit_only/test_targets.jsonl')].index(cid)]['endpoint_status'])
        if component[h]==0:tt.append('in_full_largest_component')
        tags[cid]=tt;tagcounts.update(tt)
    methods=['simkgc_G1','simkgc_G2','simkgc_filter','collab_lan','collab_full','transport_R3','native_query_full'];seeds=[16112026,16112027,16112028];mr=[]
    for method in methods:
        for tag in sorted(tagcounts):
            values=[]
            for seed in seeds:
                rr=read(STUDY/'evaluation'/f'{method}_s{seed}'/'rankings.jsonl');selected=[r for r in rr if r['task']!='relation' and tag in tags[r['id']]];values.append(float(np.mean([1/r['rank'] for r in selected])))
            mr.append(dict(method=method,diagnostic_stratum=tag,facts=tagcounts[tag],link_MRR=float(np.mean(values)),seed_sd=float(np.std(values)),not_new_independent_test=True))
    csvsave('saved_model_results_by_full_graph_shape.csv',mr);save(OUT/'test_full_graph_shape_tags.json',dict(counts=tagcounts,per_fact=tags))
    # R3 contexts, interpreted against full graph components AFTER inference.
    cache=np.load(STUDY/'retrieval/R3_all_global.npz');views=read(STUDY/'index/oriented_views.jsonl');edges=read(STUDY/'index/edges.jsonl');R=15;slotcounts=Counter();perq=[]
    for cid in tests:
        h,r,t=S[cid]['triple']
        for side,(a,qr) in [('tail',(h,r)),('head',(t,r+R))]:
            counts=Counter();contexts=[]
            for vi in cache['ids'][a,qr,:16]:
                if vi<0:continue
                v=views[int(vi)];edge=edges[v['edge_index']];ah=v['anchor'];bt=v['neighbor'];qid=entities[a]['entity_id']
                if ah==a:kind='same_anchor'
                elif ah>=2150:kind='anchor_outside_full_base_catalogue'
                elif component[entities[ah]['entity_id']]==component[qid]:kind='different_anchor_same_full_component'
                else:kind='different_full_component_base_anchor'
                counts[kind]+=1;slotcounts[kind]+=1
                noendpoint=not any(j<2150 and component[entities[j]['entity_id']]==component[qid] for j in [ah,bt]);counts['neither_endpoint_in_query_full_component']+=noendpoint;slotcounts['neither_endpoint_in_query_full_component']+=noendpoint
                if len(contexts)<3:contexts.append(dict(edge_id=edge['edge_id'],oriented_anchor=ah,oriented_relation=v['relation'],oriented_neighbor=bt,is_base=edge['is_base'],source_pages=edge['pages'],full_component_class=kind))
            perq.append(dict(claim_id=cid,task=side,query_anchor=a,query_relation=qr,selected_slots=sum(counts[k] for k in ['same_anchor','anchor_outside_full_base_catalogue','different_anchor_same_full_component','different_full_component_base_anchor']),counts=dict(counts),first_three_contexts=contexts))
    save(OUT/'r3_context_component_ledger.jsonl',perq)
    complete=dict(full_components=len(cm),full_tree_components=sum(c['tree'] for c in cm),full_cycle_rank=sum(c['independent_undirected_cycles'] for c in cm),components_multi_document=sum(len(c['documents'])>=2 for c in cm),components_multi_declared_family=sum(len(c['source_families'])>=2 for c in cm),multi_document_bridge_entities=len(bridge),entities_joining_distinct_cross_doc_claims=sum(x['distinct_claims_can_join_different_docs'] for x in bridge),entities_joining_distinct_cross_family_claims=sum(x['distinct_claims_can_join_different_declared_families'] for x in bridge),test_shape_counts=tagcounts,R3_test_queries=len(perq),R3_context_slot_counts=slotcounts,caution='These are descriptive saved-run strata and source signatures, not additional model experiments or proof of causal contribution.')
    save(OUT/'implications_complete.json',complete);print('IMPLICATIONS',complete,flush=True)


if __name__=='__main__':main()
