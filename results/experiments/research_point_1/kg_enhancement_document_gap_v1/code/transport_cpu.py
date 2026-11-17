"""Frozen T0--T5 validation-only mechanism experiment, entirely on CPU."""
import time
from common_local import *
from torch.nn import functional as F


class CPUIndex:
    def __init__(self):
        self.cat=read(STUDY/'data/catalogue.json');self.R=len(self.cat['relations']);self.n=self.cat['nbase'];self.entities=self.cat['entities']
        self.edges=read(STUDY/'index/edges.jsonl');self.views=read(STUDY/'index/oriented_views.jsonl');self.registry=read(STUDY/'data/training_source_registry.json')
        self.vec=torch.load(STUDY/'index/vectors.pt',map_location='cpu',weights_only=True)
        self.a=np.array([x['anchor'] for x in self.views]);self.b=np.array([x['neighbor'] for x in self.views]);self.r=np.array([x['relation'] for x in self.views])
        self.edge_docs=[{p[0] for p in e['pages']} for e in self.edges];self.anchor_docs=defaultdict(set);self.graph=defaultdict(set);profile=np.zeros((len(self.entities),2*self.R),np.float32)
        for e in self.edges:
            h,r,t=e['triple']
            for a in [h,t]:self.anchor_docs[a].update(p[0] for p in e['pages'])
            if e['is_base'] or e['conservative']:
                self.graph[h].add(t);self.graph[t].add(h);profile[h,r]+=1;profile[t,r+self.R]+=1
        profile/=np.maximum(1.,np.linalg.norm(profile,axis=1,keepdims=True));self.profile=profile
        self.cached={r:np.load(STUDY/'retrieval'/f'{r}_all_global.npz') for r in ['R1','R3']}
        self.meta={}
        for v in self.views:
            e=self.edges[v['edge_index']];ss=sources(e,self.registry)
            condition=canonical([x.get('conditions_source') for x in ss if x.get('conditions_source')])
            self.meta[v['view_id']]=dict(condition=condition,label=self.entities[v['anchor']]['label_zh'])

    def full_scores(self,keys):
        h=torch.tensor([q[0] for q in keys]);r=torch.tensor([q[1] for q in keys]);v=self.vec
        with torch.no_grad():
            p=(v['queries'][h,r]@v['plain'].T).numpy();a=(v['entities'][h]@v['entities'][self.a].T).numpy();rel=(v['relations'][r]@v['relations'][self.r].T).numpy()
        scores=.55*a+.25*p+.2*rel
        for j,(head,relation) in enumerate(keys):
            distance=np.zeros(len(self.entities),np.float32);distance[head]=1.
            for x in self.graph[head]:
                distance[x]=max(distance[x],.5)
                for y in self.graph[x]:distance[y]=max(distance[y],.25)
            scores[j]+=.15*distance[self.a]+.05*(self.profile[head]@self.profile[self.a].T)
            et=self.entities[head]['entity_type'];rr=self.cat['registry'][self.cat['relations'][relation%self.R]];allowed=rr['domain' if relation>=self.R else 'range']
            good=np.array([self.entities[x]['entity_type']==et and self.entities[y]['entity_type'] in allowed for x,y in zip(self.a,self.b)])
            scores[j,~good]=-1e4
        return scores

    def select(self,keys,method,k,full):
        ids=np.full((len(keys),k),-1,np.int64);ss=np.zeros((len(keys),k),np.float32);blocked=[]
        for j,(h,r) in enumerate(keys):
            if method in ['T0','T5']:
                cache=self.cached['R3' if method=='T0' else 'R1'];ids[j]=cache['ids'][h,r,:k];ss[j]=cache['scores'][h,r,:k];continue
            score=full[j].copy();good=score>0;docs=self.anchor_docs[h]
            if method in ['T1','T2']:
                if not docs:continue
                shared=np.array([bool(docs&self.edge_docs[v['edge_index']]) for v in self.views])
                good &= shared if method=='T1' else ~shared
            if method=='T4':
                qlabel=self.entities[h]['label_zh']
                for vi in np.flatnonzero(good):
                    why=conflict(qlabel,self.meta[int(vi)]['label'],self.meta[int(vi)]['condition'])
                    if why:good[vi]=False;blocked.append(dict(h=int(h),r=int(r),view_id=int(vi),reason=why))
            vv=np.flatnonzero(good)
            if method in ['T3','T4']:
                order=np.lexsort((vv,-score[vv],-(self.r[vv]==r).astype(int)))
            else:order=np.lexsort((vv,-score[vv]))
            chosen=vv[order[:k]];ids[j,:len(chosen)]=chosen;ss[j,:len(chosen)]=score[chosen]
        return ids,ss,blocked


