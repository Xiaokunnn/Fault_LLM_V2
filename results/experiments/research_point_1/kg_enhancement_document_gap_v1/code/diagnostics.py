"""Post-hoc validation diagnostics; no new hyperparameter selection or test use."""
from common_local import *
from transport_cpu import CPUIndex,score_transport,link_ranks


def main():
    if (OUT/'diagnostics/complete.json').exists():print('REUSE diagnostics');return
    d,cat,entities,ei,claims,src,uf=load_domain();index=CPUIndex();keys=[tuple(k) for k in read(OUT/'mechanism/query_keys.json')];ki={k:j for j,k in enumerate(keys)}
    targets=read(STUDY/'data/validation_targets.jsonl');truth=read(STUDY/'data/validation_truth.json');selection={m:np.load(OUT/'mechanism'/f'{m}_k16_selection.npz') for m in ['T0','T1','T2','T3','T4','T5']}
    components={x['entity_id']:int(x['component_id']) for x in csv.DictReader((AUDIT/'node_degrees.csv').open()) if x['view']=='G_full'}
    def component(a):return components.get(entities[a]['entity_id']) if a<2150 else None
    querymeta={}
    for h,r in keys:
        ids=selection['T0']['ids'][ki[h,r]];ss=selection['T0']['scores'][ki[h,r]];valid=ids>=0;weight=torch.softmax(torch.tensor(np.r_[np.where(valid,ss,-1e4)/.1,0]),0).numpy()[:-1]*valid
        both_outside=0.;exact=0.;same=0.;unknown=0.;known_mass=0.
        for vi,w in zip(ids,weight):
            if vi<0:continue
            a,b=index.a[vi],index.b[vi];outside=component(a)!=component(h) and component(b)!=component(h);both_outside+=float(w)*outside;exact+=float(w)*(index.r[vi]==r)
            if index.anchor_docs[h]:same+=float(w)*bool(index.anchor_docs[h]&index.edge_docs[vi//2]);known_mass+=float(w)
            else:unknown+=float(w)
        querymeta[h,r]=dict(h=h,r=r,source_observable=bool(index.anchor_docs[h]),query_source_documents=sorted(index.anchor_docs[h]),outside_full_component_weight=both_outside,same_directed_relation_weight=exact,same_visible_document_weight=same,unknown_document_weight=unknown,null_weight=float(1-weight.sum()),context_stratum='outside_component_dominant' if both_outside>.5 else 'includes_same_component_or_null_dominant')
    save(OUT/'diagnostics/query_context_metadata.jsonl',list(querymeta.values()))
    baseranks={};allranks={};results=[]
    for seed in SEEDS:
        data=torch.load(STUDY/'features'/f'G2_s{seed}.pt',map_location='cpu',weights_only=True)
        matrix=score_transport(data,keys,selection['T0']['ids'],selection['T0']['scores'],index,alpha=0.)
        rr=link_ranks(matrix,keys,targets,truth);baseranks[seed]={(x['id'],x['task']):x for x in rr};save(OUT/'diagnostics'/f'text_only_s{seed}_ranks.jsonl',rr)
        for method in ['text_only','T0','T1','T2','T3','T4','T5']:
            rows=rr if method=='text_only' else read(OUT/'mechanism'/f'{method}_k16_s{seed}_ranks.jsonl');allranks[method,seed]={(x['id'],x['task']):x for x in rows}
            for stratum in ['all_validation','outside_component_dominant','includes_same_component_or_null_dominant','source_observable','source_unknown']:
                take=[]
                for x in rows:
                    meta=querymeta[x['query_anchor'],x['query_relation']]
                    ok=(stratum=='all_validation' or stratum==meta['context_stratum'] or stratum=='source_observable' and meta['source_observable'] or stratum=='source_unknown' and not meta['source_observable'])
                    if ok:take.append(x)
                if not take:continue
                results.append(dict(method=method,seed=seed,stratum=stratum,query_directions=len(take),MRR=float(np.mean([1/x['rank'] for x in take])),Hits1=float(np.mean([x['rank']<=1 for x in take])),Hits10=float(np.mean([x['rank']<=10 for x in take])),wins_vs_text=sum(x['rank']<baseranks[seed][x['id'],x['task']]['rank'] for x in take),losses_vs_text=sum(x['rank']>baseranks[seed][x['id'],x['task']]['rank'] for x in take)))
        del data
    csvsave('diagnostics/stratified_seed_results.csv',results)
    groups=defaultdict(list)
    for x in results:groups[x['method'],x['stratum']].append(x)
    aggregated=[]
    for (method,s),rows in sorted(groups.items()):aggregated.append(dict(method=method,stratum=s,query_directions=rows[0]['query_directions'],MRR=float(np.mean([x['MRR'] for x in rows])),MRR_seed_sd=float(np.std([x['MRR'] for x in rows])),Hits1=float(np.mean([x['Hits1'] for x in rows])),Hits10=float(np.mean([x['Hits10'] for x in rows])),mean_wins_vs_text=float(np.mean([x['wins_vs_text'] for x in rows])),mean_losses_vs_text=float(np.mean([x['losses_vs_text'] for x in rows]))))
    csvsave('diagnostics/stratified_results.csv',aggregated)
    # Persist actual source pointers for base edges whose old training registry
    # held no source payload. This enriches this new report only.
    provenance={}
    for x in read(OUT/'POTENTIAL_RELATIONS.jsonl'):
        for v in x['transport_actual_contexts']:
            eid=v['edge_id'];edge=next(e for e in index.edges if e['edge_id']==eid)
            if eid in provenance:continue
            ss=src.get(eid,[]) if edge['is_base'] else sources(edge,index.registry)
            provenance[eid]=dict(edge_id=eid,is_base=edge['is_base'],source_keys=edge['source_keys'],pages=edge['pages'],sources=[I.source_pointer(z) for z in ss],source_location_retained=bool(edge['pages']),full_source_payload_available=bool(ss))
    save(OUT/'potential/context_provenance.jsonl',list(provenance.values()))
    # Choose diagnostic illustrations by fixed direction-delta rule, on validation
    # only. Display selection is not another score/threshold selection.
    case_rows=[]
    for (cid,task),row in allranks['T0',SEEDS[0]].items():
        h,r=row['query_anchor'],row['query_relation'];deltas={}
        for m in ['T0','T1','T2','T3','T5']:
            deltas[m]=float(np.mean([1/allranks[m,s][cid,task]['rank']-1/allranks['text_only',s][cid,task]['rank'] for s in SEEDS]))
        case_rows.append(dict(id=cid,task=task,head_index=h,relation_index=r,deltas_vs_text=deltas,metadata=querymeta[h,r]))
    save(OUT/'diagnostics/direction_deltas.jsonl',case_rows)
    cases=[]
    for tag,method,sign in [('transport_win','T0',1),('transport_loss','T0',-1),('cross_document_win','T2',1),('cross_document_loss','T2',-1)]:
        pool=[x for x in case_rows if method!='T2' or x['metadata']['source_observable']]
        q=sorted(pool,key=lambda x:(-sign*x['deltas_vs_text'][method],x['id'],x['task']))[0];h,r=q['head_index'],q['relation_index'];contexts=[]
        for vi,sv in zip(selection[method]['ids'][ki[h,r]],selection[method]['scores'][ki[h,r]]):
            if vi<0:continue
            view=index.views[int(vi)];edge=index.edges[view['edge_index']];ss=src.get(edge['edge_id'],[]) if edge['is_base'] else sources(edge,index.registry)
            contexts.append(dict(view_id=int(vi),edge_id=edge['edge_id'],triple=edge['triple'],anchor=index.entities[view['anchor']],neighbor=index.entities[view['neighbor']],relation=index.cat['relations'][view['relation']%15],inverse_view=view['relation']>=15,score=float(sv),documents=edge['pages'],sources=[I.source_pointer(z) for z in ss[:2]]))
        cases.append(dict(tag=tag,method=method,query=q,claim=claims[q['id']],head=entities[ei[claims[q['id']]['head_entity_id']]],tail=entities[ei[claims[q['id']]['tail_entity_id']]],target_sources=[I.source_pointer(x) for x in src[q['id']]],seed_ranks={m:[allranks[m,s][q['id'],q['task']]['rank'] for s in SEEDS] for m in ['text_only','T0','T1','T2','T3','T5']},contexts=contexts,proxy_ranking_case_not_fact_validation=True))
    save(OUT/'diagnostics/cases.jsonl',cases)
    save(OUT/'diagnostics/complete.json',dict(validation_only=True,graph_components_reused_not_recomputed=True,independent_new_test=False,CPU_only=True,LLM_requests=0,source_pointer_edges=len(provenance),validation_query_keys=len(querymeta)))
    print('diagnostics complete',len(cases),flush=True)


if __name__=='__main__':main()
