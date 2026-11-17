"""One new paired contribution objective; architecture and frozen data unchanged."""
import argparse
import time
from collections import defaultdict
import numpy as np
import torch
from torch.nn import functional as F
from role_io import *
from contrast import load_parent,make_packs,forward_probe,task_margin
from fit_collab import validation
from eval_core import Evaluator

ALL_ARMS=['gate_kgc','joint_kgc','margin_only','absolute_only','full','joint_full','shuffled','relative_only']
ARMS=os.environ.get('RP1_ROLE_ARMS',','.join(ALL_ARMS)).split(',')
assert set(ARMS)<=set(ALL_ARMS)


def contrast_losses(model,data,graph,pairs,arm,seed):
    pp,pm,pz,slots=make_packs(graph,pairs)
    if arm=='shuffled':
        for i,pair in enumerate(pairs):
            if int(digest(['shuffle',seed,pair['pair_id']])[:8],16)%2:
                for key in pp:
                    tmp=pp[key][i].clone();pp[key][i]=pm[key][i];pm[key][i]=tmp
    h=torch.tensor([p['h'] for p in pairs],device='cuda');r=torch.tensor([p['r'] for p in pairs],device='cuda');q=data['queries'][h,r]
    ep,lp=forward_probe(model,q,r,data['entities'],pp,slots,selected_gradient=True)
    em,lm=forward_probe(model,q,r,data['entities'],pm,slots,selected_gradient=True)
    # Same background/null baseline cancels from U+ - U-, so only two forwards needed.
    difference=20*(task_margin(ep,data['entities'],pairs)-task_margin(em,data['entities'],pairs))
    margin=F.softplus(.1-difference).mean()
    absolute=(F.binary_cross_entropy_with_logits(lp,torch.full_like(lp,.8))+F.binary_cross_entropy_with_logits(lm,torch.full_like(lm,.2)))/2
    relative=F.softplus(1-(lp-lm)).mean()
    return margin,absolute,relative


def fit(seed,arm):
    folder=OUT/'models'/f'role_{arm}_s{seed}'
    if (folder/'complete.json').exists():return
    assert not folder.exists(),'Preserve any interrupted model, do not overwrite'
    seed_all(seed);model,data,graph=load_parent(seed);model.train()
    for name,p in model.named_parameters():p.requires_grad_(arm in ['joint_kgc','joint_full'] or name.startswith('trust.'))
    parameters=[p for p in model.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(parameters,lr=.001,weight_decay=1e-4)
    raw=read(OUT/f'data/utility_{seed}.jsonl');pairs=[x for x in raw if x['strong_contrast'] and x['split']=='fit']
    probe_queries={(x['h'],x['r']) for x in read(OUT/'data/role_pairs_unfiltered.jsonl') if x['split']=='probe'}
    base=read(RUN/'data/train_base.jsonl');R=graph.R;n=read(RUN/'data/catalogue.json')['nbase'];examples=[];known=defaultdict(set)
    for x in base:
        h,r,t=x['triple']
        for a,rel,y in [(h,r,t),(t,r+R,h)]:
            known[a,rel].add(y)
            if (a,rel) not in probe_queries:examples.append((a,rel,y,x['id']))
    if not pairs and arm not in ['gate_kgc','joint_kgc']:raise ValueError('No justified contribution pair; cannot fabricate support supervision')
    ev=Evaluator.validation(read(RUN/'data/catalogue.json'));rng=np.random.default_rng(seed+16);prng=np.random.default_rng(seed+17)
    start=time.perf_counter();torch.cuda.reset_peak_memory_stats();best=validation(model,data,graph,ev);best_epoch=0;history=[dict(epoch=0,validation_link_MRR=best)]
    save(folder/'config.json',dict(seed=seed,arm=arm,epochs=40,lr=.001,patience=10,validation_every=5,batch=128,pair_batch=64,
        pretrained_checkpoint_sha256=file_sha(checkpoint(seed)),parent_feature_sha256=file_sha(RUN/'features'/f'seed{seed}.pt'),
        trainable_parameters=sum(p.numel() for p in parameters),architecture_parameters=sum(p.numel() for p in model.parameters()),
        pairs=len(pairs),contrast_probe_excluded_from_new_fit=True,kgc_examples=len(examples),gate_selected_slot_gradient_only=True,
        contrast_weight_margin=.1,contrast_weight_absolute=.1,smoothing=[.8,.2],new_architecture_modules=False,
        model_selection='Original validation link MRR only, including epoch0. Probe and historical test never select checkpoints.',
        utility_sha256=file_sha(OUT/f'data/utility_{seed}.jsonl')))
    torch.save(model.state_dict(),folder/'best.pt')
    for epoch in range(1,41):
        model.train();permutation=rng.permutation(len(examples));losses=[];ms=[];absvals=[]
        for off in range(0,len(examples),128):
            batch=[examples[i] for i in permutation[off:off+128]];h=[x[0] for x in batch];r=torch.tensor([x[1] for x in batch],device='cuda');target=torch.tensor([x[2] for x in batch],device='cuda')
            pack=graph.pack(h,[x[3] for x in batch]);q=data['queries'][torch.tensor(h,device='cuda'),r]
            scores=20*(model(q,r,data['entities'],pack)@data['entities'][:n].T)
            for j,(a,rel,y,_) in enumerate(batch):
                other=[t for t in known[a,rel] if t!=y]
                if other:scores[j,other]=-1e4
            kgc=F.cross_entropy(scores,target)
            pair_batch=[pairs[int(i)] for i in prng.integers(0,len(pairs),size=min(64,len(pairs)))] if pairs else []
            if pair_batch:margin,absolute,relative=contrast_losses(model,data,graph,pair_batch,arm,seed)
            else:margin=absolute=relative=0*kgc
            loss=kgc
            if arm in ['margin_only','full','joint_full','shuffled','relative_only']:loss=loss+.1*margin
            if arm in ['absolute_only','full','joint_full','shuffled']:loss=loss+.1*absolute
            if arm=='relative_only':loss=loss+.1*relative
            optimizer.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(parameters,1.);optimizer.step()
            losses.append(float(kgc.detach()));ms.append(float(margin.detach()));absvals.append(float(absolute.detach()))
        if epoch%5==0:
            m=validation(model,data,graph,ev);history.append(dict(epoch=epoch,kgc=float(np.mean(losses)),margin=float(np.mean(ms)),absolute=float(np.mean(absvals)),validation_link_MRR=m,seconds=time.perf_counter()-start))
            if m>best:best=m;best_epoch=epoch;torch.save(model.state_dict(),folder/'best.pt')
            print(DATASET,arm,seed,epoch,m,flush=True)
            if epoch-best_epoch>=10:break
    torch.save(model.state_dict(),folder/'last_diagnostic.pt')
    save(folder/'history.jsonl',history);save(folder/'complete.json',dict(seed=seed,arm=arm,best_epoch=best_epoch,executed_epochs=epoch,validation_link_MRR=best,
        seconds=time.perf_counter()-start,peak_cuda_bytes=torch.cuda.max_memory_allocated(),checkpoint_sha256=file_sha(folder/'best.pt'),
        last_checkpoint_sha256=file_sha(folder/'last_diagnostic.pt'),no_test_or_probe_selection=True))
    del model,data,optimizer;torch.cuda.empty_cache()


def main():
    while not (OUT/'data/utility_freeze.json').exists():time.sleep(2)
    for seed in SEEDS:
        for arm in ARMS:fit(seed,arm)
    save(OUT/'models/complete.json',dict(models=len(SEEDS)*len(ARMS),all_seed_arms_retained=True))


if __name__=='__main__':main()
