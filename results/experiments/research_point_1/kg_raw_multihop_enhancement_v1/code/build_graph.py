"""All-status G_raw, administrative masking BEFORE any bridge/path search."""
import time
import numpy as np
import torch
from raw_io import *

CONFIG = dict(seeds=SEEDS, answers=2150, held_folds=['valid','test'], schema_filter=False,
    status_filter=False, semantic_copy_rule=dict(both_cosine=.95, one_alias_exact_other_cosine=.90,
    types_equal=True, relation_agnostic=True), bridge_topk=4, bridge_prefetch=24,
    bridge_semantic_floor=.60, branch_limit=16, beam_width=48, max_paths_per_query=384,
    max_hops=3, real_min_hops=2, max_virtual=2, no_consecutive_virtual=True,
    support_topm=8, fusion_grid=[0.,.05,.1,.2], selected_on='mean validation MRR over three reused seeds',
    no_new_supervision_from_raw=True, no_test_prediction=True,
    four_hop_policy='Only diagnostic extension if 3-hop bridges contain <=1 real edge for most supported queries')

def components(n, triples):
    adj=[set() for _ in range(n)]
    for h,r,t in triples:
        if h!=t: adj[h].add(t); adj[t].add(h)
    ids=np.full(n,-1,np.int32); sizes=[]
    for h in range(n):
        if ids[h]>=0: continue
        cid=len(sizes); stack=[h]; ids[h]=cid; count=0
        while stack:
            u=stack.pop(); count+=1
            for v in adj[u]:
                if ids[v]<0: ids[v]=cid; stack.append(v)
        sizes.append(count)
    return adj,ids,sizes

