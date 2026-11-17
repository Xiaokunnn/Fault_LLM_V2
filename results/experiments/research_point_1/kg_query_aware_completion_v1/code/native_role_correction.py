"""Mechanical source-field correction; same architecture, loss and settings.

Native cells expose `role`, not `column_role`. Preserve the initial index and
all results, replace only semantic/role fields in a separate feature overlay.
No changes to retrieval, answers, split, objectives or model selection.
"""
import gc
import time
import copy
import json
from collections import Counter,defaultdict
import numpy as np
import torch
from torch.nn import functional as F
from transformers import AutoModel,AutoTokenizer
from io_utils import *
from query_model import Context,Residual,VARIANTS,scores
from build_index import edge_sources,bindings
from train_adapters import validation
from eval_core import Evaluator

COR=EXP/'native_role_correction'


def prepare():
    if (COR/'feature_freeze.json').exists():return
    views=read(EXP/'index/oriented_views.jsonl');edges=read(EXP/'index/edges.jsonl');registry=read(EXP/'data/training_source_registry.json');texts=[];flags=[];counts=Counter();cellrole={}
    for v in views:
        ss=edge_sources(edges[v['edge_index']],registry);info=bindings(ss);roles={}
        for x in ss:
            for u in x.get('evidence_units') or []:
                roles[u.get('cell_id')]=u.get('role');cellrole[u.get('cell_id')]=u.get('role')
        for x in info:
            for u in x['layout']:
                role=roles.get(u.get('cell_id'))
                if role is not None:u['role']=role
        text=v['plain']+' 适用和证据绑定：'+canonical(info) if info else v['semantic']
        f=list(v['flags']);f[5]=float(any(r and r!='unclassified' for r in roles.values()))
        texts.append(text);flags.append(f);counts['views_with_known_native_role']+=int(f[5])
    path=ROOT/'data/model/BAAI-bge-small-zh-v1.5-r7999e1d';tok=AutoTokenizer.from_pretrained(path,local_files_only=True);m=AutoModel.from_pretrained(path,local_files_only=True).cuda().eval();zz=[]
    with torch.no_grad():
        for off in range(0,len(texts),128):
            b=tok(texts[off:off+128],padding=True,truncation=True,max_length=192,return_tensors='pt');v=m(**{k:v.cuda() for k,v in b.items()}).last_hidden_state[:,0];zz.append(F.normalize(v,dim=-1).cpu())
    COR.mkdir(exist_ok=True,parents=True);torch.save(dict(semantic=torch.cat(zz),flags=torch.tensor(flags,dtype=torch.float32)),COR/'vectors.pt')
    save(COR/'cell_roles.json',cellrole);save(COR/'corrected_semantic_text.jsonl',[dict(view_id=i,text=t,flags=flags[i]) for i,t in enumerate(texts)])
    save(COR/'feature_freeze.json',dict(vector_sha256=file_sha(COR/'vectors.pt'),texts_sha256=file_sha(COR/'corrected_semantic_text.jsonl'),counts=counts,cell_role_counts=dict(Counter(cellrole.values())),
        correction='Read actual evidence_units.role and include it in the serialized layout and presence flag. All other fields/encoder/token budget unchanged.',test_exposure_disclosed=True,no_hyperparameter_changes=True,retrieval_unchanged=True))
    del m;gc.collect();torch.cuda.empty_cache()


class NativeContext(Context):
    def __init__(self,seed):
        super().__init__(seed);x=torch.load(COR/'vectors.pt',map_location='cuda',weights_only=True)
        self.meta['semantic']=x['semantic'];self.flags=x['flags']


