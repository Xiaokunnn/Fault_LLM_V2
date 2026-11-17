"""Fresh new-split author SimKGC baselines, preserving existing experiments."""
import argparse
from types import SimpleNamespace
import gc
import time
import numpy as np
import torch
from io_utils import *
import train_simkgc as original
from views import build as original_build


def build(view, seed, **kwargs):
    if view != 'filter': return original_build(view, seed=seed)
    x=original_build('G3',seed=seed)
    admissible={tuple(e['triple']) for e in read(EXP/'data/context_edges.jsonl') if not e['is_base'] and e['simple_filter']}
    keep=np.array([tuple(t) in admissible for t in x['aux']])
    for k in ['aux','weights','legal']: x[k]=x[k][keep]
    x['weights'][:]=1.;x['legal'][:]=True
    x['aux_rows']=[r for r,k in zip(x['aux_rows'],keep) if k]
    x['summary']=dict(x['summary'],view='filter',aux_edges=len(x['aux']),filter='Schema legal AND existing executable location contract')
    return x


def cache(seed,view):
    out=EXP/'features'/f'{view}_s{seed}.pt'
    if out.exists(): return
    cat=read(EXP/'data/catalogue.json');R=len(cat['relations']);n=cat['nbase']
    start=time.perf_counter();model,tok,texts,_=original.setup(view,cat)
    path=EXP/'models'/f'simkgc_{view}_s{seed}'/'best.pt'
    model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True));model.cuda().eval()
    def encode(values,encoder):
        z=[]
        with torch.no_grad():
            for off in range(0,len(values),128):
                b=tok(values[off:off+128],padding='max_length',truncation=True,max_length=96,return_tensors='pt')
                z.append(model._encode(encoder,b['input_ids'].cuda(),b['attention_mask'].cuda(),b.get('token_type_ids',torch.zeros_like(b['input_ids'])).cuda()).cpu())
        return torch.cat(z)
    entities=encode(texts,model.tail_bert)
    queries=encode([original.query_text(h,r,texts,cat) for h in range(n) for r in range(2*R)],model.hr_bert).reshape(n,2*R,-1)
    out.parent.mkdir(exist_ok=True,parents=True);torch.save(dict(entities=entities,queries=queries),out)
    save(out.with_suffix('.json'),dict(checkpoint_sha256=file_sha(path),feature_sha256=file_sha(out),seconds=time.perf_counter()-start,queries=list(queries.shape),entities=len(entities),no_test_input=True))
    del model;gc.collect();torch.cuda.empty_cache()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int);args=parser.parse_args()
    while not (EXP/'data/freeze.json').exists():time.sleep(2)
    original.build=build
    for seed in [args.seed] if args.seed else SEEDS:
        for view in ['G1','G2','filter']:
            original.fit(SimpleNamespace(view=view,seed=seed,epochs=10,patience=3,batch=32,lr=2e-5,prototype='none'))
            cache(seed,view)
    save(EXP/'configs/foundations_complete.json',dict(seeds=[args.seed] if args.seed else SEEDS,views=['G1','G2','filter'],fresh_pretrained_initialization=True))


if __name__=='__main__': main()
