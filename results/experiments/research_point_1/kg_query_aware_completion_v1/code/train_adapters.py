"""Same new split, G2 foundation and validation-only selection for all arms."""
import argparse
from collections import defaultdict
import gc
import time
import numpy as np
import torch
from torch.nn import functional as F
from io_utils import *
from query_model import Context, Residual, VARIANTS, scores
from eval_core import Evaluator
import fit_collab
from model import Neighborhood,Collaboration


def validation(model,ctx,ev,variant):
    R=len(ctx.data['queries'][0])//2
    keys=sorted({k for x in ev.targets for k in [(x['triple'][0],x['triple'][1]),(x['triple'][2],x['triple'][1]+R)]})
    matrix=scores(model,ctx,keys,variant);idx={k:i for i,k in enumerate(keys)}
    def predict(h,r,t,task):return np.zeros(R) if task=='relation' else matrix[idx[(h,r) if task=='tail' else (t,r+R)]]
    return ev.score(predict)[0]['link_MRR']


def fit(seed,variant):
    folder=EXP/'models'/f'query_{variant}_s{seed}'
    if (folder/'complete.json').exists():return
    assert not folder.exists(),'Preserve interrupted run'
    seed_all(seed);ctx=Context(seed);model=Residual().cuda();cat=read(EXP/'data/catalogue.json');R=len(cat['relations']);n=cat['nbase'];ev=Evaluator.validation(cat)
    train=read(EXP/'retrieval/train_example_keys.json');known=defaultdict(set)
    for h,r,t,cid in train:known[h,r].add(t)
    opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=1e-4);rng=np.random.default_rng(seed+4)
    start=time.perf_counter();torch.cuda.reset_peak_memory_stats();best=validation(model,ctx,ev,variant);be=0;history=[dict(epoch=0,validation_link_MRR=best)]
    save(folder/'config.json',dict(seed=seed,variant=variant,retrieval=VARIANTS[variant],epochs=60,batch=128,lr=.001,patience=15,validation_every=5,parameters=sum(p.numel() for p in model.parameters()),foundation_sha256=file_sha(EXP/'features'/f'G2_s{seed}.pt'),only_kgc_loss=True,no_dynamic_gate=True,selection='Validation link MRR only including epoch0',residual_bound=.5,hidden=64))
    torch.save(model.state_dict(),folder/'best.pt')
    for epoch in range(1,61):
        losses=[];permutation=rng.permutation(len(train))
        for off in range(0,len(train),128):
            batch=[train[i] for i in permutation[off:off+128]];h=[x[0] for x in batch];r=[x[1] for x in batch];t=torch.tensor([x[2] for x in batch],device='cuda')
            q,x,m,*_=ctx.values(h,r,variant,[x[3] for x in batch]);logits=20*(model(q,x,m)@ctx.data['entities'][:n].T)
            for j,(a,b,y,cid) in enumerate(batch):
                other=list(known[a,b]-{y})
                if other:logits[j,other]=-1e4
            loss=F.cross_entropy(logits,t);opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step();losses.append(float(loss.detach()))
        if epoch%5==0:
            v=validation(model,ctx,ev,variant);history.append(dict(epoch=epoch,loss=float(np.mean(losses)),validation_link_MRR=v,seconds=time.perf_counter()-start))
            if v>best:best=v;be=epoch;torch.save(model.state_dict(),folder/'best.pt')
            print('QUERY',seed,variant,epoch,v,flush=True)
            if epoch-be>=15:break
    save(folder/'history.jsonl',history);save(folder/'complete.json',dict(best_epoch=be,executed_epochs=epoch,validation_link_MRR=best,seconds=time.perf_counter()-start,peak_cuda_bytes=torch.cuda.max_memory_allocated(),checkpoint_sha256=file_sha(folder/'best.pt'),no_test_access=True))
    del ctx,model,opt;gc.collect();torch.cuda.empty_cache()


def old_load(seed,variant,checkpoint=None):
    data=torch.load(EXP/'features'/f'G2_s{seed}.pt',map_location='cuda',weights_only=True)
    model=Collaboration(len(read(EXP/'data/catalogue.json')['relations']),variant=variant).cuda()
    if checkpoint:model.load_state_dict(torch.load(checkpoint,map_location='cuda',weights_only=True))
    return model,data,Neighborhood(variant,seed)


def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int);args=p.parse_args()
    while not (EXP/'retrieval/freeze.json').exists():time.sleep(2)
    fit_collab.load=old_load
    save(EXP/'data/collab_freeze.json',dict(source=file_sha(EXP/'data/freeze.json'),adaptation='Same original model and fitting, new split/fresh features'))
    save(EXP/'data/controls_freeze.json',dict(new_methods=list(VARIANTS),no_test_access=True))
    for seed in [args.seed] if args.seed else SEEDS:
        while not (EXP/'features'/f'G2_s{seed}.json').exists():time.sleep(2)
        save(EXP/'features'/f'seed{seed}.json',read(EXP/'features'/f'G2_s{seed}.json'))
        for variant in ['lan','full']:fit_collab.fit(seed,variant)
        for variant in VARIANTS:fit(seed,variant)
    save(EXP/'configs/adapters_complete.json',dict(seeds=[args.seed] if args.seed else SEEDS,query_variants=list(VARIANTS),old_variants=['lan','full']))


if __name__=='__main__':main()
