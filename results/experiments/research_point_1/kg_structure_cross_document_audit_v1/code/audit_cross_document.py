"""Exact shared facts, provisional alias/semantic pairs, scope and granularity."""
from common_audit import *
import torch


def signature(x):
    def strip(v):
        if isinstance(v,dict):return {k:strip(z) for k,z in v.items() if k in ['text','role','condition','operator','value','unit','modality']}
        if isinstance(v,list):return [strip(z) for z in v]
        return I.norm(v)
    return canonical(dict(condition=strip(x.get('conditions_source')),modality=I.norm(x.get('modality')),pump_type=I.norm(x.get('pump_type')),service=I.norm(x.get('service'))))


def protected(s):return sorted(set(re.findall(r'最大|最小|最高|最低|前|后|内|外|上|下|进口|出口|吸入|排出|正转|反转|不|禁止|never|not|\d+(?:\.\d+)?',I.norm(s))))


def main():
    if (OUT/'cross_document_complete.json').exists():print('REUSE cross-document audit');return
    torch.set_num_threads(2);d,entities,E,S,C,src=dataset();registry=d['schema']['relation_registry'];aliases=read(STUDY/'data/entity_alias_closure.json')[:2150];alias={e['entity_id']:aliases[j] for j,e in enumerate(entities)}
    graph,_,_=graphs(E,C,set(C));component={e:j for j,cc in enumerate(nx.connected_components(graph)) for e in cc}
    edocs=defaultdict(set);efams=defaultdict(set);escope=defaultdict(set);cdocs={};cfams={};sig={}
    typed={};labelgroups=defaultdict(list);aliasgroups=defaultdict(list);cross_type_alias=defaultdict(list)
    for e in entities:
        key=(e['entity_type'],I.norm(e['label_zh']));typed[key]=e['entity_id'];labelgroups[key].append(e['entity_id']);aliasgroups[e['entity_type'],alias[e['entity_id']]].append(e['entity_id']);cross_type_alias[alias[e['entity_id']]].append(e['entity_id'])
    for cid,c in C.items():
        cdocs[cid]={x['doc_id'] for x in src[cid]};cfams[cid]={x['source_family_id'] for x in src[cid]};sig[cid]={signature(x) for x in src[cid]}
        for s in ['head','tail']:
            eid=c[s+'_entity_id'];edocs[eid].update(cdocs[cid]);efams[eid].update(cfams[cid]);escope[eid].update(I.norm(x.get('pump_type')) for x in src[cid] if x.get('pump_type'))
    shared_claims=[]
    for cid in sorted(C):
        if len(cdocs[cid])>=2:
            shared_claims.append(dict(claim_id=cid,claim=C[cid],documents=sorted(cdocs[cid]),source_families=sorted(cfams[cid]),assertions=len(src[cid]),condition_scope_signatures=len(sig[cid]),all_conditions_unspecified=all(not x.get('conditions_source') for x in src[cid]),sources=[I.source_pointer(x) for x in src[cid]],caution='Same Claim family does not guarantee equivalent conditions or independent sources'))
    save(OUT/'cross_document_shared_claims.jsonl',shared_claims)
    # Entire initial candidate pool is evidence-bearing occurrences, not 8003
    # confirmed facts. Group by exact typed canonical statement only.
    initial=defaultdict(list);candidate_entity_docs=defaultdict(set);exactbase=defaultdict(list)
    for cid,c in C.items():exactbase[(E[c['head_entity_id']]['entity_type'],I.norm(E[c['head_entity_id']]['label_zh']),c['relation'],E[c['tail_entity_id']]['entity_type'],I.norm(E[c['tail_entity_id']]['label_zh']))].append(cid)
    audit={k:x for x in d['audit'] for k in I.record_ids(x)}
    for x in d['normalized']:
        initial[tuple(I.core_tuple(x))].append(x)
        for side in ['head','tail']:candidate_entity_docs[x[side+'_type'],I.norm(x[side+'_canonical_zh'])].add(x['doc_id'])
    candidate_clusters=[]
    for key,rr in sorted(initial.items()):
        docs={x['doc_id'] for x in rr}
        if len(docs)<2:continue
        states=Counter();legal=0
        for x in rr:
            a=next((audit[u] for u in I.record_ids(x) if u in audit),x);states[a.get('decision','missing')]+=1
            rule=registry.get(x['relation'])
            legal+=bool(rule and x['head_type'] in rule['domain'] and x['tail_type'] in rule['range'])
        candidate_clusters.append(dict(cluster_id='CROSS-'+digest(key)[:20],canonical_statement=list(key),occurrences=len(rr),documents=sorted(docs),source_families=sorted({x['source_family_id'] for x in rr}),automatic_status_counts=dict(states),schema_legal_occurrences=legal,condition_scope_variants=len({signature(x) for x in rr}),all_conditions_unspecified=all(not x.get('conditions_source') for x in rr),matching_published_claim_ids=exactbase[key],record_ids=[x['triple_id'] for x in rr],sources=[I.source_pointer(x) for x in rr],label='Exact canonical expression, not verified condition-complete same fact'))
    save(OUT/'initial_candidate_cross_document_clusters.jsonl',candidate_clusters)
    pairrows=[]
    for a,b in itertools.combinations(sorted(I.BUILD),2):
        ec={e for e in E if a in edocs[e] and b in edocs[e]};cc={c for c in C if a in cdocs[c] and b in cdocs[c]}
        ci=[x for x in candidate_clusters if a in x['documents'] and b in x['documents']]
        pairrows.append(dict(document_a=a,document_b=b,shared_published_entity_ids=len(ec),shared_published_claim_ids=len(cc),shared_initial_canonical_clusters=len(ci),initial_clusters_spanning_different_families=sum(len(x['source_families'])>1 for x in ci)))
    csvsave('document_pair_overlap.csv',pairrows)
    # Alias closure is inherited from the experiment's finite source mapping.
    # It is an alignment hypothesis, not an authorized graph transformation.
    aliasledger=[]
    for (typ,root),ids in sorted(aliasgroups.items()):
        if len(ids)<2:continue
        aliasledger.append(dict(cluster_id='ALIAS-'+digest([typ,root])[:20],entity_type=typ,alias_root=root,entities=[E[e] for e in sorted(ids)],documents=sorted(set().union(*(edocs[e] for e in ids))),scope_variants=sorted(set().union(*(escope[e] for e in ids))),protected_token_signatures=sorted({canonical(protected(E[e]['label_zh'])) for e in ids}),full_components=sorted({component[e] for e in ids}),automatic_hypothesis=True,confirmed_synonymous=False))
    save(OUT/'alias_hypothesis_clusters.jsonl',aliasledger)
    # Cache is frozen pretrained BGE, not a new embedding model or current
    # fine-tuned SimKGC. Only its base entity rows are used.
    features=torch.load(STUDY/'index/vectors.pt',map_location='cpu',weights_only=True)['entities'][:2150].numpy()
    similarity=features@features.T;types=[e['entity_type'] for e in entities];idx={e['entity_id']:j for j,e in enumerate(entities)}
    profile=defaultdict(set)
    for c in C.values():
        h,r,t=c['head_entity_id'],c['relation'],c['tail_entity_id'];profile[h].add(('out',r,E[t]['entity_type']));profile[t].add(('in',r,E[h]['entity_type']))
    semanticpairs=[];seen=set()
    for i,e in enumerate(entities):
        candidates=[j for j in np.argsort(-similarity[i],kind='stable') if j!=i and types[j]==types[i] and len(edocs[e['entity_id']]|edocs[entities[j]['entity_id']])>=2][:5]
        for j in candidates:
            if similarity[i,j]<.85:continue
            u,v=e['entity_id'],entities[j]['entity_id'];key=tuple(sorted([u,v]))
            if key in seen:continue
            seen.add(key);aa,bb=I.norm(e['label_zh']),I.norm(entities[j]['label_zh']);p,q=profile[u],profile[v]
            semanticpairs.append(dict(pair_id='SEM-'+digest(key)[:20],entity_a=e,entity_b=entities[j],cosine=float(similarity[i,j]),documents_a=sorted(edocs[u]),documents_b=sorted(edocs[v]),same_full_component=component[u]==component[v],saved_alias_same=alias[u]==alias[v],substring_granularity_candidate=aa in bb or bb in aa,protected_tokens_differ=protected(aa)!=protected(bb),scope_signatures_disjoint=bool(escope[u] and escope[v] and not escope[u]&escope[v]),relation_role_profile_jaccard=len(p&q)/max(1,len(p|q)),alias_confirmed=False,interpretation='High semantic similarity can be alias, subtype, action granularity, negation, model or condition difference'))
    save(OUT/'semantic_entity_pair_candidates.jsonl',sorted(semanticpairs,key=lambda x:(-x['cosine'],x['pair_id'])))
    # High-similarity statement pairs, exact same directed predicate and types.
    ids=sorted(C);H=np.array([idx[C[c]['head_entity_id']] for c in ids]);T=np.array([idx[C[c]['tail_entity_id']] for c in ids]);hs=similarity[H[:,None],H[None,:]];ts=similarity[T[:,None],T[None,:]]
    relationpairs=[];bins=Counter()
    for i in range(len(ids)):
        for j in range(i+1,len(ids)):
            a,b=ids[i],ids[j];x,y=C[a],C[b]
            if x['relation']!=y['relation'] or E[x['head_entity_id']]['entity_type']!=E[y['head_entity_id']]['entity_type'] or E[x['tail_entity_id']]['entity_type']!=E[y['tail_entity_id']]['entity_type']:continue
            if len(cdocs[a]|cdocs[b])<2:continue
            value=float(min(hs[i,j],ts[i,j]))
            if value<.85:continue
            for threshold in [.85,.9,.95]:
                if value>=threshold:bins[f'min_endpoint_cosine_ge_{threshold}']+=1
            relationpairs.append(dict(pair_id='FACTSIM-'+digest([a,b])[:20],claim_a=a,claim_b=b,relation=x['relation'],head_cosine=float(hs[i,j]),tail_cosine=float(ts[i,j]),min_endpoint_cosine=value,documents_a=sorted(cdocs[a]),documents_b=sorted(cdocs[b]),source_families_a=sorted(cfams[a]),source_families_b=sorted(cfams[b]),different_declared_families=bool(cfams[a].isdisjoint(cfams[b])),same_head_id=x['head_entity_id']==y['head_entity_id'],same_tail_id=x['tail_entity_id']==y['tail_entity_id'],same_full_component=component[x['head_entity_id']]==component[y['head_entity_id']],head_scope_disjoint=bool(escope[x['head_entity_id']] and escope[y['head_entity_id']] and not escope[x['head_entity_id']]&escope[y['head_entity_id']]),exact_condition_scope_signature_equal=sig[a]==sig[b],entities_a=[E[x['head_entity_id']],E[x['tail_entity_id']]],entities_b=[E[y['head_entity_id']],E[y['tail_entity_id']]],sources_a=[I.source_pointer(s) for s in src[a]],sources_b=[I.source_pointer(s) for s in src[b]],same_fact_confirmed=False))
    save(OUT/'semantic_claim_pair_candidates.jsonl',sorted(relationpairs,key=lambda x:(-x['min_endpoint_cosine'],x['pair_id'])))
    # Descriptive canonical-name granularity, not extraction-error counts.
    granularity=[]
    for typ in sorted(set(types)):
        ee=[e for e in entities if e['entity_type']==typ];lengths=[len(I.norm(e['label_zh'])) for e in ee]
        granularity.append(dict(entity_type=typ,n=len(ee),median_label_chars=float(np.median(lengths)),label_chars_ge20=sum(n>=20 for n in lengths),label_chars_ge40=sum(n>=40 for n in lengths),numeric_or_model_token_candidates=sum(bool(re.search(r'\d|[A-Z]{2,}',e['label_zh'])) for e in ee),shared_across_documents=sum(len(edocs[e['entity_id']])>=2 for e in ee),seen_in_multiple_initial_docs=sum(len(candidate_entity_docs[typ,I.norm(e['label_zh'])])>=2 for e in ee)))
    csvsave('entity_granularity.csv',granularity)
    # Topic overlap is distinct from shared facts. Terms come from direct
    # existing canonical/surface pairs, not new translations or external texts.
    anchors=['泵','轴承','轴封','叶轮','机械密封','汽蚀','振动','对中','润滑','泄漏'];mentions=[];anchor_rows=[]
    for label in anchors:
        forms={I.norm(x[side+'_surface']) for pop in [d['normalized'],d['graph']['source_records']] for x in pop for side in ['head','tail'] if I.norm(x[side+'_canonical_zh'])==I.norm(label) and 3<=len(I.norm(x[side+'_surface']))<=80}
        pages=defaultdict(list)
        for (doc,page),x in d['pages'].items():
            flat=I.norm(x['page_text'])
            if any(f in flat for f in forms):pages[doc].append(page)
        anchor_rows.append(dict(concept_label=label,existing_surface_forms=len(forms),documents_with_literal_mentions=len(pages),pages_with_mentions=sum(len(v) for v in pages.values())))
        mentions.append(dict(concept_label=label,existing_surface_forms=sorted(forms),document_pages=dict(pages),not_shared_fact_count=True))
    csvsave('manual_concept_mentions.csv',anchor_rows);save(OUT/'manual_concept_mention_ledger.jsonl',mentions)
    summary=dict(published_claims=1400,published_assertions=1456,claims_multi_document=len(shared_claims),claims_multi_declared_family=sum(len(cfams[c])>=2 for c in C),entities_multi_document=sum(len(edocs[e])>=2 for e in E),entities_multi_declared_family=sum(len(efams[e])>=2 for e in E),same_typed_label_duplicate_groups=sum(len(v)>1 for v in labelgroups.values()),same_type_saved_alias_clusters=len(aliasledger),entities_in_same_type_alias_clusters=sum(len(x['entities']) for x in aliasledger),cross_type_alias_roots=sum(len({E[e]['entity_type'] for e in ids})>1 for ids in cross_type_alias.values()),candidate_unique_canonical_statements=len(initial),candidate_cross_document_exact_clusters=len(candidate_clusters),candidate_cross_document_different_family_clusters=sum(len(x['source_families'])>=2 for x in candidate_clusters),candidate_cross_document_clusters_with_any_published_claim=sum(bool(x['matching_published_claim_ids']) for x in candidate_clusters),entity_semantic_pairs_ge085=len(semanticpairs),entity_semantic_pairs_disconnected=sum(not x['same_full_component'] for x in semanticpairs),entity_semantic_pairs_ge090=sum(x['cosine']>=.9 for x in semanticpairs),claim_semantic_pair_bins=bins,claim_semantic_pairs_disconnected=sum(not x['same_full_component'] for x in relationpairs),base_entities_multi_initial_documents=sum(len(candidate_entity_docs[e['entity_type'],I.norm(e['label_zh'])])>=2 for e in entities),semantic_pairs_are_proposals_not_truth=True,topic_overlap_not_fact_equivalence=True)
    save(OUT/'cross_document_complete.json',summary);print('CROSS_DOCUMENT',summary,flush=True)


if __name__=='__main__':main()
