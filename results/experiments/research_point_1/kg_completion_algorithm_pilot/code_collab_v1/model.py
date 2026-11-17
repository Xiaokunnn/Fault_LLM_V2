"""Relation-aware candidate collaboration with explicit zero-message abstention."""
from collections import defaultdict
import math
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from collab_io import *


class Neighborhood:
    def __init__(self,variant,seed,max_neighbors=16):
        self.R=len(read(RUN/'data/catalogue.json')['relations']);self.limit=max_neighbors
        self.meta=read(RUN/'data/train_group_context.json')
        self.ids={x['claim_id']:x['group_id'] for x in read(RUN/'data/base_split.jsonl') if x['fold']=='train'}
        self.adj=defaultdict(list);self.cache={};self.rows=[]
        noise={r['edge_id']:r for r in read(RUN/f'data/noise_context_{seed}.jsonl')} if variant.startswith('noise') else {}
        for original in read(RUN/'data/context_edges.jsonl'):
            e=dict(original)
            if not e['legal']:continue
            if not e['is_base']:
                if variant=='conservative' and not e['conservative']:continue
                fraction=.25 if variant=='scale25' else .5 if variant=='scale50' else 1.
                if int(digest(['scale',seed,e['edge_id']])[:12],16)/16**12>fraction:continue
                if noise:
                    perturb=noise[e['edge_id']];rate=.25 if variant=='noise25' else .5
                    if perturb['draw']<rate and perturb['replacement'] is not None:e['triple']=perturb['replacement'];e['synthetic_corruption']=True
            self.rows.append(e)
            h,r,t=e['triple']
            self.adj[h].append((t,r,e));self.adj[t].append((h,r+self.R,e))
        self.logic=np.zeros((2*self.R,2*self.R),dtype=np.float32);rel_nodes=defaultdict(set)
        for node,entries in self.adj.items():
            for _,r,_ in entries:rel_nodes[r].add(node)
        for r in range(2*self.R):
            for q in range(2*self.R):self.logic[r,q]=len(rel_nodes[r]&rel_nodes[q])/max(1,len(rel_nodes[r]))

    def entries(self,h,training_id=None):
        group=self.ids[training_id] if training_id is not None else None
        key=(h,group)
        if key in self.cache:return self.cache[key]
        meta=self.meta.get(group);out=[]
        for t,r,e in self.adj[h]:
            if meta:
                if e['group_id']==group:continue
                if e['pair'] in meta['pairs']:continue
                if not e['is_base'] and set(map(tuple,e['pages']))&set(map(tuple,meta['pages'])):continue
            out.append((t,r,e))
        out.sort(key=lambda x:(not x[2]['is_base'],digest(['neighbor',x[2]['edge_id'],x[0],x[1]])))
        self.cache[key]=out[:self.limit];return self.cache[key]

    def pack(self,heads,training_ids=None,device='cuda'):
        b=len(heads);N=self.limit
        idx=np.zeros((b,N),dtype=np.int64);rel=idx.copy();features=np.zeros((b,N,12),np.float32)
        mask=np.zeros((b,N),bool);base=mask.copy();fixed=np.zeros((b,N),np.float32);logic=np.zeros((b,N,2*self.R),np.float32)
        for i,h in enumerate(heads):
            entries=self.entries(int(h),training_ids[i] if training_ids is not None else None)
            for j,(t,r,e) in enumerate(entries):
                idx[i,j]=t;rel[i,j]=r;features[i,j]=e['features'];mask[i,j]=True;base[i,j]=e['is_base'];fixed[i,j]=e['fixed_weight']
                other={r2 for _,r2,_ in entries if r2!=r};den=max([self.logic[o,r] for o in other]+[.05])
                logic[i,j]=self.logic[r]/den
        return {k:torch.as_tensor(v,device=device) for k,v in dict(idx=idx,rel=rel,features=features,mask=mask,base=base,fixed=fixed,logic=logic).items()}


class Collaboration(nn.Module):
    def __init__(self,R,dim=512,hidden=64,variant='full'):
        super().__init__();self.variant=variant;self.R=R;self.hidden=hidden
        self.relation=nn.Embedding(2*R,hidden);self.direction=nn.Embedding(2,hidden)
        self.query=nn.Linear(dim,hidden,bias=False);self.neighbor=nn.Linear(dim,hidden,bias=False)
        self.attention=nn.Linear(hidden,1,bias=False)
        self.trust=nn.Sequential(nn.Linear(15,32),nn.Tanh(),nn.Linear(32,1))
        self.output=nn.Linear(hidden,dim,bias=False);nn.init.zeros_(self.output.weight)
        self.null_logit=nn.Parameter(torch.zeros(1))

    def forward(self,q,r,entities,pack,return_details=False):
        a=self.query(q);neighbor=self.neighbor(entities[pack['idx']]);role=self.direction(pack['rel']//self.R)
        if self.variant=='no_relation':qrel=torch.zeros_like(a);erel=torch.zeros_like(neighbor)
        else:qrel=self.relation(r);erel=self.relation(pack['rel'])
        values=torch.tanh(neighbor+erel+role)
        att=self.attention(torch.tanh(a[:,None,:]+qrel[:,None,:]+values)).squeeze(-1)
        att=att.masked_fill(~pack['mask'],-1e4)
        if self.variant=='lan':
            neural=torch.softmax(att,dim=-1)*pack['mask']
            logic=pack['logic'].gather(-1,r[:,None,None].expand(-1,pack['idx'].shape[1],1)).squeeze(-1)
            weights=(neural+logic)*pack['mask'];gates=torch.ones_like(weights);null=torch.zeros(len(q),device=q.device)
        else:
            semantic=(q[:,None,:]*entities[pack['idx']]).sum(-1)
            rolecos=F.cosine_similarity(qrel[:,None,:],erel,dim=-1)
            count=pack['mask'].sum(-1).clamp_min(1).float().log1p()[:,None].expand_as(semantic)/3
            inputs=torch.cat([pack['features'],semantic[:,:,None],rolecos[:,:,None],count[:,:,None]],-1)
            learned=torch.sigmoid(self.trust(inputs).squeeze(-1))
            gates=torch.where(pack['base'],torch.ones_like(learned),learned)
            if self.variant=='no_dynamic':gates=torch.ones_like(gates)
            if self.variant=='fixed':gates=pack['fixed']
            null_column=self.null_logit.expand(len(q),1) if self.variant!='no_null' else torch.full((len(q),1),-1e4,device=q.device)
            prob=torch.softmax(torch.cat([att,null_column],-1),dim=-1)
            null=prob[:,-1];weights=prob[:,:-1]*gates*pack['mask']
        message=(weights[:,:,None]*values).sum(1)
        if self.variant=='no_neighbor':message=torch.tanh(a+qrel)
        residual=.25*torch.tanh(self.output(message))/math.sqrt(q.shape[-1])
        enhanced=F.normalize(q+residual,dim=-1)
        if return_details:return enhanced,dict(gates=gates,weights=weights,null=null,residual_norm=residual.norm(dim=-1))
        return enhanced