def score_transport(data,keys,ids,ss,index,alpha=.2):
    outputs=[]
    with torch.no_grad():
        for off in range(0,len(keys),128):
            kk=keys[off:off+128];ix=torch.as_tensor(ids[off:off+128]);mask=ix>=0;safe=ix.clamp_min(0);scores=torch.as_tensor(ss[off:off+128]);h=torch.tensor([q[0] for q in kk]);r=torch.tensor([q[1] for q in kk]);e=data['entities'];q=data['queries'][h,r]
            weights=torch.softmax(torch.cat([scores.masked_fill(~mask,-1e4)/.1,torch.zeros((len(kk),1))],-1),-1)[:,:-1]*mask
            a=torch.as_tensor(index.a)[safe];b=torch.as_tensor(index.b)[safe]
            transport=e[b]-e[a]+e[h,None,:];message=(weights[:,:,None]*transport).sum(1)
            outputs.append((F.normalize(q+alpha*message,dim=-1)@e[:index.n].T).numpy())
    return np.concatenate(outputs)


def link_ranks(matrix,keys,targets,truths):
    idx={q:j for j,q in enumerate(keys)};tail=defaultdict(set);head=defaultdict(set);rows=[]
    for h,r,t in truths:tail[h,r].add(t);head[r,t].add(h)
    for q in targets:
        h,r,t=q['triple']
        for task,anchor,rel,target,filt in [('tail',h,r,t,tail[h,r]),('head',t,r+15,h,head[r,t])]:
            scores=matrix[idx[anchor,rel]];keep=np.ones(len(scores),bool);keep[list(filt)]=False;keep[target]=True;equal=np.isclose(scores,scores[target],rtol=0,atol=1e-8)&keep;greater=(scores>scores[target]+1e-8)&keep;rank=float(1+greater.sum()+(equal.sum()-1)/2);visible=scores.copy();visible[~keep]=-np.inf
            rows.append(dict(id=q['id'],task=task,query_anchor=anchor,query_relation=rel,rank=rank,top1=int(np.argmax(visible)),target=target,endpoint_status=q['endpoint_status']))
    return rows


