"""Reuse original fitting; new simple filter, fresh structural initializations."""
import argparse
import fcntl
import time
from types import SimpleNamespace
import numpy as np
import torch
import gc
from collab_io import *
import train_simkgc as original
from views import build as original_build


def foundation(seed,view='G2'):
    return (OLD if DATASET=='cold' and view in ['G1','G2','G3'] else RUN)/'models'/f'simkgc_{view}_s{seed}'


def filtered_build(view,seed,**kwargs):
    data=original_build('G3',seed=seed)
    admissible={tuple(e['triple']) for e in read(RUN/'data/context_edges.jsonl') if not e['is_base'] and e['simple_filter']}
    keep=np.array([tuple(t) in admissible for t in data['aux']])
    for key in ['aux','weights','legal']:data[key]=data[key][keep]
    data['weights'][:]=1.;data['legal'][:]=True
    data['aux_rows']=[r for r,k in zip(data['aux_rows'],keep) if k]
    data['summary']=dict(data['summary'],view='filter',aux_edges=len(data['aux']),filter='legal AND evidence-location valid; no learned thresholds',schema_invalid_contexts=0)
    return data


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int);args=parser.parse_args()
    while not (RUN/'data/collab_freeze.json').exists():time.sleep(2)
    wanted=[foundation(seed,view)/'complete.json' for seed in ([args.seed] if args.seed else SEEDS) for view in (['filter'] if DATASET=='cold' else ['G1','G2','G3','filter'])]
    if all(p.exists() for p in wanted):
        print('REUSE all completed baseline models',DATASET,flush=True);return
    rows=[]
    for seed in [args.seed] if args.seed else SEEDS:
        for view in (['filter'] if DATASET=='cold' else ['G1','G2','G3','filter']):
            if (foundation(seed,view)/'complete.json').exists():continue
            with (STUDY/'gpu.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                original.build=filtered_build if view=='filter' else original_build
                params=SimpleNamespace(view=view,seed=seed,epochs=10,patience=3,batch=32,lr=2e-5,prototype='none')
                original.fit(params)
                rows.append(dict(view=view,seed=seed,initialization='original pretrained BGE; no old fine-tuned weights',checkpoint_sha256=file_sha(foundation(seed,view)/'best.pt')))
                gc.collect();torch.cuda.empty_cache()
    save(RUN/'configs/new_baseline_execution.json',rows)
    print('Baseline training complete',DATASET,flush=True)


if __name__=='__main__':main()
