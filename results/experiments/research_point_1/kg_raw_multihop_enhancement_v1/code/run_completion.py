"""Three-seed validation only: matched raw R3, bounded path fusion and controls."""
import gc
import gzip
import time
import numpy as np
import torch
from torch.nn import functional as F
from raw_io import *
from path_search import relation_feature

def metrics(ranks):
    x=np.asarray(ranks,dtype=np.float64)
    return dict(n=len(x),MRR=float(np.mean(1/x)),Hits1=float(np.mean(x<=1)),Hits3=float(np.mean(x<=3)),Hits10=float(np.mean(x<=10)),mean_rank=float(x.mean()))

class Evaluation:
    def __init__(self,cat,keys):
        self.cat=cat;self.keys=keys;self.ki={tuple(k):i for i,k in enumerate(keys)};R=len(cat['relations'])
        self.truth=defaultdict(set)
        for h,r,t in read(EXP/'data/validation_truth.json'):self.truth[h,r].add(t);self.truth[t,r+R].add(h)
        self.rows=[]; support={x['id']:x for x in read(EXP/'analysis/real_target_support.jsonl')}
        groups={x['claim_id']:x['group_id'] for x in read(OLD/'data/base_split.jsonl') if x['fold']=='valid'}
        for x in read(EXP/'data/validation_targets.jsonl'):
            h,r,t=x['triple'];s=support[x['id']]
            for task,a,rel,y in [('tail',h,r,t),('head',t,r+R,h)]:
                self.rows.append(dict(id=x['id'],task=task,h=a,r=rel,target=y,key_index=self.ki[a,rel],group=groups[x['id']],relation=cat['relations'][r],endpoint_status=s['masked_endpoint_status'],real_target_path=bool(s['simple_two_hop_paths'] or s['simple_three_hop_paths'])))
    def evaluate(self,scores):
        ranks=[];legal=[];ties=[];top=[]
        R=len(self.cat['relations'])
        for row in self.rows:
            s=scores[row['key_index']].astype(np.float64).copy();y=row['target'];target=s[y]
            blocked=self.truth[row['h'],row['r']]-{y}
            if blocked:s[list(blocked)]=-1e5
            eq=np.isclose(s,target,atol=1e-8,rtol=0);greater=s>target+1e-8
            ranks.append(float(1+greater.sum()+(eq.sum()-1)/2));ties.append(int(eq.sum()))
            pred=int(s.argmax());top.append(pred)
            rule=self.cat['registry'][self.cat['relations'][row['r']%R]]
            legal.append(self.cat['entities'][pred]['entity_type'] in rule['domain' if row['r']>=R else 'range'])
        return np.asarray(ranks),np.asarray(legal),np.asarray(ties),np.asarray(top)

def retrieve_raw(cat,keys,v,views,edges,kind):
    dev=device();R=len(cat['relations']);N=len(cat['entities'])
    e=torch.tensor(v['entities'],device=dev);plain=torch.tensor(v['plain'],device=dev);rel=torch.tensor(v['relations'],device=dev);prof=torch.tensor(v['profiles'],device=dev)
    a=torch.tensor([x['anchor'] for x in views],device=dev);b=torch.tensor([x['neighbor'] for x in views],device=dev);r=torch.tensor([x['relation'] for x in views],device=dev)
    qh=torch.tensor([x[0] for x in keys],device=dev);qr=torch.tensor([x[1] for x in keys],device=dev);q=torch.tensor(v['queries'][qh.cpu().numpy(),qr.cpu().numpy()],device=dev)
    adj=[set() for _ in range(N)]
    for x in edges:
        h,rr,t=x['triple'];adj[h].add(t);adj[t].add(h)
    struct=np.zeros((len(keys),len(e)),np.float32)
    for j,(h,rr) in enumerate(keys):
        struct[j,h]=1
        for u in adj[h]:
            struct[j,u]=max(struct[j,u],.5)
            for z in adj[u]:struct[j,z]=max(struct[j,z],.25)
    with torch.inference_mode():
        anchor=e[qh]@e[a].T; ps=q@plain.T
        if kind=='knn':
            scores=.6*ps+.4*anchor;scores[:,b>=cat['nbase']]=-1e4
        else:
            scores=.55*anchor+.25*ps+.20*(rel[qr]@rel[r].T)+.15*torch.tensor(struct,device=dev)[:,a]+.05*(prof[qh]@prof[a].T)
            if kind=='R3':
                typ=[x['entity_type'] for x in cat['entities']]
                mask=np.array([[typ[h]==typ[x['anchor']] and typ[x['neighbor']] in cat['registry'][cat['relations'][rr%R]]['domain' if rr>=R else 'range'] for x in views] for h,rr in keys])
                scores.masked_fill_(~torch.tensor(mask,device=dev),-1e4)
        vals,ids=scores.topk(16,dim=-1);ids[vals<=0]=-1
    return ids.cpu().numpy().astype(np.int32),vals.cpu().numpy().astype(np.float32)

