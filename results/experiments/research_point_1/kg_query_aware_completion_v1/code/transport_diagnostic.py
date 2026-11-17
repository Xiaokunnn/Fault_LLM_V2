"""Post-hoc component control, same fixed transport across R0/R1/R2.

Motivated by the prespecified fixed R3 comparator outperforming the neural
adapter. Not a new independent test or a replacement for the primary grid.
"""
import gc
import numpy as np
import torch
from io_utils import *
from fixed_baselines import Fixed,evaluate_valid
from eval_core import Evaluator


def main():
    torch.set_num_threads(2);cat=read(EXP/'data/catalogue.json');ev=Evaluator.validation(cat);models=[]
    for seed in SEEDS:
        for strategy in ['R0','R1','R2']:
            method='transport_'+strategy;folder=EXP/'models'/f'{method}_s{seed}';model=Fixed(seed,method,0.);history=[]
            for alpha in [0.,.05,.1,.2]:
                model.alpha=alpha;history.append(dict(alpha=alpha,validation_link_MRR=evaluate_valid(model,ev)))
            best=max(history,key=lambda x:x['validation_link_MRR']);save(folder/'history.jsonl',history)
            save(folder/'complete.json',dict(**best,seed=seed,method=method,trained_parameters=0,posthoc_diagnostic=True,initial_primary_grid_unchanged=True));models.append((method,seed))
            del model;gc.collect();torch.cuda.empty_cache()
    save(EXP/'verification/transport_diagnostic_release.json',dict(configs={f'{m}_s{s}':file_sha(EXP/'models'/f'{m}_s{s}'/'complete.json') for m,s in models},
        code=file_sha(Path(__file__)),test_exposure_disclosed=True,reason='Same transport, different retrieval: isolate the simple comparator mechanism without changing main model',validation_grid_unchanged=True))
    targets=read(EXP/'audit_only/test_targets.jsonl');R=len(cat['relations']);ev=Evaluator(targets,read(EXP/'audit_only/test_truth.json'),cat,list(range(cat['nbase'])))
    keys=sorted({k for x in targets for k in [(x['triple'][2],x['triple'][1]+R)]+[(x['triple'][0],r) for r in range(R)]});idx={k:i for i,k in enumerate(keys)};table=[]
    for method,seed in models:
        out=EXP/'evaluation'/f'{method}_s{seed}';cfg=read(EXP/'models'/f'{method}_s{seed}'/'complete.json');matrix=Fixed(seed,method,cfg['alpha']).score(keys)
        def predict(h,r,t,task):return np.array([matrix[idx[h,j],t] for j in range(R)]) if task=='relation' else matrix[idx[(h,r) if task=='tail' else (t,r+R)]]
        m,rows=ev.score(predict);save(out/'metrics.json',dict(m,method=method,seed=seed,proxy_only=True,posthoc_diagnostic=True));save(out/'rankings.jsonl',rows)
        np.savez_compressed(out/'scores.npz',**{task:np.stack([predict(*x['triple'],task) for x in targets]) for task in ['head','tail','relation']})
        save(out/'complete.json',dict(no_training=True,validation_selected_alpha=True,posthoc_internal_diagnostic=True))
        table.append(dict(method=method,seed=seed,alpha=cfg['alpha'],MRR=m['link_MRR'],Hits1=(m['head']['all']['Hits1']+m['tail']['all']['Hits1'])/2,Hits10=(m['head']['all']['Hits10']+m['tail']['all']['Hits10'])/2,posthoc=True))
        print(method,seed,m['link_MRR'],flush=True);gc.collect();torch.cuda.empty_cache()
    csvsave('analysis/transport_retrieval_diagnostic.csv',table)


if __name__=='__main__':main()
