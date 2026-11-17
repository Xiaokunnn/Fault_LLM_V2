"""Counterfactual packs and gradient paths, reusing the unchanged old model."""
import torch
import numpy as np
from role_io import *
from fit_collab import load


def load_parent(seed):return load(seed,'full',checkpoint(seed))


def make_packs(graph,pairs):
    p=graph.pack([x['h'] for x in pairs],[x['training_id'] for x in pairs])
    slots=torch.tensor([x['slot'] for x in pairs],device='cuda');batch=torch.arange(len(pairs),device='cuda')
    p['base'][batch,slots]=False;p['features'][batch,slots,7]=0.
    for i,x in enumerate(pairs):
        assert int(p['idx'][i,slots[i]])==x['neighbor'] and int(p['rel'][i,slots[i]])==x['edge_relation']
    plus={k:v.clone() for k,v in p.items()};minus={k:v.clone() for k,v in p.items()};zero={k:v.clone() for k,v in p.items()}
    minus['idx'][batch,slots]=torch.tensor([x['negative_neighbor'] for x in pairs],device='cuda')
    minus['rel'][batch,slots]=torch.tensor([x['negative_relation'] for x in pairs],device='cuda')
    zero['mask'][batch,slots]=False
    return plus,minus,zero,slots


def forward_probe(model,q,r,entities,pack,slots,unit_gate=False,selected_gradient=False):
    captured=[];mask=torch.zeros((*pack['mask'].shape,1),device=q.device)
    mask[torch.arange(len(q),device=q.device),slots]=1.
    def hook(module,args,output):
        captured.append(output)
        if unit_gate:return output*(1-mask)+20.*mask
        if selected_gradient:return output*mask+output.detach()*(1-mask)
        return output
    handle=model.trust.register_forward_hook(hook)
    try:enhanced=model(q,r,entities,pack)
    finally:handle.remove()
    logits=captured[0][torch.arange(len(q),device=q.device),slots,0]
    return enhanced,logits


def task_margin(v,entities,pairs):
    values=[]
    for i,p in enumerate(pairs):
        good=entities[torch.tensor(p['positive_tail_ids'],device=v.device)]
        alternatives=entities[torch.tensor(p['competitor_ids'],device=v.device)]
        values.append(.05*(torch.logsumexp(20*(good@v[i]),0)-torch.logsumexp(20*(alternatives@v[i]),0)))
    return torch.stack(values)


def input_logits(model,q,r,entities,pack):
    a=model.relation(r);b=model.relation(pack['rel'])
    semantic=(q[:,None,:]*entities[pack['idx']]).sum(-1)
    rolecos=torch.nn.functional.cosine_similarity(a[:,None,:],b,dim=-1)
    count=pack['mask'].sum(-1).clamp_min(1).float().log1p()[:,None].expand_as(semantic)/3
    inputs=torch.cat([pack['features'],semantic[:,:,None],rolecos[:,:,None],count[:,:,None]],-1)
    return inputs,model.trust(inputs).squeeze(-1)
