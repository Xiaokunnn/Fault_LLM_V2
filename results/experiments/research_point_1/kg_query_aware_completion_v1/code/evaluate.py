"""Release once all validation selections freeze; identical 224-fact task."""
import gc
import time
import numpy as np
import torch
from io_utils import *
from query_model import Context,Residual,VARIANTS,scores
from fixed_baselines import Fixed,METHODS
from model import Neighborhood,Collaboration
from fit_collab import query_scores
from eval_core import Evaluator


def selections():
    return [(method,seed) for seed in SEEDS for method in ['simkgc_G1','simkgc_G2','simkgc_filter','collab_lan','collab_full']+['query_'+v for v in VARIANTS]+METHODS]


def get_scores(method,seed,keys):
    if method.startswith('simkgc'):
        view=method.removeprefix('simkgc_');d=torch.load(EXP/'features'/f'{view}_s{seed}.pt',map_location='cuda',weights_only=True)
        n=read(EXP/'data/catalogue.json')['nbase'];z=[]
        with torch.no_grad():
            for off in range(0,len(keys),128):
                kk=keys[off:off+128];q=d['queries'][torch.tensor([x[0] for x in kk],device='cuda'),torch.tensor([x[1] for x in kk],device='cuda')]
                z.append((q@d['entities'][:n].T).cpu().numpy())
        return np.concatenate(z)
    if method.startswith('collab'):
        variant=method.removeprefix('collab_');ctx=Context(seed);m=Collaboration(len(read(EXP/'data/catalogue.json')['relations']),variant=variant).cuda()
        m.load_state_dict(torch.load(EXP/'models'/f'{method}_s{seed}'/'best.pt',map_location='cuda',weights_only=True));m.eval()
        return query_scores(m,ctx.data,Neighborhood(variant,seed),keys)
    if method.startswith('query_'):
        variant=method.removeprefix('query_');ctx=Context(seed);m=Residual().cuda()
        m.load_state_dict(torch.load(EXP/'models'/f'{method}_s{seed}'/'best.pt',map_location='cuda',weights_only=True));m.eval()
        return scores(m,ctx,keys,variant)
    cfg=read(EXP/'models'/f'{method}_s{seed}'/'complete.json');return Fixed(seed,method,cfg['alpha']).score(keys)


def main():
    torch.set_num_threads(2);deadline=time.monotonic()+7200
    while not all((EXP/'configs'/name).exists() for name in ['foundations_complete.json','adapters_complete.json','fixed_complete.json']):
        if time.monotonic()>deadline:raise TimeoutError('Incomplete new-grid fitting; do not synthesize outputs')
        time.sleep(3)
    folders=[EXP/'models'/f'{m}_s{s}' for m,s in selections()]
    assert all((f/'complete.json').exists() for f in folders)
    save(EXP/'verification/test_release.json',dict(selection_files={str(f.relative_to(EXP)):file_sha(f/'complete.json') for f in folders},
        trained_checkpoints={str(f.relative_to(EXP)):file_sha(f/'best.pt') for f in folders if (f/'best.pt').exists()},
        code={p.name:file_sha(p) for p in sorted((EXP/'code').glob('*.py'))},protocol=file_sha(EXP/'DATA_PROTOCOL.md'),all_models_selected_before_test=True))
    targets=read(EXP/'audit_only/test_targets.jsonl');cat=read(EXP/'data/catalogue.json');R=len(cat['relations']);ev=Evaluator(targets,read(EXP/'audit_only/test_truth.json'),cat,list(range(cat['nbase'])))
    keys=sorted({k for x in targets for k in [(x['triple'][2],x['triple'][1]+R)]+[(x['triple'][0],r) for r in range(R)]});index={k:i for i,k in enumerate(keys)}
    for method,seed in selections():
        out=EXP/'evaluation'/f'{method}_s{seed}'
        if (out/'complete.json').exists():continue
        start=time.perf_counter();torch.cuda.reset_peak_memory_stats();matrix=get_scores(method,seed,keys)
        def predict(h,r,t,task):
            if task=='relation':return np.array([matrix[index[h,j],t] for j in range(R)])
            return matrix[index[(h,r) if task=='tail' else (t,r+R)]]
        matrices={task:np.stack([predict(*x['triple'],task) for x in targets]) for task in ['head','tail','relation']}
        metrics,rows=ev.score(predict);save(out/'metrics.json',dict(metrics,method=method,seed=seed,proxy_only=True));save(out/'rankings.jsonl',rows)
        np.savez_compressed(out/'scores.npz',**matrices)
        save(out/'complete.json',dict(seconds=time.perf_counter()-start,peak_cuda_bytes=torch.cuda.max_memory_allocated(),scores_sha256=file_sha(out/'scores.npz'),test_used_for_selection=False))
        print('TEST',method,seed,metrics['link_MRR'],flush=True);gc.collect();torch.cuda.empty_cache()
    save(EXP/'evaluation/complete.json',dict(evaluations=len(folders),trained_models=sum((f/'best.pt').exists() for f in folders),validation_selected_fixed_controls=sum(not (f/'best.pt').exists() for f in folders),all_seeds_reported=True))


if __name__=='__main__':main()
