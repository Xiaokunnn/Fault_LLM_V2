"""ComplEx original multilinear score, adapted logistic/negative-sampling runner.

Not an author-code reproduction. No test or source-provenance file is read here.
"""
import argparse
import time
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from common import RUN,SEEDS,seed_all,save,read,file_sha
from views import build
from eval_core import Evaluator


class Complex(nn.Module):
    def __init__(self,n,R,dim=64,text_features=None,seed=0):
        super().__init__();self.dim=dim
        self.entity=nn.Embedding(n,2*dim);self.relation=nn.Embedding(R,2*dim)
        with torch.no_grad():
            self.entity.weight.normal_(0,.1,generator=torch.Generator().manual_seed(seed+1))
            self.relation.weight.normal_(0,.1,generator=torch.Generator().manual_seed(seed+2))
        if text_features is not None:
            self.register_buffer('text',text_features)
            self.text_projection=nn.Linear(text_features.shape[1],2*dim,bias=False)
            nn.init.normal_(self.text_projection.weight,std=.01)

    def vectors(self,index):
        v=self.entity(index)
        if hasattr(self,'text'):v=v+self.text_projection(self.text[index])
        return v

    def forward(self,h,r,t):
        hr,hi=self.vectors(h).chunk(2,-1);rr,ri=self.relation(r).chunk(2,-1);tr,ti=self.vectors(t).chunk(2,-1)
        return (hr*rr*tr+hi*rr*ti+hr*ri*ti-hi*ri*tr).sum(-1)

    @torch.no_grad()
    def prediction_cache(self,n):
        e=self.vectors(torch.arange(n,device=self.entity.weight.device));r=self.relation.weight
        return e,r


def callback(model,cat):
    e,r=model.prediction_cache(cat['nbase']);er,ei=e.chunk(2,-1);rr,ri=r.chunk(2,-1)
    def predict(h,rel,t,task):
        if task=='tail':scores=(er[h]*rr[rel]-ei[h]*ri[rel])@er.T+(er[h]*ri[rel]+ei[h]*rr[rel])@ei.T
        elif task=='head':scores=(rr[rel]*er[t]+ri[rel]*ei[t])@er.T+(rr[rel]*ei[t]-ri[rel]*er[t])@ei.T
        else:scores=(er[h]*er[t]+ei[h]*ei[t])@rr.T+(er[h]*ei[t]-ei[h]*er[t])@ri.T
        return scores.detach().cpu().numpy()
    return predict


