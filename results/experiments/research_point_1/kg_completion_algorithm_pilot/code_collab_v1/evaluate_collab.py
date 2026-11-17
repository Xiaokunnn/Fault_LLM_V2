"""All methods frozen before new scoring; exact-ID complete-answer evaluation."""
import time
import fcntl
import gc
import numpy as np
import torch
from collab_io import *
from baselines import foundation
from fit_collab import VARIANTS,load,query_scores
from eval_core import Evaluator
from train_simkgc import setup,callback


def evaluate(name,folder,targets,cat):
    out=RUN/'evaluation'/name
    if (out/'metrics.json').exists():return
    start=time.perf_counter();R=len(cat['relations'])
    if name.startswith('simkgc') and DATASET=='cold' and '_filter_' not in name:
        source=OLD/'evaluation'/name/'test';assert source.exists()
        save(out/'reuse.json',dict(path=str(source.relative_to(PILOT)),same_targets=True,metrics_sha256=file_sha(source/'metrics.json'),scores_sha256=file_sha(source/'scores.npz')))
        prior=read(source/'metrics.json');ranks=read(source/'rankings.jsonl')
        assert {r['id'] for r in targets}=={r['id'] for r in ranks}
        save(out/'metrics.json',dict(prior,model=name,reused_from_previous_frozen_cold_experiment=True))
        save(out/'rankings.jsonl',ranks);return
    if name.startswith('collab'):
        cfg=read(folder/'config.json');model,data,graph=load(cfg['seed'],cfg['variant'],folder/'best.pt')
        keys=sorted({k for q in targets for k in [(q['triple'][2],q['triple'][1]+R)]+[(q['triple'][0],r) for r in range(R)]})
        scores=query_scores(model,data,graph,keys);idx={k:i for i,k in enumerate(keys)}
        def predict(h,r,t,task):
            if task=='relation':return np.array([scores[idx[h,j],t] for j in range(R)])
            return scores[idx[(h,r) if task=='tail' else (t,r+R)]]
        details=[]
        with torch.no_grad():
            for off in range(0,len(keys),128):
                kk=keys[off:off+128];h=[k[0] for k in kk];r=torch.tensor([k[1] for k in kk],device='cuda');p=graph.pack(h)
                _,ds=model(data['queries'][torch.tensor(h,device='cuda'),r],r,data['entities'],p,True)
                for j,k in enumerate(kk):details.append(dict(head=k[0],directed_relation=k[1],null=float(ds['null'][j]),residual_norm=float(ds['residual_norm'][j]),
                    contexts=[dict(edge_id=e['edge_id'],neighbor=t,edge_relation=rel,is_base=e['is_base'],pages=e['pages'],
                            task_gate=float(ds['gates'][j,l]),message_weight=float(ds['weights'][j,l])) for l,(t,rel,e) in enumerate(graph.entries(k[0]))]))
        save(out/'context_contributions.jsonl',details)
    else:
        view=name.split('_')[1];model,tok,descriptions,_=setup(view,cat);model=model.cuda().eval()
        model.load_state_dict(torch.load(folder/'best.pt',map_location='cuda',weights_only=True))
        predict=callback(model,tok,descriptions,cat,targets,'cuda')
    matrices={task:np.stack([predict(*r['triple'],task) for r in targets]) for task in ['head','tail','relation']}
    ix={tuple(r['triple']):i for i,r in enumerate(targets)}
    def frozen(h,r,t,task):return matrices[task][ix[h,r,t]]
    ev=Evaluator(targets,read(RUN/'audit_only/test_truth.json'),cat,list(range(cat['nbase'])))
    metrics,ranks=ev.score(frozen)
    alias=Evaluator(targets,read(RUN/'audit_only/test_truth.json'),cat,read(RUN/'data/filter_entity_aliases.json'))
    sensitivity,_=alias.score(frozen);metrics['automatic_alias_sensitivity_link_MRR']=sensitivity['link_MRR']
    detail_index={(x['head'],x['directed_relation']):x for x in details} if name.startswith('collab') else {}
    for task in ['head','tail']:
        metrics[task]['no_context_queries']=sum(not detail_index[(q['triple'][0],q['triple'][1]) if task=='tail' else (q['triple'][2],q['triple'][1]+R)]['contexts'] for q in targets) if name.startswith('collab') else None
    metrics.update(model=name,seed=read(folder/'config.json')['seed'],seconds=time.perf_counter()-start,checkpoint_sha256=file_sha(folder/'best.pt'),proxy_only=True,
        dataset=DATASET,rank_rule='Same exact base2150/15 answers, exact known-positive filtering, average rank within absolute1e-8 ties; validation alias proxy unchanged')
    save(out/'metrics.json',metrics);save(out/'rankings.jsonl',ranks)
    out.mkdir(parents=True,exist_ok=True);np.savez_compressed(out/'scores.npz',**matrices)
    print('EVALUATED',DATASET,name,metrics['link_MRR'],flush=True)
    del model;torch.cuda.empty_cache()


def main():
    torch.set_num_threads(2);names=[]
    for s in SEEDS:
        names +=[(f'simkgc_{v}_s{s}',foundation(s,v)) for v in ['G1','G2','G3','filter']]
        names +=[(f'collab_{v}_s{s}',RUN/'models'/f'collab_{v}_s{s}') for v in VARIANTS]
    deadline=time.monotonic()+7200
    while any(not (p/'complete.json').exists() for _,p in names):
        if time.monotonic()>deadline:raise TimeoutError('Preserve unfinished models; no evaluation released')
        time.sleep(3)
    save(RUN/'configs/test_release.json',dict(models={n:dict(folder=str(p.relative_to(PILOT)),complete_sha256=file_sha(p/'complete.json'),checkpoint_sha256=file_sha(p/'best.pt')) for n,p in names},
         design_sha256=file_sha(STUDY/'DESIGN_FROZEN.md'),all_conditions_predeclared=True,selection='validation only; no post-test changes'))
    targets=read(RUN/'audit_only/test_targets.jsonl');cat=read(RUN/'data/catalogue.json')
    for name,folder in names:
        with (STUDY/'gpu.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            evaluate(name,folder,targets,cat)
            gc.collect();torch.cuda.empty_cache()
    save(RUN/'evaluation/complete.json',dict(models=len(names),targets=len(targets),all_scores_saved_or_exact_reuse=True))


if __name__=='__main__':main()