def transport(features,keys,ids,ss,views):
    dev=device();e=features['entities'].to(dev);q=features['queries'][[x[0] for x in keys],[x[1] for x in keys]].to(dev)
    valid=torch.tensor(ids>=0,device=dev);idx=np.maximum(ids,0)
    a=torch.tensor(np.array([x['anchor'] for x in views])[idx],device=dev);b=torch.tensor(np.array([x['neighbor'] for x in views])[idx],device=dev)
    logits=torch.tensor(ss,device=dev).masked_fill(~valid,-1e4)/.1
    w=torch.softmax(torch.cat([logits,torch.zeros((len(keys),1),device=dev)],-1),-1)[:,:-1]*valid
    context=(w[:,:,None]*(e[b]-e[a]+e[torch.tensor([x[0] for x in keys],device=dev),None])).sum(1)
    return q,e,context

def path_support(z,mode,seed=16112026,return_usage=False):
    nodes=z['nodes'];rels=z['relations'];L=z['length'];ns=z['node_score'];rs=z['relation_score']; Q,M=L.shape
    valid=(L>=2);real=(rels>=0).sum(-1);virt=(rels==-1).sum(-1)
    if mode=='onehop':valid=L==1
    if mode=='real2':valid&=(real>=2)
    if mode=='bridgeonly':valid&=(virt>0)
    if mode=='len2':valid&=(L==2)
    if mode=='len3':valid&=(L==3)
    if mode=='node':s=ns.copy()
    elif mode=='relation':s=rs.copy()
    elif mode=='uniform':s=np.full_like(ns,.65)
    else:s=.5*ns+.5*rs-.05*virt
    if mode=='shuffle_relation':
        rv=np.load(EXP/'index/vectors.npz')['relations']; keys=read(EXP/'paths/query_keys.json');rng=np.random.default_rng(seed)
        shuffled=rs.copy()
        for i,j in zip(*np.where(valid)):
            rr=rels[i,j,:L[i,j]].copy(); realpos=np.where(rr>=0)[0]
            if len(realpos)>1:
                # Deterministic reversal avoids a no-op 2-token random permutation.
                rr[realpos]=rr[realpos[::-1]]
            shuffled[i,j]=relation_feature(rr,rv)@rv[keys[i][1]]
        s=.5*ns+.5*shuffled-.05*virt
    destinations=np.take_along_axis(nodes,np.maximum(L,0)[...,None],axis=2)[...,0].copy()
    if mode=='shuffle_endpoint':
        cat=read(EXP/'data/catalogue.json');bytype=defaultdict(list)
        for e in cat['entities'][:cat['nbase']]:bytype[e['entity_type']].append(e['index'])
        rng=np.random.default_rng(seed)
        for i,j in zip(*np.where(valid&(destinations<cat['nbase']))):
            t=int(destinations[i,j]);pool=bytype[cat['entities'][t]['entity_type']];destinations[i,j]=int(rng.choice(pool))
    support=np.zeros((Q,2150),np.float32);npath=np.zeros_like(support,dtype=np.int16);picked=np.zeros_like(valid)
    for i in range(Q):
        candidates=defaultdict(list)
        for j in np.where(valid[i])[0]:
            t=int(destinations[i,j])
            if 0<=t<2150:candidates[t].append(j)
        for t,jj in candidates.items():
            jj=sorted(jj,key=lambda j:(-float(s[i,j]),j))[:1 if mode=='best_single' else 8]
            picked[i,jj]=True
            odds=np.exp(np.clip((s[i,jj]-.65)/.1,-10,10));mass=float(odds.sum())
            support[i,t]=mass/(1+mass);npath[i,t]=len(jj)
    if return_usage:return support,npath,dict(picked=picked,destinations=destinations,scores=s)
    return support,npath