def main():
    if (OUT/'mechanism/complete.json').exists():print('REUSE CPU mechanism study');return
    targets=read(STUDY/'data/validation_targets.jsonl');truth=read(STUDY/'data/validation_truth.json');R=15
    keys=sorted({k for x in targets for k in [(x['triple'][0],x['triple'][1]),(x['triple'][2],x['triple'][1]+R)]});index=CPUIndex();start=time.perf_counter();full=index.full_scores(keys);selections={};coverage=[];blocksets=[]
    for method in ['T0','T1','T2','T3','T4','T5']:
        for k in [8,16,32]:
            ids,ss,blocked=index.select(keys,method,k,full);selections[method,k]=(ids,ss);blocksets+=blocked
            (OUT/'mechanism').mkdir(parents=True,exist_ok=True);np.savez_compressed(OUT/'mechanism'/f'{method}_k{k}_selection.npz',ids=ids,scores=ss)
            used={int(v)//2 for v in ids.ravel() if v>=0};slots=[(j,int(v)) for j,row in enumerate(ids) for v in row if v>=0];known=[bool(index.anchor_docs[h]) for h,r in keys]
            mismatch=0;samedoc=0;crossdoc=0;exact=0
            for j,v in slots:
                h,r=keys[j];rule=index.cat['registry'][index.cat['relations'][r%R]];allowed=rule['domain' if r>=R else 'range'];mismatch+=index.entities[index.a[v]]['entity_type']!=index.entities[h]['entity_type'] or index.entities[index.b[v]]['entity_type'] not in allowed;exact+=index.r[v]==r
                if known[j]:
                    if index.anchor_docs[h]&index.edge_docs[v//2]:samedoc+=1
                    else:crossdoc+=1
            coverage.append(dict(method=method,k=k,query_keys=len(keys),source_observable_keys=sum(known),nonempty_keys=int((ids[:,0]>=0).sum()),selected_slots=len(slots),distinct_relations_used=len(used),distinct_uncertain_candidates_used=sum(not index.edges[v]['is_base'] for v in used),same_visible_source_slots=samedoc,cross_visible_source_slots=crossdoc,query_role_type_mismatch_rate=mismatch/max(1,len(slots)),same_directed_relation_rate=exact/max(1,len(slots)),explicit_blocked_contexts=len({(x['h'],x['r'],x['view_id']) for x in blocked})))
    csvsave('mechanism/context_coverage.csv',coverage);save(OUT/'mechanism/query_keys.json',keys);save(OUT/'mechanism/explicit_conflict_blocks.jsonl',list({(b['h'],b['r'],b['view_id']):b for b in blocksets}.values()))
    results=[];allranks={};reference=[]
    for seed in SEEDS:
        data=torch.load(STUDY/'features'/f'G2_s{seed}.pt',map_location='cpu',weights_only=True)
        assert all(v.device.type=='cpu' for v in data.values())
        for method,k in selections:
            tick=time.perf_counter();ids,ss=selections[method,k];matrix=score_transport(data,keys,ids,ss,index);rows=link_ranks(matrix,keys,targets,truth)
            for x in rows:x['source_observable']=bool(index.anchor_docs[x['query_anchor']]);x['context_available']=bool(ids[keys.index((x['query_anchor'],x['query_relation'])),0]>=0)
            allranks[method,k,seed]=rows;save(OUT/'mechanism'/f'{method}_k{k}_s{seed}_ranks.jsonl',rows);np.savez_compressed(OUT/'mechanism'/f'{method}_k{k}_s{seed}_scores.npz',scores=matrix)
            for subset in ['all_validation','source_observable_directions','source_unknown_directions']:
                rr=[x for x in rows if subset=='all_validation' or (x['source_observable'] if subset=='source_observable_directions' else not x['source_observable'])]
                if not rr:continue
                ranks=np.array([x['rank'] for x in rr]);results.append(dict(method=method,k=k,seed=seed,subset=subset,query_directions=len(rr),MRR=float(np.mean(1/ranks)),Hits1=float(np.mean(ranks<=1)),Hits10=float(np.mean(ranks<=10)),nonempty_rate=float(np.mean([x['context_available'] for x in rr])),cpu_seconds=time.perf_counter()-tick))
            if method=='T0' and k==16:
                m=float(np.mean([1/x['rank'] for x in rows]));old=read(STUDY/'models'/f'transport_R3_s{seed}'/'complete.json')['validation_link_MRR'];reference.append(dict(seed=seed,original_validation_MRR=old,CPU_MRR=m,delta=m-old,within_1e_5=abs(m-old)<1e-5))
            print('CPU',method,k,seed,float(np.mean([1/x['rank'] for x in rows])),flush=True)
        del data
    csvsave('mechanism/ALL_SEED_RESULTS.csv',results);groups=defaultdict(list)
    for r in results:groups[r['method'],r['k'],r['subset']].append(r)
    aggregated=[]
    for (method,k,subset),rr in sorted(groups.items()):
        cov=next(x for x in coverage if x['method']==method and x['k']==k)
        aggregated.append(dict(method=method,k=k,subset=subset,query_directions=rr[0]['query_directions'],MRR=float(np.mean([x['MRR'] for x in rr])),MRR_seed_sd=float(np.std([x['MRR'] for x in rr])),Hits1=float(np.mean([x['Hits1'] for x in rr])),Hits10=float(np.mean([x['Hits10'] for x in rr])),nonempty_rate=rr[0]['nonempty_rate'],distinct_uncertain_candidates_used=cov['distinct_uncertain_candidates_used'],same_directed_relation_rate=cov['same_directed_relation_rate'],role_type_mismatch_rate=cov['query_role_type_mismatch_rate'],explicit_blocked_contexts=cov['explicit_blocked_contexts']))
    csvsave('TRANSPORT_COMPARISON.csv',aggregated)
    mapping={x['claim_id']:x['group_id'] for x in read(STUDY/'data/base_split.jsonl') if x['fold']=='valid'};comp=[]
    for subset in ['all_validation','source_observable_directions']:
        for method in ['T1','T2','T3','T4','T5']:
            by=defaultdict(list);sd=[]
            for seed in SEEDS:
                a=allranks[method,16,seed];b={(x['id'],x['task']):x for x in allranks['T0',16,seed]};values=[]
                for x in a:
                    if subset!='all_validation' and not x['source_observable']:continue
                    delta=1/x['rank']-1/b[x['id'],x['task']]['rank'];by[mapping[x['id']]].append(delta);values.append(delta)
                sd.append(float(np.mean(values)))
            if not by:continue
            v=np.array([np.mean(x) for x in by.values()]);rng=np.random.default_rng(SEEDS[0]);draw=[float(np.mean(rng.choice(v,len(v)))) for _ in range(2000)];comp.append(dict(method=method,control='T0',subset=subset,query_mean_delta=float(np.mean(sd)),group_macro_delta=float(v.mean()),CI95=[float(x) for x in np.quantile(draw,[.025,.975])],seed_deltas=sd,fact_groups=len(v),development_comparison_not_independent_test=True))
    save(OUT/'mechanism/paired_comparisons.json',comp);save(OUT/'mechanism/reference_replay.json',reference)
    assert all(r['within_1e_5'] for r in reference),'Investigate CPU replay mismatch; do not fabricate equivalent baseline'
    save(OUT/'mechanism/complete.json',dict(validation_facts=len(targets),query_keys=len(keys),seed_count=3,settings=54,seconds=time.perf_counter()-start,device='cpu',GPU_used=False,LLM_requests=0,alpha=.2,query_provenance='Training-visible index anchor source sets only; no target source lookup',test_targets_read=False))


if __name__=='__main__':main()
