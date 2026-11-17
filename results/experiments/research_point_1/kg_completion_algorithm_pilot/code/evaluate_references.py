"""Predeclared diagnostic priors, not substitutes for the three trained algorithms."""
import time
import numpy as np
import torch
from common import RUN,read,save
from eval_core import Evaluator


def main():
    assert (RUN/'configs/test_release.json').exists()
    cat=read(RUN/'data/catalogue.json');targets=read(RUN/'audit_only/test_targets.jsonl')
    truth=read(RUN/'audit_only/test_truth.json');ev=Evaluator(targets,truth,cat,list(range(cat['nbase'])))
    train=read(RUN/'data/train_base.jsonl');R=len(cat['relations']);n=cat['nbase'];entities=cat['entities']
    head=np.zeros((R,n));tail=np.zeros((R,n));rel=np.zeros(R)
    for q in train:
        h,r,t=q['triple'];head[r,h]+=1;tail[r,t]+=1;rel[r]+=1
    for name in ['schema_only','schema_frequency','simkgc_zeroshot']:
        out=RUN/'evaluation/references'/name
        if (out/'metrics.json').exists():continue
        start=time.perf_counter()
        if name=='simkgc_zeroshot':
            from train_simkgc import setup,callback
            device='cuda' if torch.cuda.is_available() else 'cpu';torch.set_num_threads(2)
            model,tok,descriptions,_=setup('G1',cat);model=model.to(device).eval();predict=callback(model,tok,descriptions,cat,targets,device)
        else:
            def predict(h,r,t,task):
                if task=='relation':
                    allowed=np.array([entities[h]['entity_type'] in cat['registry'][v]['domain'] and entities[t]['entity_type'] in cat['registry'][v]['range'] for v in cat['relations']])
                    freq=rel
                else:
                    rule=cat['registry'][cat['relations'][r]]
                    allowed=np.array([e['entity_type'] in rule['domain' if task=='head' else 'range'] for e in entities[:n]])
                    freq=head[r] if task=='head' else tail[r]
                return allowed.astype(float)*(1+freq/(1+freq.max()) if name=='schema_frequency' else 1.)
        metrics,rows=ev.score(predict);metrics.update(reference=name,seconds=time.perf_counter()-start,proxy_only=True)
        save(out/'metrics.json',metrics);save(out/'rankings.jsonl',rows)
        print(name,metrics['link_MRR'],flush=True)


if __name__=='__main__':main()