def summarize(rows,method,seed,alpha,ranks,legal,ties):
    return dict(method=method,seed=seed,alpha=alpha,**metrics(ranks),top1_type_legal_fraction=float(legal.mean()),tied_directions=int((ties>1).sum()))

def main():
    if (EXP/'completion/freeze.json').exists():print('REUSE validation completion');return
    torch.set_num_threads(4);start=time.perf_counter();cat=read(EXP/'data/catalogue.json'); keys=read(EXP/'paths/query_keys.json');cfg=read(EXP/'config.json')
    ev=Evaluation(cat,keys); v=np.load(EXP/'index/vectors.npz');views=read(EXP/'index/oriented_views.jsonl');edges=load_graph()
    retrieval={}
    for strategy in ['R3','R3_soft','knn']:
        ids,ss=retrieve_raw(cat,keys,v,views,edges,strategy);retrieval[strategy]=(ids,ss);npz(EXP/f'completion/{strategy}_retrieval.npz',ids=ids,scores=ss)
    methods={'SimKGC_G1':('text','G1'),'SimKGC_G2':('text','G2'),'transport_R3_historical':('historical','R3'),
        'transport_R3_raw':('transport','R3'),'transport_R3_raw_soft':('transport','R3_soft'),'semantic_knn_raw':('knn','knn'),
        'P1_nodes_real':('B0','node'),'P2_relations_real':('B0','relation'),'P3_joint_real':('B0','joint'),
        'P4_B1':('B1','joint'),'P4_B2':('B2','joint'),'P4_B3_full':('B3','joint'),'random_bridges':('random','joint'),
        'no_relation_sequence':('B3','node'),'uniform_path_scores':('B3','uniform'),'best_single_path':('B3','best_single'),
        'onehop_only':('B0','onehop'),'real_multiedge_only':('B3','real2'),'bridged_paths_only':('B3','bridgeonly'),
        'twohop_only':('B3','len2'),'threehop_only':('B3','len3'),'shuffle_relation_order':('B3','shuffle_relation'),
        'shuffle_endpoints':('B3','shuffle_endpoint')}
    save(EXP/'completion/methods.json',methods)
    pathz={k:dict(np.load(EXP/f'paths/{k}.npz')) for k in ['B0','B1','B2','B3','random']}
    history=[]; allranks={};scores_selected={};legals={};tieset={};topset={};supportcache={};cost={};matrixcache={}
    # All path methods see the exact same fixed query keys and answer catalogue.
    for method,(kind,mode) in methods.items():
        if kind in pathz:
            t=time.perf_counter();support,npath=path_support(pathz[kind],mode);supportcache[method]=support
            npz(EXP/f'completion/{method}_support.npz',support=support,npath=npath);cost[method]=time.perf_counter()-t
    for seed in SEEDS:
        feats={name:torch.load(OLD/'features'/f'{name}_s{seed}.pt',map_location='cpu',weights_only=True) for name in ['G1','G2']}
        e=feats['G2']['entities'];q=feats['G2']['queries'][[x[0] for x in keys],[x[1] for x in keys]];base=(q@e[:2150].T).numpy()
        for method,(kind,mode) in methods.items():
            t=time.perf_counter();matrices={}
            if kind=='text':
                f=feats[mode];qq=f['queries'][[x[0] for x in keys],[x[1] for x in keys]]
                matrices={0.:(qq@f['entities'][:2150].T).numpy()}
            elif kind in ['transport','historical']:
                if kind=='historical':
                    vv=read(OLD/'index/oriented_views.jsonl');z=np.load(OLD/'retrieval/R3_all_global.npz');hh=np.array([x[0] for x in keys]);rr=np.array([x[1] for x in keys]);ids,ss=z['ids'][hh,rr,:16],z['scores'][hh,rr,:16]
                else:vv=views;ids,ss=retrieval[mode]
                qq,ee,cc=transport(feats['G2'],keys,ids,ss,vv)
                for a in cfg['fusion_grid']:matrices[a]=(F.normalize(qq+a*cc,dim=-1)@ee[:2150].T).cpu().numpy()
            elif kind=='knn':
                ids,ss=retrieval['knn'];ix=np.maximum(ids,0);dst=np.array([x['neighbor'] for x in views])[ix];logit=ss/.05;logit-=logit.max(-1,keepdims=True);ww=np.exp(logit)*(ids>=0);ww/=np.maximum(ww.sum(-1,keepdims=True),1e-12)
                memory=np.zeros_like(base)
                for i in range(len(keys)):
                    for j in range(16):
                        if ids[i,j]>=0 and dst[i,j]<2150:memory[i,dst[i,j]]+=ww[i,j]
                b=np.exp(20*base-(20*base).max(-1,keepdims=True));b/=b.sum(-1,keepdims=True)
                for a in cfg['fusion_grid']:matrices[a]=(1-a)*b+a*memory
            else:
                s=supportcache[method]
                if mode=='shuffle_endpoint':s,_=path_support(pathz[kind],mode,seed)
                for a in cfg['fusion_grid']:matrices[a]=base+a*s
            for a,s in matrices.items():
                ranks,legal,ties,top=ev.evaluate(s);allranks[method,seed,a]=ranks;legals[method,seed,a]=legal;tieset[method,seed,a]=ties;topset[method,seed,a]=top
                history.append(summarize(ev.rows,method,seed,a,ranks,legal,ties))
            matrixcache[method,seed]=matrices
            cost[f'{method}:{seed}']=time.perf_counter()-t
        del feats;gc.collect()
        if device()=='cuda':torch.cuda.empty_cache()
        print('SEED complete',seed,flush=True)
    csvsave(EXP/'completion/all_validation_grid.csv',history)
    selected={}
    for method in methods:
        alphas=sorted({x['alpha'] for x in history if x['method']==method})
        selected[method]=max(alphas,key=lambda a:(np.mean([x['MRR'] for x in history if x['method']==method and x['alpha']==a]),-a))
    results=[]; strata=[]; rankrows=[]
    for method in methods:
        a=selected[method]
        for seed in SEEDS:
            k=method,seed,a;ranks=allranks[k];row=summarize(ev.rows,method,seed,a,ranks,legals[k],tieset[k]);results.append(row)
            for field in ['task','relation','endpoint_status','real_target_path']:
                for value in sorted(set(str(r[field]) for r in ev.rows)):
                    ix=[i for i,r in enumerate(ev.rows) if str(r[field])==value]
                    strata.append(dict(method=method,seed=seed,field=field,value=value,**metrics(ranks[ix])))
            for i,r in enumerate(ev.rows):rankrows.append(dict(method=method,seed=seed,**r,rank=float(ranks[i]),top1=int(topset[k][i]),type_legal=bool(legals[k][i]),ties=int(tieset[k][i])))
        means={name:float(np.mean([r[name] for r in results if r['method']==method])) for name in ['MRR','Hits1','Hits3','Hits10','top1_type_legal_fraction']}
        print('RESULT',method,a,means['MRR'],flush=True)
    csvsave(EXP/'completion/seed_results.csv',results);csvsave(EXP/'completion/strata.csv',strata)
    out=EXP/'completion/query_ranks.jsonl.gz';out.parent.mkdir(exist_ok=True,parents=True)
    assert not out.exists()
    with gzip.open(out,'wt',encoding='utf-8') as f:
        for row in rankrows:f.write(canonical(row)+'\n')
    baseline=['SimKGC_G1','SimKGC_G2','transport_R3_historical','transport_R3_raw','transport_R3_raw_soft','semantic_knn_raw','P1_nodes_real','P2_relations_real','P3_joint_real','P4_B1','P4_B2','P4_B3_full']
    summary=[];rng=np.random.default_rng(16112026);groups=sorted({r['group'] for r in ev.rows});gidx=[np.array([i for i,r in enumerate(ev.rows) if r['group']==g]) for g in groups]
    for method in methods:
        a=selected[method];rr=np.stack([allranks[method,s,a] for s in SEEDS]);mm=(1/rr).mean(0)
        diffs={}
        for ref in ['SimKGC_G2','transport_R3_raw','P4_B3_full']:
            br=np.stack([allranks[ref,s,selected[ref]] for s in SEEDS]);delta=mm-(1/br).mean(0);ci=[]
            for _ in range(2000):
                ix=np.concatenate([gidx[j] for j in rng.integers(len(groups),size=len(groups))]);ci.append(float(delta[ix].mean()))
            diffs.update({ref+'_delta_MRR':float(delta.mean()),ref+'_ci_low':float(np.quantile(ci,.025)),ref+'_ci_high':float(np.quantile(ci,.975))})
        seedmetrics=[metrics(x) for x in rr]
        summary.append(dict(method=method,alpha=a,seeds=len(SEEDS),MRR_mean=float(np.mean([x['MRR'] for x in seedmetrics])),MRR_seed_sd=float(np.std([x['MRR'] for x in seedmetrics],ddof=1)),Hits1_mean=float(np.mean([x['Hits1'] for x in seedmetrics])),Hits3_mean=float(np.mean([x['Hits3'] for x in seedmetrics])),Hits10_mean=float(np.mean([x['Hits10'] for x in seedmetrics])),top1_type_legal_fraction=float(np.mean([x['top1_type_legal_fraction'] for x in results if x['method']==method])),**diffs))
    csvsave(EXP/'BASELINE_RESULTS.csv',[r for r in summary if r['method'] in baseline]);csvsave(EXP/'ABLATION_RESULTS.csv',[r for r in summary if r['method'] not in baseline or r['method']=='P4_B3_full'])
    # Same full-method alpha for ablations removes separate alpha-selection advantage.
    fa=selected['P4_B3_full'];fixed=[]
    for method,(kind,mode) in methods.items():
        if kind not in pathz:continue
        for seed in SEEDS:
            k=method,seed,fa;fixed.append(summarize(ev.rows,method,seed,fa,allranks[k],legals[k],tieset[k]))
    csvsave(EXP/'completion/ablations_shared_alpha.csv',fixed)
    seed=SEEDS[0];save(EXP/'completion/prediction_examples.jsonl',[dict(query=key,method=m,seed=seed,alpha=selected[m],top5=[dict(entity=int(t),score=float(matrixcache[m,seed][selected[m]][i,t])) for t in np.argsort(-matrixcache[m,seed][selected[m]][i])[:5]]) for m in ['SimKGC_G2','transport_R3_raw','P4_B3_full'] for i,key in enumerate(keys)])
    save(EXP/'completion/freeze.json',dict(selected=selected,summary=summary,unique_queries=len(keys),directions=len(ev.rows),groups=len(groups),wall_seconds=time.perf_counter()-start,cost_seconds=cost,selection='one alpha per method, mean validation MRR across all 3 seeds, smallest alpha tie-break; not independent test',bootstrap='2000 paired source/fact-group resamples, mean-over-seeds RR, no selection correction',test_evaluated=False,trained_new_parameters=0,training_decision='Decide only after matched-pool baseline and negative controls; no new supervised labels generated'))

if __name__=='__main__':main()
