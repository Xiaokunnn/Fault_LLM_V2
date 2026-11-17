"""Reuse frozen BGE caches, encode missing raw-edge texts, build virtual layers."""
import gc
import time
import numpy as np
import torch
from torch.nn import functional as F
from raw_io import *

def main():
    if (EXP/'index/freeze.json').exists(): print('REUSE vector/bridge index'); return
    torch.set_num_threads(4); start=time.perf_counter(); dev=device()
    cat=read(EXP/'data/catalogue.json'); edges=load_graph(); cfg=read(EXP/'config.json')
    n=len(cat['entities']); R=len(cat['relations']); old=torch.load(OLD/'index/vectors.pt',map_location='cpu',weights_only=True)
    ev=F.normalize(old['entities'].float(),dim=-1); rv=old['relations'].float()
    assert max(max(e['triple'][::2]) for e in edges)<len(ev)
    oldviews=read(OLD/'index/oriented_views.jsonl'); oldedges=read(OLD/'index/edges.jsonl')
    existing={tuple([*oldedges[v['edge_index']]['triple'],v['inverse']]):i for i,v in enumerate(oldviews)} if oldviews and 'inverse' in oldviews[0] else {tuple([*oldedges[v['edge_index']]['triple'],i%2]):i for i,v in enumerate(oldviews)}
    views=[]; missing=[]; plain=torch.zeros((2*len(edges),512))
    for j,e in enumerate(edges):
        h,r,t=e['triple']
        for inv in [0,1]:
            a,b=(t,h) if inv else (h,t); dr=r+R*inv; idx=len(views)
            relation=('逆向关系：' if inv else '')+cat['registry'][cat['relations'][r]]['label_zh']
            text=f"主体：{cat['entities'][a]['label_zh']}。关系：{relation}。客体：{cat['entities'][b]['label_zh']}。"
            views.append(dict(view_id=idx,edge_index=j,anchor=a,neighbor=b,relation=dr,inverse_traversal=bool(inv),is_base=e['is_base'],plain=text))
            oi=existing.get((h,r,t,inv))
            if oi is not None: plain[idx]=old['plain'][oi]
            else:missing.append((idx,text))
    if missing:
        from transformers import AutoTokenizer, AutoModel
        model_path=ROOT/'data/model/BAAI-bge-small-zh-v1.5-r7999e1d'
        tok=AutoTokenizer.from_pretrained(model_path,local_files_only=True)
        model=AutoModel.from_pretrained(model_path,local_files_only=True).to(dev).eval()
        with torch.inference_mode():
            for off in range(0,len(missing),64):
                batch=missing[off:off+64]; x=tok([s for _,s in batch],padding=True,truncation=True,max_length=128,return_tensors='pt').to(dev)
                v=F.normalize(model(**x).last_hidden_state[:,0].float(),dim=-1).cpu()
                plain[[i for i,_ in batch]]=v
        del model;gc.collect()
        if dev=='cuda':torch.cuda.empty_cache()
    # Only active train-visible nodes and the fixed label-only answer catalogue.
    structure=np.load(EXP/'data/structure.npz'); ci=structure['components']; deg=structure['degree']
    eligible=np.where((deg>0)|(np.arange(n)<cat['nbase']))[0]; assert eligible.max()<len(ev)
    profiles=np.zeros((len(ev),2*R),np.float32); adj=[set() for _ in range(len(ev))]
    for e in edges:
        h,r,t=e['triple'];profiles[h,r]+=1;profiles[t,r+R]+=1;adj[h].add(t);adj[t].add(h)
    profiles/=np.maximum(np.linalg.norm(profiles,axis=1,keepdims=True),1)
    pattern=np.zeros_like(profiles)
    for h in eligible:
        if adj[h]:pattern[h]=profiles[list(adj[h])].mean(0)
    pattern/=np.maximum(np.linalg.norm(pattern,axis=1,keepdims=True),1)
    ids=torch.as_tensor(eligible,device=dev); eg=ev.to(dev); pg=torch.tensor(profiles,device=dev); lg=torch.tensor(pattern,device=dev)
    types=[x['entity_type'] for x in cat['entities']]; typecodes={t:i for i,t in enumerate(sorted(set(types)))}
    ti=torch.tensor([typecodes[t] for t in types[:len(ev)]],device=dev); comps=torch.tensor(ci[:len(ev)],device=dev)
    bridge_rows={name:[] for name in ['B1','B2','B3','random']}; rng=np.random.default_rng(16112026)
    for off in range(0,len(eligible),128):
        aa=ids[off:off+128]; sim=eg[aa]@eg[ids].T
        sim[comps[aa,None]==comps[ids][None,:]]=-2.
        ss,jj=sim.topk(min(cfg['bridge_prefetch'],len(ids)),dim=-1); dest=ids[jj]
        role=(pg[aa,None,:]*pg[dest]).sum(-1); pat=(lg[aa,None,:]*lg[dest]).sum(-1); same=(ti[aa,None]==ti[dest]).float()
        values={'B1':ss,'B2':.75*ss+.15*same+.10*role,'B3':.65*ss+.15*same+.10*role+.10*pat}
        ss=ss.cpu().numpy(); dest=dest.cpu().numpy(); role=role.cpu().numpy(); pat=pat.cpu().numpy(); same=same.cpu().numpy()
        for name,val in values.items():
            val=val.cpu().numpy()
            for q,a in enumerate(aa.cpu().tolist()):
                select=sorted([j for j in range(dest.shape[1]) if ss[q,j]>=cfg['bridge_semantic_floor']],key=lambda j:(-float(val[q,j]),int(dest[q,j])))[:cfg['bridge_topk']]
                for j in select:
                    b=int(dest[q,j]); bridge_rows[name].append(dict(a=a,b=b,component_a=int(ci[a]),component_b=int(ci[b]),semantic_cos=float(ss[q,j]),type_match=bool(same[q,j]),role_cos=float(role[q,j]),pattern_cos=float(pat[q,j]),score=float(val[q,j]),kind=name,provenance='frozen BGE labels + masked all-status directed-role counts; virtual, not a fact'))
    bytype=defaultdict(list)
    for x in eligible:bytype[types[x]].append(int(x))
    # Same source node, count and destination-type distribution as B3.
    for z in bridge_rows['B3']:
        a=z['a']; pool=[b for b in bytype[types[z['b']]] if ci[b]!=ci[a]]
        b=int(rng.choice(pool)); cosine=float(ev[a]@ev[b])
        bridge_rows['random'].append(dict(a=a,b=b,component_a=int(ci[a]),component_b=int(ci[b]),semantic_cos=cosine,type_match=types[a]==types[b],role_cos=float(profiles[a]@profiles[b]),pattern_cos=float(pattern[a]@pattern[b]),score=z['score'],kind='random',provenance='type/count/source-matched random destination; score distribution copied from B3'))
    save(EXP/'index/oriented_views.jsonl',views)
    for name,rows in bridge_rows.items():save(EXP/f'bridges/{name}.jsonl',rows)
    npz(EXP/'index/vectors.npz',entities=ev.numpy(),relations=rv.numpy(),plain=plain.numpy(),queries=old['queries'].float().numpy(),profiles=profiles,patterns=pattern)
    summary={name:dict(directed_proposals=len(rr),unique_undirected_pairs=len({tuple(sorted([x['a'],x['b']])) for x in rr}),source_nodes=len({x['a'] for x in rr}),mean_semantic_cos=float(np.mean([x['semantic_cos'] for x in rr])),type_match_fraction=float(np.mean([x['type_match'] for x in rr]))) for name,rr in bridge_rows.items()}
    save(EXP/'index/freeze.json',dict(eligible_nodes=len(eligible),views=len(views),reused_plain_views=len(views)-len(missing),newly_encoded_plain_views=len(missing),reused_entity_vectors=len(ev),no_held_quote_encoding=True,bridges=summary,device=dev,wall_seconds=time.perf_counter()-start))
    print(canonical(read(EXP/'index/freeze.json')),flush=True)

if __name__=='__main__':main()
