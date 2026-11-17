"""Validation-selected fixed retrieval fusion and kNN-KGE mechanism adaptation."""
import gc
import time
import numpy as np
import torch
from torch.nn import functional as F
from io_utils import *
from query_model import Context
from eval_core import Evaluator

METHODS=['fixed_R1','fixed_R2','fixed_R3','transport_R3','knn_train','knn_candidates']


class Fixed:
    def __init__(self,seed,method,alpha):
        self.ctx=Context(seed);self.method=method;self.alpha=alpha;self.n=read(EXP/'data/catalogue.json')['nbase']
        if method.startswith('knn'):
            edges=read(EXP/'index/edges.jsonl');R=len(read(EXP/'data/catalogue.json')['relations']);a=[];r=[];b=[]
            for e in edges:
                h,rel,t=e['triple']
                if not e['is_base'] and (method=='knn_train' or not e['conservative']):continue
                if max(h,t)>=self.n:continue
                a += [h,t];r += [rel,rel+R];b += [t,h]
            self.memory=self.ctx.data['queries'][torch.tensor(a,device='cuda'),torch.tensor(r,device='cuda')]
            self.targets=torch.tensor(b,device='cuda')
    @torch.no_grad()
    def score(self,keys):
        outputs=[]
        for off in range(0,len(keys),128):
            kk=keys[off:off+128];h=[k[0] for k in kk];r=[k[1] for k in kk]
            if self.method.startswith('knn'):
                q=self.ctx.data['queries'][torch.tensor(h,device='cuda'),torch.tensor(r,device='cuda')]
                base=torch.softmax(20*(q@self.ctx.data['entities'][:self.n].T),-1)
                v,ix=(q@self.memory.T).topk(min(16,len(self.memory)),dim=-1)
                p=torch.softmax(v/.05,-1);memory=torch.zeros_like(base)
                memory.scatter_add_(1,self.targets[ix],p)
                scores=(1-self.alpha)*base+self.alpha*memory
            else:
                strategy=self.method.split('_')[-1]
                q,x,m,tail,transport,_=self.ctx.values(h,r,'full',retrieval=(strategy,16,'all'))
                context=transport if self.method.startswith('transport') else tail
                enhanced=F.normalize(q+self.alpha*context*m[:,None],dim=-1)
                scores=enhanced@self.ctx.data['entities'][:self.n].T
            outputs.append(scores.cpu().numpy())
        return np.concatenate(outputs)


def evaluate_valid(model,ev):
    R=len(model.ctx.data['queries'][0])//2
    keys=sorted({k for x in ev.targets for k in [(x['triple'][0],x['triple'][1]),(x['triple'][2],x['triple'][1]+R)]})
    matrix=model.score(keys);idx={k:i for i,k in enumerate(keys)}
    def p(h,r,t,task):return np.zeros(R) if task=='relation' else matrix[idx[(h,r) if task=='tail' else (t,r+R)]]
    return ev.score(p)[0]['link_MRR']


def main():
    torch.set_num_threads(2);cat=read(EXP/'data/catalogue.json');ev=Evaluator.validation(cat)
    for seed in SEEDS:
        while not (EXP/'features'/f'G2_s{seed}.json').exists():time.sleep(2)
        for method in METHODS:
            folder=EXP/'models'/f'{method}_s{seed}'
            if (folder/'complete.json').exists():continue
            start=time.perf_counter();model=Fixed(seed,method,0.);history=[]
            for alpha in [0.,.05,.1,.2]:
                model.alpha=alpha;metric=evaluate_valid(model,ev);history.append(dict(alpha=alpha,validation_link_MRR=metric))
            chosen=max(history,key=lambda x:x['validation_link_MRR'])
            save(folder/'history.jsonl',history);save(folder/'complete.json',dict(**chosen,method=method,seed=seed,seconds=time.perf_counter()-start,trained_parameters=0,
                implementation='kNN-KGE datastore and probability interpolation mechanism adapted to frozen SimKGC queries; not author-code reproduction' if method.startswith('knn') else 'fixed fusion, no learned attention/gate/residual',
                answer_catalogue=cat['nbase'],no_test_access=True,feature_sha256=file_sha(EXP/'features'/f'G2_s{seed}.pt')))
            print('FIXED',seed,method,chosen,flush=True);del model;gc.collect();torch.cuda.empty_cache()
    save(EXP/'configs/fixed_complete.json',dict(methods=METHODS,seeds=SEEDS,validation_only=True))


if __name__=='__main__':main()
