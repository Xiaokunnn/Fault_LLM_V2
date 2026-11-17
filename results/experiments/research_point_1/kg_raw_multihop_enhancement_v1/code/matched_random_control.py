"""Additional exact-effective-edge/degree/type matched bridge randomization."""
import gzip
import time
import numpy as np
import torch
from raw_io import *
from path_search import Paths,relation_feature
from run_completion import Evaluation,path_support,metrics

def main():
    folder=EXP/'completion/random_degree_matched'
    if (folder/'freeze.json').exists():return
    torch.set_num_threads(4);start=time.perf_counter();p=Paths();keys=read(EXP/'paths/query_keys.json');ev=Evaluation(p.cat,keys);rng=np.random.default_rng(16112026)
    orig={}
    for x in read(EXP/'bridges/B3.jsonl'):
        pair=tuple(sorted([x['a'],x['b']]))
        if pair not in orig or x['score']>orig[pair]['score']:orig[pair]=x
    pairs=list(sorted(orig));current=set(pairs);types=[e['entity_type'] for e in p.cat['entities']];ci=p.components
    groups=defaultdict(list)
    for i,(a,b) in enumerate(pairs):groups[types[a],types[b]].append(i)
    pools=[np.array(v) for v in groups.values() if len(v)>1];weights=np.array([len(v) for v in pools],float);weights/=weights.sum();swaps=0
    for attempt in range(len(pairs)*12):
        pool=pools[int(rng.choice(len(pools),p=weights))];ii,jj=rng.choice(pool,2,replace=False);a,b=pairs[ii];c,d=pairs[jj]
        if len({a,b,c,d})<4 or ci[a]==ci[d] or ci[c]==ci[b]:continue
        u,v=tuple(sorted([a,d])),tuple(sorted([c,b]))
        if u in current or v in current or u==v:continue
        # Keep the ordered type bucket valid for subsequent swaps.
        if (types[u[0]],types[u[1]])!=(types[a],types[b]) or (types[v[0]],types[v[1]])!=(types[c],types[d]):continue
        current.remove(tuple(sorted([a,b])));current.remove(tuple(sorted([c,d])));current.add(u);current.add(v);pairs[ii]=u;pairs[jj]=v;swaps+=1
    olddegree=Counter(v for pair in orig for v in pair);newdegree=Counter(v for pair in pairs for v in pair);assert olddegree==newdegree and len(current)==len(orig)
    vec=np.load(EXP/'index/vectors.npz');ee=vec['entities'];prof=vec['profiles'];pat=vec['patterns'];rows=[]
    for (a,b),oldpair in zip(pairs,sorted(orig)):
        rows.append(dict(a=a,b=b,component_a=int(ci[a]),component_b=int(ci[b]),semantic_cos=float(ee[a]@ee[b]),type_match=types[a]==types[b],role_cos=float(prof[a]@prof[b]),pattern_cos=float(pat[a]@pat[b]),score=orig[oldpair]['score'],kind='random_degree_matched',provenance='degree/type-pair/unique-edge-count preserving double-edge swaps, virtual negative control'))
    save(EXP/'bridges/random_degree_matched.jsonl',rows);badj=p.bridge_adj('random_degree_matched');M=p.cfg['max_paths_per_query'];H=3
    nodes=np.full((len(keys),M,4),-1,np.int32);rels=np.full((len(keys),M,H),-2,np.int16);eids=np.full((len(keys),M,H),-1,np.int32);length=np.zeros((len(keys),M),np.int8);ns=np.zeros_like(length,dtype=np.float32);rs=np.zeros_like(ns)
    for i,(h,r) in enumerate(keys):
        found,meta=p.search(h,r,badj)
        for j,(nn,rr,ee_,s) in enumerate(found[:M]):
            L=len(rr);nodes[i,j,:L+1]=nn;rels[i,j,:L]=rr;eids[i,j,:L]=ee_;length[i,j]=L
            ns[i,j]=.5*float(p.ev[h]@p.ev[nn[1]])+.5*float(np.mean(p.ev[nn[1:]]@p.qv[h,r]));rs[i,j]=relation_feature(rr,p.rv)@p.rv[r]
    z=dict(nodes=nodes,relations=rels,edge_ids=eids,length=length,node_score=ns,relation_score=rs);npz(EXP/'paths/random_degree_matched.npz',**z)
    support,npath=path_support(z,'joint');npz(folder/'support.npz',support=support,npath=npath)
    full=read(EXP/'completion/freeze.json');grid=read(EXP/'config.json')['fusion_grid'];history=[];ranks={};legal={};rankrows=[]
    for seed in SEEDS:
        f=torch.load(OLD/'features'/f'G2_s{seed}.pt',map_location='cpu',weights_only=True);q=f['queries'][[x[0] for x in keys],[x[1] for x in keys]];base=(q@f['entities'][:2150].T).numpy()
        for a in grid:
            rr,ll,tt,pp=ev.evaluate(base+a*support);ranks[seed,a]=rr;legal[seed,a]=ll
            history.append(dict(method='random_degree_matched',seed=seed,alpha=a,**metrics(rr),top1_type_legal_fraction=float(ll.mean())))
    a=max(grid,key=lambda a:(np.mean([r['MRR'] for r in history if r['alpha']==a]),-a));chosen=[r for r in history if r['alpha']==a]
    for seed in SEEDS:
        for i,row in enumerate(ev.rows):rankrows.append(dict(method='random_degree_matched',seed=seed,**row,rank=float(ranks[seed,a][i]),type_legal=bool(legal[seed,a][i])))
    csvsave(folder/'grid.csv',history);csvsave(folder/'seed_results.csv',chosen)
    out=folder/'query_ranks.jsonl.gz';out.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(out,'wt',encoding='utf-8') as f:
        for x in rankrows:f.write(canonical(x)+'\n')
    original=[json.loads(x) for x in gzip.decompress((EXP/'completion/query_ranks.jsonl.gz').read_bytes()).decode().splitlines()];ref_lookup={(x['method'],x['seed'],x['id'],x['task']):x['rank'] for x in original}
    mm=np.mean([1/ranks[s,a] for s in SEEDS],0);groups=sorted({x['group'] for x in ev.rows});gidx=[np.array([i for i,x in enumerate(ev.rows) if x['group']==g]) for g in groups];diffs={}
    for ref in ['SimKGC_G2','transport_R3_raw','P4_B3_full']:
        delta=mm-np.mean([[1/ref_lookup[ref,s,x['id'],x['task']] for x in ev.rows] for s in SEEDS],0);boots=[]
        for _ in range(2000):
            ix=np.concatenate([gidx[j] for j in rng.integers(len(groups),size=len(groups))]);boots.append(float(delta[ix].mean()))
        diffs.update({ref+'_delta_MRR':float(delta.mean()),ref+'_ci_low':float(np.quantile(boots,.025)),ref+'_ci_high':float(np.quantile(boots,.975))})
    result=dict(method='random_degree_matched',alpha=a,seeds=3,MRR_mean=float(np.mean([r['MRR'] for r in chosen])),MRR_seed_sd=float(np.std([r['MRR'] for r in chosen],ddof=1)),Hits1_mean=float(np.mean([r['Hits1'] for r in chosen])),Hits3_mean=float(np.mean([r['Hits3'] for r in chosen])),Hits10_mean=float(np.mean([r['Hits10'] for r in chosen])),top1_type_legal_fraction=float(np.mean([r['top1_type_legal_fraction'] for r in chosen])),**diffs)
    # Append this additionally necessary control; preserve every original row/result.
    target=EXP/'ABLATION_RESULTS.csv';existing=list(csv.DictReader(target.open()));assert not any(x['method']=='random_degree_matched' for x in existing)
    with target.open('a') as f:
        w=csv.DictWriter(f,fieldnames=list(existing[0]),lineterminator='\n');w.writerow(result)
    coverage=[];dest=np.take_along_axis(nodes,length[...,None],axis=2)[...,0];real=(rels>=0).sum(-1)
    for row in ev.rows:
        i=row['key_index'];valid=length[i]>=2;hit=valid&(dest[i]==row['target']);coverage.append(dict(id=row['id'],task=row['task'],target_reached=bool(hit.any()),target_reached_real2=bool((hit&(real[i]>=2)).any())))
    csvsave(folder/'coverage.csv',coverage)
    save(folder/'freeze.json',dict(result=result,unique_bridges=len(rows),degree_exactly_matched=True,type_pair_counts_exactly_matched=True,successful_swaps=swaps,remaining_original_pairs=len(set(orig)&current),paths=int((length>0).sum()),target_reached=sum(x['target_reached'] for x in coverage),target_reached_real2=sum(x['target_reached_real2'] for x in coverage),wall_seconds=time.perf_counter()-start))
    print(canonical(read(folder/'freeze.json')),flush=True)

if __name__=='__main__':main()