def fit(args):
    folder=RUN/'models'/f'complex_{args.view}_s{args.seed}_f{args.fraction}_n{args.noise}_{args.prototype}_{args.run_tag}'
    if (folder/'complete.json').exists():print('REUSE',folder,flush=True);return
    assert not (folder/'history.jsonl').exists(),'Preserve interrupted run; select a new run suffix'
    seed_all(args.seed);device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    data=build(args.view,args.fraction,args.noise,args.seed);cat=data['catalogue']
    tf=None
    if args.view in ['G4','G3_labels']:tf=torch.load(RUN/'data'/('text_features.pt' if args.view=='G4' else 'text_labels.pt'),map_location=device,weights_only=True)['features']
    model=Complex(len(cat['entities']),len(cat['relations']),args.dim,tf,args.seed).to(device)
    optimizer=torch.optim.Adam(model.parameters(),lr=args.lr)
    base=data['base'];aux=data['aux'];weights=data['weights'];legal=data['legal']
    validation=Evaluator.validation(cat)
    rng=np.random.default_rng(args.seed+5);aux_rng=np.random.default_rng(args.seed+6)
    nbase=cat['nbase'];history=[];best=-1.;best_epoch=0;start=time.perf_counter()
    if device.type=='cuda':torch.cuda.reset_peak_memory_stats()
    bknown={tuple(x) for x in base};aknown=bknown|{tuple(x) for x in aux}
    def loss_on(batch,wr=None,flags=None,kind='base',fixed_negative=None):
        x=torch.as_tensor(batch,dtype=torch.long,device=device);size=len(batch)
        pos=model(x[:,0],x[:,1],x[:,2])
        generator=rng if kind=='base' else aux_rng
        neg=fixed_negative if fixed_negative is not None else generator.integers(0,nbase,size=(size,args.negatives))
        # Filter only training-known triples, never held-out positives.
        known=bknown if kind=='base' else aknown
        bad=np.array([[(int(h),int(r),int(t)) in known for t in ts] for (h,r,_),ts in zip(batch,neg)])
        ni=torch.as_tensor(neg,dtype=torch.long,device=device)
        h=x[:,0,None].expand_as(ni);rel=x[:,1,None].expand_as(ni)
        negs=model(h,rel,ni)
        mask=torch.as_tensor(~bad,device=device)
        negative=(F.softplus(negs)*mask).sum(1)/mask.sum(1).clamp_min(1)
        if flags is None:flags=np.ones(size,dtype=bool)
        positive=torch.where(torch.as_tensor(flags,device=device),F.softplus(-pos),F.softplus(pos))
        loss=positive+negative
        if wr is not None:loss=loss*torch.as_tensor(wr,device=device)
        return loss.mean()+args.reg*(model.vectors(x[:,0]).pow(2).mean()+model.vectors(x[:,2]).pow(2).mean()+model.relation(x[:,1]).pow(2).mean())
    save(folder/'config.json',dict(vars(args),implementation='ComplEx scoring function adaptation; Adam logistic sampled-tail loss, train-known negative masking, L2; not author implementation',device=str(device),view=data['summary'],parameters=sum(p.numel() for p in model.parameters()),input_freeze=file_sha(RUN/'data/freeze.json')))
    for epoch in range(1,args.epochs+1):
        model.train();losses=[];permutation=rng.permutation(len(base))
        if args.view in ['G3_flat','G3_flat_filtered']:
            merged=np.concatenate([base,aux]);permutation=rng.permutation(len(merged))
            # Same optimizer-step budget as other arms; sample fixed base-size epoch.
            if len(permutation)>len(base):permutation=permutation[:len(base)]
        for off in range(0,len(permutation),args.batch):
            ix=permutation[off:off+args.batch]
            batch=merged[ix] if args.view in ['G3_flat','G3_flat_filtered'] else base[ix]
            optimizer.zero_grad(set_to_none=True)
            loss=loss_on(batch,kind='aux' if args.view=='G3_flat_filtered' else 'base')
            if len(aux) and args.view not in ['G3_flat','G3_flat_filtered']:
                ai=aux_rng.integers(0,len(aux),size=len(ix));aw=weights[ai].copy()
                # Schema-invalid rows train a structural-consistency negative, not a factual negative.
                aw[~legal[ai]]=1.
                loss=loss+args.aux_scale*loss_on(aux[ai],aw,legal[ai],kind='aux')
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step();losses.append(float(loss.detach()))
        if epoch==1 or epoch%args.eval_every==0:
            model.eval();metrics,_=validation.score(callback(model,cat));record=dict(epoch=epoch,loss=float(np.mean(losses)),validation=metrics,elapsed=time.perf_counter()-start);history.append(record)
            print(folder.name,'epoch',epoch,'val_link_MRR',metrics['link_MRR'],flush=True)
            if metrics['link_MRR']>best:
                best=metrics['link_MRR'];best_epoch=epoch
                folder.mkdir(parents=True,exist_ok=True);torch.save(model.state_dict(),folder/'best.pt')
            if epoch-best_epoch>=args.patience:break
    save(folder/'history.jsonl',history)
    save(folder/'complete.json',dict(best_epoch=best_epoch,validation_link_MRR=best,seconds=time.perf_counter()-start,
         peak_cuda_bytes=torch.cuda.max_memory_allocated() if device.type=='cuda' else 0,checkpoint_sha256=file_sha(folder/'best.pt'),
         no_test_read=True,prototype=args.prototype))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--view',default='G1');p.add_argument('--seed',type=int,default=SEEDS[0]);p.add_argument('--dim',type=int,default=64)
    p.add_argument('--lr',type=float,default=.003);p.add_argument('--epochs',type=int,default=150);p.add_argument('--eval-every',type=int,default=10)
    p.add_argument('--patience',type=int,default=40);p.add_argument('--batch',type=int,default=128);p.add_argument('--negatives',type=int,default=32)
    p.add_argument('--reg',type=float,default=1e-4);p.add_argument('--aux-scale',type=float,default=.3)
    p.add_argument('--fraction',type=float,default=1.);p.add_argument('--noise',type=float,default=0.);p.add_argument('--prototype',default='none');p.add_argument('--run-tag',default='r1');fit(p.parse_args())
