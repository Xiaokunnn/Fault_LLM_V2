"""Clean relation-score ablation: same pool, node coefficient and bridge penalty."""
import gzip
import numpy as np
import torch
from raw_io import *
from run_completion import Evaluation,metrics

def main():
    out=EXP/'completion/no_relation_fixed_scale'
    if (out/'freeze.json').exists():return
    torch.set_num_threads(4);keys=read(EXP/'paths/query_keys.json');cat=read(EXP/'data/catalogue.json');ev=Evaluation(cat,keys);z=np.load(EXP/'paths/B3.npz');L=z['length'];dest=np.take_along_axis(z['nodes'],L[...,None],axis=2)[...,0];nv=(z['relations']==-1).sum(-1)
    s=.5*z['node_score']+.5*.65-.05*nv;support=np.zeros((len(keys),2150),np.float32)
    for i in range(len(keys)):
        for t in np.unique(dest[i,(L[i]>=2)&(dest[i]>=0)&(dest[i]<2150)]):
            jj=np.where((L[i]>=2)&(dest[i]==t))[0];jj=jj[np.argsort(-s[i,jj],kind='stable')[:8]];mass=float(np.exp(np.clip((s[i,jj]-.65)/.1,-10,10)).sum());support[i,t]=mass/(1+mass)
    npz(out/'support.npz',support=support);grid=read(EXP/'config.json')['fusion_grid'];hist=[];rr={};ll={}
    for seed in SEEDS:
        f=torch.load(OLD/'features'/f'G2_s{seed}.pt',map_location='cpu',weights_only=True);q=f['queries'][[x[0] for x in keys],[x[1] for x in keys]];base=(q@f['entities'][:2150].T).numpy()
        for a in grid:
            ranks,legal,ties,top=ev.evaluate(base+a*support);rr[seed,a]=ranks;ll[seed,a]=legal;hist.append(dict(method='no_relation_fixed_scale',seed=seed,alpha=a,**metrics(ranks),type_legal=float(legal.mean())))
    a=max(grid,key=lambda a:(np.mean([r['MRR'] for r in hist if r['alpha']==a]),-a));rows=[r for r in hist if r['alpha']==a];diffs={};rng=np.random.default_rng(16112026)
    orig=[json.loads(x) for x in gzip.decompress((EXP/'completion/query_ranks.jsonl.gz').read_bytes()).decode().splitlines()];lookup={(x['method'],x['seed'],x['id'],x['task']):x for x in orig}
    groups=sorted({x['group'] for x in ev.rows});gi=[np.array([i for i,x in enumerate(ev.rows) if x['group']==g]) for g in groups];mean=np.mean([1/rr[seed,a] for seed in SEEDS],0)
    for ref in ['SimKGC_G2','transport_R3_raw','P4_B3_full']:
        d=mean-np.mean([[1/lookup[ref,seed,x['id'],x['task']]['rank'] for x in ev.rows] for seed in SEEDS],0);bs=[]
        for _ in range(2000):
            ix=np.concatenate([gi[j] for j in rng.integers(len(gi),size=len(gi))]);bs.append(float(d[ix].mean()))
        diffs.update({ref+'_delta_MRR':float(d.mean()),ref+'_ci_low':float(np.quantile(bs,.025)),ref+'_ci_high':float(np.quantile(bs,.975))})
    result=dict(method='no_relation_fixed_scale',alpha=a,seeds=3,MRR_mean=float(np.mean([r['MRR'] for r in rows])),MRR_seed_sd=float(np.std([r['MRR'] for r in rows],ddof=1)),Hits1_mean=float(np.mean([r['Hits1'] for r in rows])),Hits3_mean=float(np.mean([r['Hits3'] for r in rows])),Hits10_mean=float(np.mean([r['Hits10'] for r in rows])),top1_type_legal_fraction=float(np.mean([r['type_legal'] for r in rows])),**diffs)
    target=EXP/'ABLATION_RESULTS.csv';existing=list(csv.DictReader(target.open()));assert not any(r['method']==result['method'] for r in existing)
    with target.open('a') as f:csv.DictWriter(f,fieldnames=list(existing[0]),lineterminator='\n').writerow(result)
    csvsave(out/'grid.csv',hist)
    save(out/'freeze.json',dict(result=result,formula='0.5 node_score + 0.5 constant(0.65) - 0.05 virtual_count; all other score/aggregation/search settings identical',shared_full_alpha=read(EXP/'completion/freeze.json')['selected']['P4_B3_full'],shared_alpha_seed_MRR=[metrics(rr[seed,.1])['MRR'] for seed in SEEDS]))
    print(canonical(result),flush=True)

if __name__=='__main__':main()
