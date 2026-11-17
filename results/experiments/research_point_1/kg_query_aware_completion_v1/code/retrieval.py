"""Query-only R0-R3 retrieval; answer-independent frozen contexts."""
from collections import Counter,defaultdict
import time
import numpy as np
import torch
from io_utils import *
from build_index import edge_sources


class Retriever:
    def __init__(self):
        self.cat=read(EXP/'data/catalogue.json');self.R=len(self.cat['relations']);self.n=self.cat['nbase']
        self.edges=read(EXP/'index/edges.jsonl');self.views=read(EXP/'index/oriented_views.jsonl')
        self.vec=torch.load(EXP/'index/vectors.pt',map_location='cuda',weights_only=True)
        self.anchor=torch.tensor([v['anchor'] for v in self.views],device='cuda');self.neighbor=torch.tensor([v['neighbor'] for v in self.views],device='cuda')
        self.rel=torch.tensor([v['relation'] for v in self.views],device='cuda');self.eidx=torch.tensor([v['edge_index'] for v in self.views],device='cuda')
        self.conservative=torch.tensor([e['is_base'] or e['conservative'] for e in self.edges],device='cuda')[self.eidx]
        et=[e['entity_type'] for e in self.cat['entities']]
        self.types=sorted(set(et));ti={s:i for i,s in enumerate(self.types)}
        self.etypes=torch.tensor([ti[t] for t in et],device='cuda');self.allowed=torch.zeros((2*self.R,len(self.types)),device='cuda',dtype=torch.bool)
        for r in range(2*self.R):
            rule=self.cat['registry'][self.cat['relations'][r%self.R]]
            for t in rule['domain' if r>=self.R else 'range']:self.allowed[r,ti[t]]=True
        self.adj=defaultdict(list);self.graph=defaultdict(set)
        for j,e in enumerate(self.edges):
            h,r,t=e['triple'];self.adj[h].append(2*j);self.adj[t].append(2*j+1)
            if e['is_base'] or e['conservative']:self.graph[h].add(t);self.graph[t].add(h)
        profile=np.zeros((len(et),2*self.R),np.float32)
        for e in self.edges:
            if e['is_base'] or e['conservative']:
                h,r,t=e['triple'];profile[h,r]+=1;profile[t,r+self.R]+=1
        denom=np.linalg.norm(profile,axis=1,keepdims=True);profile/=np.maximum(1.,denom)
        self.profile=torch.as_tensor(profile,device='cuda')
        structure=np.zeros((self.n,len(et)),np.float32)
        for h in range(self.n):
            structure[h,h]=1.
            for u in self.graph[h]:
                structure[h,u]=max(structure[h,u],.5)
                for v in self.graph[u]:structure[h,v]=max(structure[h,v],.25)
        self.structure=torch.as_tensor(structure,device='cuda')
        metas=read(EXP/'data/train_group_context.json');self.ids={x['claim_id']:x['group_id'] for x in read(EXP/'data/base_split.jsonl') if x['fold']=='train'}
        self.blocks={};registry=read(EXP/'data/training_source_registry.json')
        # Build inverted source blockers once, before any query scoring.
        page_inv=defaultdict(set);pair_inv=defaultdict(set);gram_inv=defaultdict(set);group_inv=defaultdict(set)
        for j,e in enumerate(self.edges):
            pair_inv[tuple(e['pair'])].add(j)
            for p in e['pages']:page_inv[tuple(p)].add(j)
            if e.get('group_id'):group_inv[e['group_id']].add(j)
            for x in edge_sources(e,registry):
                for g in shingles(x.get('evidence_text','')):gram_inv[g].add(j)
        for g,meta in metas.items():
            bad=set(group_inv[g])
            for p in meta['pairs']:bad.update(pair_inv[tuple(p)])
            for p in meta['pages']:bad.update(page_inv[tuple(p)])
            for z in meta['quotegrams']:bad.update(gram_inv[z])
            self.blocks[g]=torch.tensor(sorted(v for j in bad for v in [2*j,2*j+1]),device='cuda')
        self.self_blocks=metas

    @torch.no_grad()
    def search(self,heads,relations,strategy='R3',k=32,training_ids=None,pool='all'):
        h=torch.as_tensor(heads,device='cuda');r=torch.as_tensor(relations,device='cuda')
        if strategy=='R0':
            result=np.full((len(h),k),-1,np.int32);vals=np.zeros((len(h),k),np.float32)
            for j,a in enumerate(heads):
                bad=set(self.blocks[self.ids[training_ids[j]]].cpu().tolist()) if training_ids else set()
                vv=[v for v in self.adj[int(a)] if v not in bad and (pool=='all' or bool(self.conservative[v]))]
                vv.sort(key=lambda v:(not self.edges[v//2]['is_base'],digest(['neighbor',self.edges[v//2]['edge_id'],self.views[v]['neighbor'],self.views[v]['relation']])))
                vv=vv[:min(k,16)];result[j,:len(vv)]=vv;vals[j,:len(vv)]=1.
            return result,vals
        q=self.vec['queries'][h,r];plain=q@self.vec['plain'].T
        anchor=self.vec['entities'][h]@self.vec['entities'][self.anchor].T
        if strategy=='R1':s=.6*plain+.4*anchor
        else:
            role=self.vec['relations'][r]@self.vec['relations'][self.rel].T
            s=.55*anchor+.25*plain+.2*role
            if strategy=='R3':
                s=s+.15*self.structure[h[:,None],self.anchor[None,:]]+.05*(self.profile[h]@self.profile[self.anchor].T)
            legal=(self.etypes[h,None]==self.etypes[self.anchor][None,:])&self.allowed[r[:,None],self.etypes[self.neighbor][None,:]]
            s=s.masked_fill(~legal,-1e4)
        if pool=='conservative':s=s.masked_fill(~self.conservative[None,:],-1e4)
        if training_ids:
            for j,cid in enumerate(training_ids):s[j,self.blocks[self.ids[cid]]]=-1e4
        # A negative semantic score is no supporting context, preserving empty fallback.
        values,idx=torch.topk(s,min(k,s.shape[1]),dim=-1,sorted=True)
        idx=idx.masked_fill(values<=0,-1)
        return idx.cpu().numpy().astype(np.int32),values.cpu().numpy().astype(np.float32)


def train_examples():
    R=len(read(EXP/'data/catalogue.json')['relations'])
    return [(x['triple'][0],x['triple'][1],x['triple'][2],x['id']) for x in read(EXP/'data/train_base.jsonl')]+[(x['triple'][2],x['triple'][1]+R,x['triple'][0],x['id']) for x in read(EXP/'data/train_base.jsonl')]


def main():
    if (EXP/'retrieval/freeze.json').exists():print('REUSE retrieval');return
    torch.set_num_threads(2);retriever=Retriever();examples=train_examples();n=retriever.n;R=retriever.R
    rows=[];relation_rows=[]
    allkeys=[(h,r) for h in range(n) for r in range(2*R)]
    for strategy in ['R0','R1','R2','R3']:
        for pool in ['all','conservative']:
            if strategy=='R0' and pool=='conservative':continue
            outputs=[];scores=[];start=time.perf_counter()
            for off in range(0,len(allkeys),128):
                kk=allkeys[off:off+128];ids,ss=retriever.search([x[0] for x in kk],[x[1] for x in kk],strategy,pool=pool);outputs.append(ids);scores.append(ss)
            folder=EXP/'retrieval';folder.mkdir(exist_ok=True,parents=True)
            np.savez_compressed(folder/f'{strategy}_{pool}_global.npz',ids=np.concatenate(outputs).reshape(n,2*R,32),scores=np.concatenate(scores).reshape(n,2*R,32))
            global_seconds=time.perf_counter()-start;outputs=[];scores=[];start=time.perf_counter()
            for off in range(0,len(examples),128):
                kk=examples[off:off+128];ids,ss=retriever.search([x[0] for x in kk],[x[1] for x in kk],strategy,training_ids=[x[3] for x in kk],pool=pool);outputs.append(ids);scores.append(ss)
            ids=np.concatenate(outputs);ss=np.concatenate(scores)
            np.savez_compressed(folder/f'{strategy}_{pool}_train.npz',ids=ids,scores=ss)
            sec=time.perf_counter()-start;used=set(int(v)//2 for v in ids[:,:16].ravel() if v>=0);candidate={j for j in used if not retriever.edges[j]['is_base']}
            chosen=[retriever.views[int(v)] for v in ids[:,:16].ravel() if v>=0]
            outside=sum(x['anchor']>=n or x['neighbor']>=n for x in chosen)
            nonempty=(ids[:,0]>=0);noadj=np.array([not retriever.adj[h] for h,r,y,cid in examples]);candidate_nonempty=np.array([any(v>=0 and not retriever.edges[int(v)//2]['is_base'] for v in row[:16]) for row in ids])
            rows.append(dict(strategy=strategy,pool=pool,retrievable_legal_candidates=sum(not e['is_base'] and (pool=='all' or e['conservative']) for e in retriever.edges),distinct_used_candidates=len(candidate),distinct_used_edges=len(used),training_queries=len(examples),nonempty_rate=float(nonempty.mean()),candidate_nonempty_rate=float(candidate_nonempty.mean()),outside_base_endpoint_fraction=outside/max(1,len(chosen)),no_direct_adjacency_queries=int(noadj.sum()),no_direct_adjacency_nonempty_rate=float(nonempty[noadj].mean()) if noadj.any() else None,train_query_mean_ms=1000*sec/len(examples),global_cache_seconds=global_seconds,located_contract_fraction=float(np.mean([retriever.edges[j]['features'][1] for j in candidate])) if candidate else None,entailed_contract_fraction=float(np.mean([retriever.edges[j]['features'][2] for j in candidate])) if candidate else None,base_fact_fraction_of_selected=len(used-candidate)/max(1,len(used))))
            for rel in range(2*R):
                rr=[i for i,x in enumerate(examples) if x[1]==rel]
                if rr:relation_rows.append(dict(strategy=strategy,pool=pool,relation=rel,name=retriever.cat['relations'][rel%R],inverse=rel>=R,n=len(rr),nonempty_rate=float(nonempty[rr].mean()),candidate_rate=float(candidate_nonempty[rr].mean())))
            print('RETRIEVAL',strategy,pool,len(candidate),'candidates',float(nonempty.mean()),'seconds',sec,flush=True)
    csvsave('RETRIEVAL_RESULTS.csv',rows);csvsave('retrieval/per_relation.csv',relation_rows)
    save(EXP/'retrieval/train_example_keys.json',examples)
    save(EXP/'retrieval/freeze.json',dict(index_sha256=file_sha(EXP/'index/freeze.json'),files={p.name:file_sha(p) for p in (EXP/'retrieval').glob('*') if p.name!='freeze.json'},answer_ids_not_used=True,measured_ms='batched amortized including device-to-host, excluding index encoding; not single-query SLA',retrieval_reference_is_not_gold=True))


if __name__=='__main__':main()