def stats(n, edges, nbase):
    triples=[e['triple'] for e in edges]; adj,ci,sizes=components(n,triples)
    out=[set() for _ in range(n)]; inc=[set() for _ in range(n)]
    for h,r,t in triples:
        if h!=t: out[h].add(t); inc[t].add(h)
    deg=np.array(list(map(len,adj))); cedge=Counter(ci[h] for h,r,t in triples)
    u2=sum(d*(d-1)//2 for d in deg)
    u3=sum((len(adj[u])-1)*(len(adj[v])-1)-len(adj[u]&adj[v]) for u in range(n) for v in adj[u] if u<v)
    d2=sum(len(inc[u])*len(out[u])-len(inc[u]&out[u]) for u in range(n))
    d3=sum((len(inc[u])-int(v in inc[u]))*(len(out[v])-int(u in out[v]))-len((inc[u]-{v})&(out[v]-{u})) for u in range(n) for v in out[u])
    active=int((deg>0).sum()); active_sizes=[s for s in sizes if s>1]
    return dict(registry_entities=n, active_entities=active, edges=len(edges), unordered_pairs=sum(deg)//2,
        self_loops=sum(h==t for h,r,t in triples), components_including_isolates=len(sizes), active_components=len(active_sizes),
        single_semantic_edge_components=sum(sizes[c]==2 and ct==1 for c,ct in cedge.items()),
        largest_component=max(sizes), largest_active_fraction=max(sizes)/max(1,active),
        degree_counts={str(k):int((deg==k).sum()) for k in [0,1,2]}|{'ge3':int((deg>=3).sum())},
        base_answer_zero_degree=int((deg[:nbase]==0).sum()), undirected_simple_node_paths_2=int(u2),
        undirected_simple_node_paths_3=int(u3), directed_simple_node_paths_2=int(d2), directed_simple_node_paths_3=int(d3),
        inverse_traversal_oriented_paths_2=int(2*u2), inverse_traversal_oriented_paths_3=int(2*u3),
        relation_edges=dict(Counter(str(r) for h,r,t in triples))),ci,deg

def main():
    if (EXP/'data/freeze.json').exists(): print('REUSE data freeze'); return
    start=time.time(); torch.set_num_threads(4)
    save(EXP/'config.json',CONFIG)
    # Pre-change integrity snapshots cover every prior RP1/RP2/RP3 research file.
    old_files=[]
    for folder in [EXP.parent,ROOT/'data/kg/marine_pump',ROOT/'results/experiments/research_point_2',ROOT/'results/experiments/research_point_3']:
        if not folder.exists(): continue
        for p in sorted(folder.rglob('*')):
            if not p.is_file() or p.is_relative_to(EXP) or '__pycache__' in p.parts: continue
            st=p.stat(); old_files.append(dict(path=str(p.relative_to(ROOT)),bytes=st.st_size,mtime_ns=st.st_mtime_ns))
    save(EXP/'verification/prior_files.json',old_files)
    d=locked(); cat=read(OLD/'data/catalogue.json'); split=read(OLD/'data/base_split.jsonl')
    blocks=read(OLD/'audit_only/copy_blockers.json'); oldex={x['record_id']:x for x in read(OLD/'audit_only/candidate_exclusions.jsonl')}
    entities=[dict(x) for x in cat['entities']]; label={normkey(e['entity_type'],e['label_zh']):e['index'] for e in entities}
    rels=cat['relations']; ri={r:i for i,r in enumerate(rels)}; R=len(rels)
    aliases=UF()
    for pop in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for x in pop:
            for side in ['head','tail']:
                aliases.join('L|'+x[side+'_type']+'|'+I.norm(x[side+'_canonical_zh']), 'S|'+I.norm(x[side+'_surface']))
    def endpoint(x,s):
        key=normkey(x[s+'_type'],x[s+'_canonical_zh'])
        if key not in label:
            idx=len(entities); label[key]=idx
            entities.append(dict(index=idx, entity_id='RAW-'+digest(key)[:24],entity_type=key[0],label_zh=x[s+'_canonical_zh'],source='full_normalized_candidate'))
        return label[key]
    audit={k:x for x in d['audit'] for k in I.record_ids(x)}
    records=[]; norm={x['triple_id']:x for x in d['normalized']}
    for x in d['normalized']:
        assert x['doc_id'] in I.BUILD and x['relation'] in ri
        a=next((audit[k] for k in I.record_ids(x) if k in audit),x)
        tr=[endpoint(x,'head'),ri[x['relation']],endpoint(x,'tail')]
        rule=cat['registry'][x['relation']]
        records.append(dict(record_id=x['triple_id'],triple=tr,source=I.source_pointer(x),
            audit_status=a.get('decision'), normalized_status=x.get('decision'),
            old_rejection_reasons=a.get('rejection_reasons',[]),
            schema_compatible=x['head_type'] in rule['domain'] and x['tail_type'] in rule['range'],
            exclusions=list(oldex[x['triple_id']]['reasons'])))
    ea=[aliases.find('L|'+e['entity_type']+'|'+I.norm(e['label_zh'])) for e in entities]
    assert len(records)==8003 and len(split)==1400
    held=[x for x in split if x['fold']!='train']; heldtr=np.array([x['triple'] for x in held])
    # Alias roots and saved masks are administrative only, never path/scoring features.
    assert all(tuple(sorted([ea[x['triple'][0]],ea[x['triple'][2]]])) in set(map(tuple,blocks['pairs'])) for x in held)
    vec=torch.load(OLD/'index/vectors.pt',map_location='cpu',weights_only=True)['entities'].numpy()
    survivors=[x for x in records if not x['exclusions']]
    assert all(max(x['triple'][::2])<len(vec) for x in survivors)
    types=[e['entity_type'] for e in entities]
    heldh=heldtr[:,0]; heldt=heldtr[:,2]
    def near_pairs(triples):
        result=[]
        for h,r,t in triples:
            hits=[]
            for hh,tt in [(heldh,heldt),(heldt,heldh)]:
                compatible=np.array([types[h]==types[a] and types[t]==types[b] for a,b in zip(hh,tt)])
                a=vec[hh]@vec[h]; b=vec[tt]@vec[t]
                ae=np.array([ea[h]==ea[v] for v in hh]); be=np.array([ea[t]==ea[v] for v in tt])
                mask=compatible&(((a>=.95)&(b>=.95))|(ae&(b>=.90))|(be&(a>=.90)))
                hits.extend(dict(held_claim=held[j]['claim_id'],cos_head=float(a[j]),cos_tail=float(b[j]),fold=held[j]['fold']) for j in np.where(mask)[0])
            result.append(hits)
        return result
    copyledger=[]
    for x,hits in zip(survivors,near_pairs([x['triple'] for x in survivors])):
        if hits:
            x['exclusions'].append('conservative_semantic_copy_risk')
            copyledger.append(dict(record_id=x['record_id'],hits=hits))
    # Base context follows the same held-page/quote rule, not just its evidence payload.
    sources=defaultdict(list)
    for x in d['graph']['source_records']:sources[x['expanded_claim_id']].append(x)
    pages=set(map(tuple,blocks['pages'])); grams=set(blocks['quotegrams']); units=set(blocks['units'])
    safe_base=[]; baseblocked=[]; train=[x for x in split if x['fold']=='train']
    for x,hits in zip(train,near_pairs([x['triple'] for x in train])):
        ss=[I.source_pointer(s) for s in sources[x['claim_id']] if (s['doc_id'],s['pdf_page_number']) not in pages and not (shingles(s['evidence_text'])&grams) and not (set(s.get('evidence_unit_ids') or [])&units)]
        if ss and not hits: safe_base.append(dict(edge_id=x['claim_id'],triple=x['triple'],is_base=True,records=[],sources=ss))
        else: baseblocked.append(dict(claim_id=x['claim_id'],no_safe_source=not bool(ss),near_copy_risk=bool(hits)))
    def dedup(rr):
        edges={}
        for row in rr:
            tr=tuple(row['triple']);e=edges.setdefault(tr,dict(edge_id='RAW-'+digest(tr)[:20],triple=list(tr),records=[],is_base=False,sources=[]))
            e['records'].append(row['record_id']);e['sources'].append(row['source'])
        return list(edges.values())
    full=dedup(records); visible=[x for x in records if not x['exclusions']]; masked=dedup(visible)
    merged={tuple(x['triple']):x for x in masked}
    for e in safe_base:
        tr=tuple(e['triple'])
        if tr in merged:
            merged[tr]['is_base']=True;merged[tr]['sources']+=e['sources'];merged[tr]['base_claim_id']=e['edge_id']
        else:merged[tr]=e
    train_edges=sorted(merged.values(),key=lambda e:e['triple'])
    for j,e in enumerate(train_edges):e['edge_index']=j
    fullstats,_,_=stats(len(entities),full,2150)
    trainstats,ci,deg=stats(len(entities),train_edges,2150)
    for label_,es in [('full',full),('train',train_edges)]:
        docs=defaultdict(lambda:dict(records=0,edges=set(),entities=set()))
        for e in es:
            for s in e['sources']:
                doc=s['doc_id'];docs[doc]['records']+=1;docs[doc]['edges'].add(e['edge_id']);docs[doc]['entities'].update(e['triple'][::2])
        save(EXP/f'analysis/{label_}_documents.json',{k:{kk:len(vv) if isinstance(vv,set) else vv for kk,vv in v.items()} for k,v in docs.items()})
    cc=dict(entities=entities,relations=rels,registry=cat['registry'],nbase=2150,old_vector_entities=len(vec))
    for name,value in [('catalogue.json',cc),('record_graph.jsonl',records),('full_edges.jsonl',full),('train_edges.jsonl',train_edges),('validation_targets.jsonl',read(OLD/'data/validation_targets.jsonl')),('validation_truth.json',read(OLD/'data/validation_truth.json'))]:save(EXP/'data'/name,value)
    # Test facts are not copied into computational outputs. Only blockers stay audit-only.
    save(EXP/'verification/semantic_copy_blockers.jsonl',copyledger)
    save(EXP/'verification/base_context_exclusions.jsonl',baseblocked)
    npz(EXP/'data/structure.npz',components=ci,degree=deg)
    save(EXP/'analysis/raw_structure.json',dict(full=fullstats,train=trainstats))
    save(EXP/'verification/domain_inputs.json',dict(revision=I.REV,hashes=d['inputs'].hashes))
    source_paths=[OLD/'data/base_split.jsonl',OLD/'audit_only/copy_blockers.json',OLD/'data/catalogue.json',OLD/'index/vectors.pt']
    save(EXP/'verification/reused_input_hashes.json',{str(p.relative_to(ROOT)):sha(p) for p in source_paths})
    summary=dict(records=len(records),raw_export_rows=len(d['raw']),full_dedup_edges=len(full),train_visible_records=len(visible),train_raw_dedup_edges=len(masked),safe_base_context_edges=len(safe_base),train_union_edges=len(train_edges),all_entities=len(entities),train_max_entity=max(max(e['triple'][::2]) for e in train_edges),old_statuses=dict(Counter(x['audit_status'] for x in records)),visible_statuses=dict(Counter(x['audit_status'] for x in visible)),visible_schema_illegal_records=sum(not x['schema_compatible'] for x in visible),exclusions=dict(Counter(s for x in records for s in x['exclusions'])),new_copy_risk_records=len(copyledger),historical_base_labels_with_unsafe_context=len(baseblocked),wall_seconds=time.time()-start)
    save(EXP/'data/freeze.json',dict(summary=summary,config_sha256=sha(EXP/'config.json'),files={p.name:sha(p) for p in sorted((EXP/'data').glob('*.json*'))}))
    print(canonical(summary),flush=True)

if __name__=='__main__':main()