def fit(seed,variant):
    folder=EXP/'models'/f'native_query_{variant}_s{seed}'
    if (folder/'complete.json').exists():return
    assert not folder.exists(),'Keep incomplete models; no overwrite'
    seed_all(seed);ctx=NativeContext(seed);model=Residual().cuda();cat=read(EXP/'data/catalogue.json');n=cat['nbase'];ev=Evaluator.validation(cat);train=read(EXP/'retrieval/train_example_keys.json');known=defaultdict(set)
    for h,r,t,cid in train:known[h,r].add(t)
    opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=1e-4);rng=np.random.default_rng(seed+4);start=time.perf_counter();torch.cuda.reset_peak_memory_stats();best=validation(model,ctx,ev,variant);be=0;hist=[dict(epoch=0,validation_link_MRR=best)]
    original=read(EXP/'models'/f'query_{variant}_s{seed}'/'config.json');save(folder/'config.json',dict(original,feature_field_correction=True,correction_freeze=file_sha(COR/'feature_freeze.json'),original_config_sha256=file_sha(EXP/'models'/f'query_{variant}_s{seed}'/'config.json')));torch.save(model.state_dict(),folder/'best.pt')
    for epoch in range(1,61):
        losses=[];perm=rng.permutation(len(train))
        for off in range(0,len(train),128):
            batch=[train[i] for i in perm[off:off+128]];h=[x[0] for x in batch];r=[x[1] for x in batch];target=torch.tensor([x[2] for x in batch],device='cuda')
            q,x,m,*_=ctx.values(h,r,variant,[x[3] for x in batch]);logits=20*(model(q,x,m)@ctx.data['entities'][:n].T)
            for j,(a,b,y,cid) in enumerate(batch):
                other=list(known[a,b]-{y})
                if other:logits[j,other]=-1e4
            loss=F.cross_entropy(logits,target);opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step();losses.append(float(loss.detach()))
        if epoch%5==0:
            v=validation(model,ctx,ev,variant);hist.append(dict(epoch=epoch,loss=float(np.mean(losses)),validation_link_MRR=v,seconds=time.perf_counter()-start))
            if v>best:best=v;be=epoch;torch.save(model.state_dict(),folder/'best.pt')
            print('NATIVE_ROLE',seed,variant,epoch,v,flush=True)
            if epoch-be>=15:break
    save(folder/'history.jsonl',hist);save(folder/'complete.json',dict(best_epoch=be,executed_epochs=epoch,validation_link_MRR=best,seconds=time.perf_counter()-start,peak_cuda_bytes=torch.cuda.max_memory_allocated(),checkpoint_sha256=file_sha(folder/'best.pt'),selection_unchanged=True))
    del ctx,model,opt;gc.collect();torch.cuda.empty_cache()


def main():
    torch.set_num_threads(2);prepare()
    # no_evidence zeroes all altered fields, so it must be exactly unchanged.
    # Reuse this matched control instead of pointless repeated training.
    variants=[v for v in VARIANTS if v!='no_evidence']
    for seed in SEEDS:
        for variant in variants:fit(seed,variant)
    save(COR/'models_complete.json',dict(new_models=21,reused_no_evidence_controls=3,all_hyperparameters_identical=True))
    save(COR/'test_release.json',dict(models={f'{v}_s{s}':file_sha(EXP/'models'/f'native_query_{v}_s{s}'/'best.pt') for v in variants for s in SEEDS},code=file_sha(Path(__file__)),original_test_already_exposed=True,only_source_field_bug_corrected=True))
    targets=read(EXP/'audit_only/test_targets.jsonl');cat=read(EXP/'data/catalogue.json');R=len(cat['relations']);ev=Evaluator(targets,read(EXP/'audit_only/test_truth.json'),cat,list(range(cat['nbase'])))
    keys=sorted({k for x in targets for k in [(x['triple'][2],x['triple'][1]+R)]+[(x['triple'][0],r) for r in range(R)]});idx={k:i for i,k in enumerate(keys)}
    for seed in SEEDS:
        ctx=NativeContext(seed)
        for variant in variants:
            name=f'native_query_{variant}_s{seed}';out=EXP/'evaluation'/name
            if (out/'complete.json').exists():continue
            model=Residual().cuda();model.load_state_dict(torch.load(EXP/'models'/name/'best.pt',map_location='cuda',weights_only=True));model.eval();matrix=scores(model,ctx,keys,variant)
            def p(h,r,t,task):return np.array([matrix[idx[h,j],t] for j in range(R)]) if task=='relation' else matrix[idx[(h,r) if task=='tail' else (t,r+R)]]
            m,rows=ev.score(p);save(out/'metrics.json',dict(m,method='native_query_'+variant,seed=seed,source_field_corrected=True,not_new_independent_test=True));save(out/'rankings.jsonl',rows)
            np.savez_compressed(out/'scores.npz',**{task:np.stack([p(*x['triple'],task) for x in targets]) for task in ['head','tail','relation']});save(out/'complete.json',dict(field_correction_only=True));print('NATIVE_TEST',seed,variant,m['link_MRR'],flush=True)
        del ctx;gc.collect();torch.cuda.empty_cache()
    save(COR/'complete.json',dict(new_models=21,matched_controls_reused=3,new_scores=21,independence='Corrective run on same exposed internal task, no new independence claim'))


if __name__=='__main__':main()
