import copy
from types import SimpleNamespace

import pytest
import torch

from src.research_point_3 import positive_guard as pg
from src.research_point_3.training import TrainingConfig
from scripts.audit_rp3_support_separability import alias_statistics, score_metrics


def reference():
    return {'availability_mask':torch.tensor([[True]]),'requested_candidate_mask':torch.tensor([[True]]),
            'support_labels':torch.tensor([[1]])}


def test_projection_feasibility_and_kkt_minimum():
    d=(torch.tensor([1.,2.],dtype=torch.float64),)
    g=(torch.tensor([2.,-1.],dtype=torch.float64),)
    v,m=pg.project_displacement(d,g,.1)
    assert m['projected_dot']==pytest.approx(m['halfspace_bound'])
    assert torch.allclose(d[0]-v[0],m['projection_coefficient']*g[0])
    # Tangential and inward feasible alternatives cannot be nearer to d.
    for delta in [torch.tensor([1.,2.]),torch.tensor([-1.,-2.]),-g[0]]:
        trial=v[0]+delta
        assert torch.dot(g[0],trial)<=m['halfspace_bound']+1e-12
        assert (trial-d[0]).square().sum()>=(v[0]-d[0]).square().sum()-1e-12


def test_feasible_zero_and_nonfinite_projection_cases():
    d=(torch.tensor([-2.,0.]),);g=(torch.tensor([1.,0.]),)
    v,m=pg.project_displacement(d,g,.1)
    assert torch.equal(v[0],d[0]) and not m['projected']
    v,m=pg.project_displacement(d,(torch.zeros(2),),.1)
    assert torch.equal(v[0],d[0]) and m['gradient_norm']==0
    with pytest.raises(ValueError):pg.project_displacement((torch.tensor([float('nan')]),),(torch.ones(1),),.1)


def test_backtracking_acceptance_uses_actual_adam_step(monkeypatch):
    model=torch.nn.Linear(1,1,bias=False)
    with torch.no_grad():model.weight.fill_(1)
    monkeypatch.setattr(pg,'positive_reference_loss',lambda model,ref:model.weight.square().sum())
    optimizer=torch.optim.AdamW(model.parameters(),lr=6.,weight_decay=0)
    model.weight.grad=torch.ones_like(model.weight)
    result=pg.PositiveStepGuard(reference()).step(model,optimizer)
    assert result['accepted'] and result['scale']==.25 and result['trial_count']==3
    assert result['positive_loss_after']<result['positive_loss_before']
    assert optimizer.state[model.weight]['step']==1


def test_rejection_restores_parameters_and_adam_state(monkeypatch):
    model=torch.nn.Linear(1,1,bias=False)
    with torch.no_grad():model.weight.fill_(1)
    monkeypatch.setattr(pg,'positive_reference_loss',lambda model,ref:model.weight.square().sum())
    optimizer=torch.optim.AdamW(model.parameters(),lr=.01,weight_decay=.01)
    model.weight.grad=torch.ones_like(model.weight);optimizer.step()
    with torch.no_grad():model.weight.fill_(1)
    optimizer.param_groups[0]['lr']=6.
    before=copy.deepcopy(optimizer.state_dict());parameter=model.weight.detach().clone()
    model.weight.grad=torch.ones_like(model.weight)
    result=pg.PositiveStepGuard(reference(),backtracks=0).step(model,optimizer)
    assert not result['accepted'] and result['optimizer_state_restored']
    assert torch.equal(model.weight,parameter)
    after=optimizer.state_dict()
    assert before['param_groups']==after['param_groups']
    for key,values in before['state'].items():
        for name,value in values.items():assert torch.equal(value,after['state'][key][name])


def test_reference_masks_unknown_unavailable_wrong_role_and_preserves_rng_mode():
    class Toy(torch.nn.Module):
        def __init__(self):
            super().__init__();self.s=torch.nn.Parameter(torch.zeros(1,4));self.dropout=torch.nn.Dropout(.5)
        def forward(self,*args):return SimpleNamespace(support_logits=self.dropout(self.s))
    model=Toy().train()
    ref={'availability_mask':torch.tensor([[True,True,False,True]]),
         'requested_candidate_mask':torch.tensor([[True,True,True,False]]),
         'support_labels':torch.tensor([[1,-100,1,1]]),
         'query_features':None,'candidate_features':None,'selection_budget':None}
    rng=torch.get_rng_state().clone()
    with pg.deterministic_reference_mode(model):
        loss=pg.positive_reference_loss(model,ref)
        grad=torch.autograd.grad(loss,model.s)[0]
    assert torch.equal(rng,torch.get_rng_state()) and model.training and model.dropout.training
    assert grad.tolist()==[[-.5,0.,0.,0.]]
    with pytest.raises(ValueError):TrainingConfig(positive_guard_margin=0.)


def test_alias_bound_and_auc_ties_are_auditable():
    rows=[{'key':'x','label':1,'trace_id':'a','evidence_id':'e','hard_empty':False,'probability':.5},
          {'key':'x','label':0,'trace_id':'b','evidence_id':'e','hard_empty':True,'probability':.5}]
    report=alias_statistics(rows,'key')
    assert report['empirical_minimum_01_errors']==1
    assert report['empirical_minimum_unweighted_bce']==pytest.approx(.69314718056)
    assert score_metrics(rows)['roc_auc']==.5
