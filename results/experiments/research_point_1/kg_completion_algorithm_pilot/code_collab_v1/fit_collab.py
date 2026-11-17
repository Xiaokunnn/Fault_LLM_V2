"""Small trainable heads over reused SimKGC; validation-only selection."""
import argparse
from collections import defaultdict
import time
import fcntl
import numpy as np
import torch
from torch.nn import functional as F
from collab_io import *
from model import Neighborhood,Collaboration
from eval_core import Evaluator

VARIANTS=['full','no_dynamic','fixed','no_relation','no_neighbor','lan','no_null','scale25','scale50','conservative','noise25','noise50']


def load(seed,variant,checkpoint=None):
    feature=RUN/'features'/f'seed{seed}.pt'
    data=torch.load(feature,map_location='cuda',weights_only=True)
    model=Collaboration(len(read(RUN/'data/catalogue.json')['relations']),variant=variant).cuda()
    if checkpoint:model.load_state_dict(torch.load(checkpoint,map_location='cuda',weights_only=True))
    return model,data,Neighborhood(variant,seed)


@torch.no_grad()
def query_scores(model,data,graph,keys):
    matrix=[]
    model.eval();n=read(RUN/'data/catalogue.json')['nbase']
    for off in range(0,len(keys),128):
        batch=keys[off:off+128];h=[x[0] for x in batch];r=torch.tensor([x[1] for x in batch],device='cuda')
        pack=graph.pack(h);q=data['queries'][torch.tensor(h,device='cuda'),r]
        enhanced=model(q,r,data['entities'],pack)
        matrix.append((enhanced@data['entities'][:n].T).cpu().numpy())
    return np.concatenate(matrix) if matrix else np.empty((0,n))


def validation(model,data,graph,ev):
    R=graph.R;keys=sorted({k for q in ev.targets for k in [(q['triple'][0],q['triple'][1]),(q['triple'][2],q['triple'][1]+R)]})
    scores=query_scores(model,data,graph,keys);index={k:i for i,k in enumerate(keys)}
    def predict(h,r,t,task):
        if task=='relation':return np.zeros(R)
        return scores[index[(h,r) if task=='tail' else (t,r+R)]]
    metrics,_=ev.score(predict)
    return metrics['link_MRR']


def fit(seed,variant):
    folder=RUN/'models'/f'collab_{variant}_s{seed}'
    if (folder/'complete.json').exists():return
    assert not folder.exists(),'Preserve any partial model; use a new run/version'
    seed_all(seed);model,data,graph=load(seed,variant);cat=read(RUN/'data/catalogue.json');R=graph.R;n=cat['nbase']
    train=read(RUN/'data/train_base.jsonl');ev=Evaluator.validation(cat)
    examples=[(x['triple'][0],x['triple'][1],x['triple'][2],x['id']) for x in train]+[(x['triple'][2],x['triple'][1]+R,x['triple'][0],x['id']) for x in train]
    known=defaultdict(set)
    for h,r,t,_ in examples:known[h,r].add(t)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=1e-4);rng=np.random.default_rng(seed+4)
    start=time.perf_counter();torch.cuda.reset_peak_memory_stats()
    save(folder/'config.json',dict(seed=seed,variant=variant,epochs=60,batch=128,lr=.001,patience=15,validation_every=5,
        parameters=sum(p.numel() for p in model.parameters()),frozen_encoder=read(RUN/'features'/f'seed{seed}.json'),
        input_freeze_sha256=file_sha(RUN/'data/collab_freeze.json'),controls_sha256=file_sha(RUN/'data/controls_freeze.json'),
        context_rows=len(graph.rows),legal_candidates=sum(not x['is_base'] for x in graph.rows),
        synthetic_contexts=sum(x.get('synthetic_corruption',False) for x in graph.rows),
        implementation='LAN-Text Eq6-11 mechanism adaptation with frozen SimKGC features and cosine decoder' if variant=='lan' else 'Relation-aware task-contribution gate and null-message residual; not factual-confidence learning',
        test_access=False,selection='Same automatic-alias filtered validation as pilot; include shared epoch0; no test feedback'))
    best=validation(model,data,graph,ev);best_epoch=0;torch.save(model.state_dict(),folder/'best.pt')
    history=[dict(epoch=0,validation_link_MRR=best,seconds=time.perf_counter()-start)]
    for epoch in range(1,61):
        model.train();losses=[]
        for off in range(0,len(examples),128):
            if off==0:permutation=rng.permutation(len(examples))
            batch=[examples[i] for i in permutation[off:off+128]];h=[x[0] for x in batch]
            r=torch.tensor([x[1] for x in batch],device='cuda');target=torch.tensor([x[2] for x in batch],device='cuda')
            pack=graph.pack(h,[x[3] for x in batch]);q=data['queries'][torch.tensor(h,device='cuda'),r]
            enhanced=model(q,r,data['entities'],pack);logits=20*(enhanced@data['entities'][:n].T)
            for j,(head,rel,t,_) in enumerate(batch):
                others=[x for x in known[head,rel] if x!=t]
                if others:logits[j,others]=-1e4
            loss=F.cross_entropy(logits,target);optimizer.zero_grad(set_to_none=True);loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step();losses.append(float(loss.detach()))
        if epoch%5==0:
            metric=validation(model,data,graph,ev)
            history.append(dict(epoch=epoch,loss=float(np.mean(losses)),validation_link_MRR=metric,seconds=time.perf_counter()-start))
            if metric>best:best=metric;best_epoch=epoch;torch.save(model.state_dict(),folder/'best.pt')
            print(DATASET,variant,seed,epoch,metric,flush=True)
            if epoch-best_epoch>=15:break
    save(folder/'history.jsonl',history)
    save(folder/'complete.json',dict(best_epoch=best_epoch,validation_link_MRR=best,seconds=time.perf_counter()-start,
        checkpoint_sha256=file_sha(folder/'best.pt'),peak_cuda_bytes=torch.cuda.max_memory_allocated(),no_test_read=True,executed_epochs=epoch))
    del model,data;torch.cuda.empty_cache()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--variant');args=parser.parse_args()
    while not (RUN/'data/controls_freeze.json').exists():time.sleep(2)
    for seed in SEEDS:
        while not (RUN/'features'/f'seed{seed}.json').exists():time.sleep(2)
        for variant in [args.variant] if args.variant else VARIANTS:
            with (STUDY/'gpu.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                fit(seed,variant)
                torch.cuda.empty_cache()
    save(RUN/'configs/adapter_grid_complete.json',dict(models=3*(1 if args.variant else len(VARIANTS)),variants=[args.variant] if args.variant else VARIANTS,all_validation_only=True))


if __name__=='__main__':main()
