"""One low-rank residual over fixed retrieval; no learned gates or extra losses."""
import math
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from io_utils import *

VARIANTS={
    'full':('R3',16,'all'), 'no_retrieval':('R0',16,'all'),
    'no_relation':('R1',16,'all'), 'no_structure':('R2',16,'all'),
    'no_evidence':('R3',16,'all'), 'k8':('R3',8,'all'),
    'k32':('R3',32,'all'), 'conservative':('R3',16,'conservative')}


class Context:
    def __init__(self, seed):
        self.data=torch.load(EXP/'features'/f'G2_s{seed}.pt',map_location='cuda',weights_only=True)
        self.meta=torch.load(EXP/'index/vectors.pt',map_location='cuda',weights_only=True)
        views=read(EXP/'index/oriented_views.jsonl');edges=read(EXP/'index/edges.jsonl')
        self.a=torch.tensor([v['anchor'] for v in views],device='cuda');self.b=torch.tensor([v['neighbor'] for v in views],device='cuda')
        self.r=torch.tensor([v['relation'] for v in views],device='cuda')
        self.quality=torch.tensor([edges[v['edge_index']]['features'] for v in views],device='cuda')
        self.flags=torch.tensor([v['flags'] for v in views],device='cuda')
        self.cache={};self.lookup={(x[0],x[1],x[3]):i for i,x in enumerate(read(EXP/'retrieval/train_example_keys.json'))}
    def values(self,h,r,variant,training_ids=None,retrieval=None):
        strategy,k,pool=retrieval or VARIANTS.get(variant,('R3',16,'all'))
        key=(strategy,pool,'train' if training_ids else 'global')
        if key not in self.cache:
            z=np.load(EXP/'retrieval'/f'{strategy}_{pool}_{key[-1]}.npz')
            self.cache[key]={k:torch.as_tensor(z[k],device='cuda') for k in ['ids','scores']}
        z=self.cache[key];hs=torch.as_tensor(h,device='cuda');rs=torch.as_tensor(r,device='cuda')
        if training_ids:
            loc=torch.tensor([self.lookup[int(a),int(b),c] for a,b,c in zip(h,r,training_ids)],device='cuda')
            ids=z['ids'][loc,:k].long();scores=z['scores'][loc,:k]
        else:ids=z['ids'][hs,rs,:k].long();scores=z['scores'][hs,rs,:k]
        mask=ids>=0;ix=ids.clamp_min(0)
        weights=torch.softmax(torch.cat([scores.masked_fill(~mask,-1e4)/.1,torch.zeros((len(h),1),device='cuda')],-1),-1)[:,:-1]*mask
        def mean(v):return (weights[:,:,None]*v).sum(1)
        e=self.data['entities'];a=self.a[ix];b=self.b[ix];rels=self.r[ix]
        # Analogy/transport preserves ordered roles; it is a hypothesis, not a
        # transitive causal assertion and never writes a graph edge.
        transport=e[b]-e[a]+e[hs,None,:]
        relation=self.meta['relations'][rels]
        semantic=self.meta['semantic'][ix]
        quality=self.quality[ix];flags=self.flags[ix]
        if variant=='no_relation':transport=e[b];relation=torch.zeros_like(relation)
        if variant=='no_evidence':semantic=self.meta['plain'][ix];quality=torch.zeros_like(quality);flags=torch.zeros_like(flags)
        features=torch.cat([mean(transport),mean(relation),mean(semantic),mean(quality),mean(flags),weights.sum(1,keepdim=True),scores.masked_fill(~mask,0).max(1,keepdim=True).values],-1)
        return self.data['queries'][hs,rs],features,mask.any(1),mean(e[b]),mean(transport),ids


class Residual(nn.Module):
    def __init__(self):
        super().__init__();self.down=nn.Linear(1558,64);self.up=nn.Linear(64,512,bias=False);nn.init.zeros_(self.up.weight)
    def forward(self,q,x,available):
        residual=.5*torch.tanh(self.up(torch.tanh(self.down(x))))/math.sqrt(512)
        residual=residual*available[:,None]
        return F.normalize(q+residual,dim=-1)


def scores(model,context,keys,variant):
    out=[];n=read(EXP/'data/catalogue.json')['nbase']
    with torch.no_grad():
        for off in range(0,len(keys),128):
            kk=keys[off:off+128];q,x,m,*_=context.values([k[0] for k in kk],[k[1] for k in kk],variant)
            out.append((model(q,x,m)@context.data['entities'][:n].T).cpu().numpy())
    return np.concatenate(out)
