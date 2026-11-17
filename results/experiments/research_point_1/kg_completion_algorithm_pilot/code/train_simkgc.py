"""Author SimKGC-IB model, adapted local encoder/data/weighted training runner.

Official two-tower BERT and compute_logits are imported unchanged. Pre-batch
memory is disabled; self negatives and in-batch contrastive loss are retained.
No TF-IDF/LSA substitution and no test-file access during fitting.
"""
import argparse
from collections import defaultdict
import importlib.util
import sys
import time
import types
from types import SimpleNamespace
import numpy as np
import torch
from torch.nn import functional as F
from transformers import AutoTokenizer
from common import PILOT,ROOT,RUN,SEEDS,read,save,seed_all,file_sha
from views import build
from eval_core import Evaluator


def author_class():
    # Author model imports construct_mask for its optional pre-batch cache.
    # We run official pre_batch=0, isolating it from the author's global data loader.
    shim=types.ModuleType('triplet_mask')
    def disabled(*a,**kw):raise RuntimeError('pre_batch=0; no external author data loader allowed')
    shim.construct_mask=disabled;sys.modules['triplet_mask']=shim
    path=PILOT/'dependencies/SimKGC/models.py'
    spec=importlib.util.spec_from_file_location('author_simkgc_models',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module.CustomBertModel


def setup(view,cat):
    path=ROOT/'data/model/BAAI-bge-small-zh-v1.5-r7999e1d'
    options=SimpleNamespace(pretrained_model=str(path),t=.05,finetune_t=True,additive_margin=.02,
         batch_size=32,pre_batch=0,pre_batch_weight=1.,use_self_negative=True,pooling='mean')
    tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True)
    items=read(RUN/'data/training_entity_text.jsonl')
    descriptions=[r['text'] if view=='G4' else r['label'] for r in items]
    return author_class()(options),tokenizer,descriptions,options


def query_text(h,r,descriptions,cat):
    n=len(cat['relations']);rel=cat['registry'][cat['relations'][r%n]]['label_zh']
    return descriptions[h]+' [SEP] '+('逆向关系：' if r>=n else '')+rel


@torch.no_grad()
def callback(model,tokenizer,descriptions,cat,targets,device):
    def encode(texts,encoder):
        result=[]
        for off in range(0,len(texts),128):
            batch=tokenizer(texts[off:off+128],padding='max_length',truncation=True,max_length=96,return_tensors='pt')
            ids=batch['input_ids'].to(device);mask=batch['attention_mask'].to(device);types_=batch.get('token_type_ids',torch.zeros_like(batch['input_ids'])).to(device)
            result.append(model._encode(encoder,ids,mask,types_))
        return torch.cat(result)
    tails=encode(descriptions[:cat['nbase']],model.tail_bert)
    R=len(cat['relations']);keys=set()
    for q in targets:
        h,r,t=q['triple'];keys.add((h,r));keys.add((t,r+R));keys.update((h,j) for j in range(R))
    keys=sorted(keys);queries=encode([query_text(h,r,descriptions,cat) for h,r in keys],model.hr_bert)
    qidx={k:i for i,k in enumerate(keys)};matrix=(queries@tails.T).cpu().numpy()
    def predict(h,r,t,task):
        if task=='tail':return matrix[qidx[h,r]]
        if task=='head':return matrix[qidx[t,r+R]]
        return np.array([matrix[qidx[h,j],t] for j in range(R)])
    return predict


