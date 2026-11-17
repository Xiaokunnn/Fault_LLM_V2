"""Frozen-weight graph interventions, declared before any new test is scored."""
import fcntl
import numpy as np
import torch
from collab_io import *
from fit_collab import load
from eval_core import Evaluator


PROTOCOL=dict(interventions=['drop_candidates','drop_all','shuffle_edge_relations'],training=False,
    parameters='Same full model/encoder/checkpoint; only packed test graph context changes',
    interpretation='Input intervention on automatic-label recovery; not causal effect in physical pumps')


def main():
    assert (RUN/'evaluation/complete.json').exists()
    torch.set_num_threads(2);cat=read(RUN/'data/catalogue.json');R=len(cat['relations']);n=cat['nbase'];targets=read(RUN/'audit_only/test_targets.jsonl')
    ev=Evaluator(targets,read(RUN/'audit_only/test_truth.json'),cat,list(range(n)))
    keys=sorted({k for q in targets for k in [(q['triple'][2],q['triple'][1]+R)]+[(q['triple'][0],r) for r in range(R)]});ix={k:i for i,k in enumerate(keys)}
    for seed in SEEDS:
        with (STUDY/'gpu.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            folder=RUN/'models'/f'collab_full_s{seed}';model,data,graph=load(seed,'full',folder/'best.pt');model.eval()
            for variant in PROTOCOL['interventions']:
                out=RUN/'interventions'/f'{variant}_s{seed}'
                if (out/'metrics.json').exists():continue
                scores=[]
                with torch.no_grad():
                    for off in range(0,len(keys),128):
                        kk=keys[off:off+128];h=[k[0] for k in kk];r=torch.tensor([k[1] for k in kk],device='cuda');pack=graph.pack(h)
                        if variant=='drop_candidates':pack['mask']&=pack['base']
                        elif variant=='drop_all':pack['mask'][:]=False
                        else:
                            pack['rel']=(pack['rel']+7)%R+(pack['rel']//R)*R
                        q=data['queries'][torch.tensor(h,device='cuda'),r];v=model(q,r,data['entities'],pack)
                        if variant=='drop_all':torch.testing.assert_close(v,q)
                        scores.append((v@data['entities'][:n].T).cpu().numpy())
                scores=np.concatenate(scores)
                def predict(h,r,t,task):
                    if task=='relation':return np.array([scores[ix[h,j],t] for j in range(R)])
                    return scores[ix[(h,r) if task=='tail' else (t,r+R)]]
                metrics,rows=ev.score(predict)
                save(out/'metrics.json',dict(metrics,seed=seed,intervention=variant,checkpoint_sha256=file_sha(folder/'best.pt'),protocol=PROTOCOL))
                save(out/'rankings.jsonl',rows)
                np.savez_compressed(out/'scores.npz',**{task:np.stack([predict(*q['triple'],task) for q in targets]) for task in ['head','tail','relation']})
            del model,data;torch.cuda.empty_cache()
    save(RUN/'interventions/complete.json',dict(models=9,training=False,protocol=PROTOCOL))
    print('Frozen interventions complete',DATASET,flush=True)


if __name__=='__main__':main()