def fit(args):
    folder=RUN/'models'/(f'simkgc_{args.view}_s{args.seed}'+('' if args.prototype=='none' else '_'+args.prototype))
    if (folder/'complete.json').exists():print('REUSE',folder,flush=True);return
    assert not folder.exists(),'Preserve interrupted SimKGC run; change tag before retry'
    seed_all(args.seed);device='cuda' if torch.cuda.is_available() else 'cpu'
    data=build(args.view,seed=args.seed);cat=data['catalogue'];R=len(cat['relations'])
    model,tokenizer,descriptions,options=setup(args.view,cat);model=model.to(device)
    reference=None;reference_hash=None
    if args.prototype!='none':
        assert args.view=='G3','Prototype isolates candidate trust; no additional text mechanism'
        ref_folder=RUN/'models'/f'simkgc_G1_s{args.seed}'
        assert (ref_folder/'complete.json').exists(),'Base anchor must have completed validation-only selection'
        state=torch.load(ref_folder/'best.pt',map_location=device,weights_only=True)
        model.load_state_dict(state)
        reference,_,_,_=setup('G1',cat);reference=reference.to(device);reference.load_state_dict(state);reference.eval()
        for parameter in reference.parameters():parameter.requires_grad_(False)
        reference_hash=file_sha(ref_folder/'best.pt')
    def augment(triples):
        return np.concatenate([triples,triples[:,[2,1,0]]+np.array([0,R,0])],axis=0)
    base=augment(data['base']);legal=data['legal'];aux=augment(data['aux'][legal]);weights=np.tile(data['weights'][legal],2)
    if args.prototype=='anchor_uniform':weights[:]=1.
    invalid=data['aux'][~legal];known=defaultdict(set)
    for h,r,t in np.concatenate([base,aux],axis=0):known[int(h),int(r)].add(int(t))
    optimizer=torch.optim.AdamW(model.parameters(),lr=args.lr,weight_decay=1e-4)
    validation=Evaluator.validation(cat);rng=np.random.default_rng(args.seed+4);aux_rng=np.random.default_rng(args.seed+5)
    def token(texts):
        d=tokenizer(texts,padding='max_length',truncation=True,max_length=96,return_tensors='pt')
        return d['input_ids'].to(device),d['attention_mask'].to(device),d.get('token_type_ids',torch.zeros_like(d['input_ids'])).to(device)
    def objective(triples,with_anchor=False):
        h,r,t=triples.T
        hi,hm,ht=token([query_text(int(a),int(b),descriptions,cat) for a,b in zip(h,r)])
        ti,tm,tt=token([descriptions[int(i)] for i in t]);si,sm,st=token([descriptions[int(i)] for i in h])
        out=model(hi,hm,ht,ti,tm,tt,si,sm,st)
        mask=np.ones((len(h),len(h)),dtype=bool)
        for i,(a,b,c) in enumerate(triples):
            for j,v in enumerate(t):
                if i!=j and int(v) in known[int(a),int(b)]:mask[i,j]=False
        batch=dict(triplet_mask=torch.tensor(mask,device=device),self_negative_mask=torch.tensor([int(a) not in known[int(a),int(b)] for a,b in zip(h,r)],device=device))
        logits=model.compute_logits(out,batch)
        ce=F.cross_entropy(logits['logits'],logits['labels'],reduction='none')
        if not with_anchor:return ce
        # Identical reference forward is executed for the continuation control too.
        with torch.no_grad():
            rq=reference._encode(reference.hr_bert,hi,hm,ht);rt=reference._encode(reference.tail_bert,ti,tm,tt)
            old_logits=(rq@rt.T)*reference.log_inv_t.exp()
        new_logits=(out['hr_vector']@out['tail_vector'].T)*model.log_inv_t.exp()
        invalid_mask=~batch['triplet_mask']
        old_logits=old_logits.masked_fill(invalid_mask,-1e4);new_logits=new_logits.masked_fill(invalid_mask,-1e4)
        kl=F.kl_div(F.log_softmax(new_logits,dim=-1),F.softmax(old_logits,dim=-1),reduction='batchmean')
        return ce,kl
    save(folder/'config.json',dict(vars(args),author_model_sha256=file_sha(PILOT/'dependencies/SimKGC/models.py'),
         author_commit='97cc43e488f19ca5b0f6fbf60ffefd2ee56c0693',implementation='Unchanged author CustomBertModel and compute_logits; adapted local encoder, sampling/known-train masks and uncertainty weights; IB+self-neg, pre_batch=0',
         options=vars(options),view=data['summary'],parameters=sum(p.numel() for p in model.parameters()),max_length=96,
         prototype=args.prototype,reference_checkpoint_sha256=reference_hash,anchor_lambda=1. if args.prototype.startswith('anchor') else 0.,
         sampler='same base exposure; added separate aux batch for G2-G4; extra cost reported, not equal FLOPs'))
    best=-1.;best_epoch=0;history=[];start=time.perf_counter();torch.cuda.reset_peak_memory_stats() if device=='cuda' else None
    for epoch in range(1,args.epochs+1):
        model.train();losses=[];anchor_values=[];perm=rng.permutation(len(base))
        for off in range(0,len(perm),args.batch):
            ix=perm[off:off+args.batch];optimizer.zero_grad(set_to_none=True)
            if reference is not None:
                ce,kl=objective(base[ix],with_anchor=True);loss=ce.mean()+(kl if args.prototype.startswith('anchor') else 0.*kl)
                anchor_values.append(float(kl.detach()))
            else:loss=objective(base[ix]).mean()
            if len(aux):
                ai=aux_rng.integers(0,len(aux),size=len(ix))
                loss=loss+.3*(objective(aux[ai])*torch.as_tensor(weights[ai],device=device)).mean()
            # Illegal Schema contexts remain traceable but are never contrastive positives.
            # Their handling is explicitly reported as excluded from this SimKGC-IB variant.
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step();losses.append(float(loss.detach()))
        model.eval();metrics,_=validation.score(callback(model,tokenizer,descriptions,cat,validation.targets,device))
        history.append(dict(epoch=epoch,loss=float(np.mean(losses)),anchor_KL=float(np.mean(anchor_values)) if anchor_values else None,validation=metrics,seconds=time.perf_counter()-start))
        print(folder.name,'epoch',epoch,'val_link_MRR',metrics['link_MRR'],flush=True)
        if metrics['link_MRR']>best:
            best=metrics['link_MRR'];best_epoch=epoch;torch.save(model.state_dict(),folder/'best.pt')
        if epoch-best_epoch>=args.patience:break
    save(folder/'history.jsonl',history)
    save(folder/'complete.json',dict(best_epoch=best_epoch,validation_link_MRR=best,seconds=time.perf_counter()-start,
         peak_cuda_bytes=torch.cuda.max_memory_allocated() if device=='cuda' else 0,checkpoint_sha256=file_sha(folder/'best.pt'),
         no_test_read=True,prototype=args.prototype,reference_checkpoint_sha256=reference_hash,illegal_context_rows_not_contrastive_positive=len(invalid)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--view',default='G1');p.add_argument('--seed',type=int,default=SEEDS[0]);p.add_argument('--epochs',type=int,default=10)
    p.add_argument('--patience',type=int,default=3);p.add_argument('--batch',type=int,default=32);p.add_argument('--lr',type=float,default=2e-5)
    p.add_argument('--prototype',choices=['none','continue','anchor','anchor_uniform'],default='none')
    # Existing server models retain their allocation. Serialize our own encoder jobs.
    import fcntl
    with (RUN/'gpu_training.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        fit(p.parse_args())
