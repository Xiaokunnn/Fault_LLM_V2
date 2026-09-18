import itertools
import math

import pytest
import torch

from src.research_point_3.joint_contract import capped_support_count, contract_mass, hard_empty_rows, hard_negative_support_loss
from src.research_point_3.model import CardFieldStateIndex as State
from src.research_point_3.training import TrainingConfig


@pytest.mark.parametrize('cap', [1, 2, 3, 5])
def test_capped_dp_matches_independent_assignment_enumeration(cap):
    p = torch.tensor([[.05, .9, .3, .75]], dtype=torch.float64)
    expected = torch.zeros(cap+1, dtype=torch.float64)
    for bits in itertools.product((0,1), repeat=4):
        probability = math.prod(float(p[0,i]) if bit else 1-float(p[0,i]) for i,bit in enumerate(bits))
        expected[min(sum(bits),cap)] += probability
    got = capped_support_count(p,cap)[0]
    assert torch.allclose(got,expected,atol=1e-14)
    assert float(got.sum()) == pytest.approx(1.0)


def test_contract_mass_matches_full_joint_enumeration_and_projection_identity():
    support = torch.tensor([[-.3,.7,-2.]],dtype=torch.float64)
    fields = torch.tensor([[.2,-.1,.9,-.5]],dtype=torch.float64)
    counts = torch.tensor([[.8,.2,-.6,-1.]],dtype=torch.float64)
    p,f,q = support.sigmoid()[0],fields.softmax(-1)[0],counts.softmax(-1)[0]
    valid_terms=[]
    for bits in itertools.product((0,1), repeat=3):
        prob=math.prod(float(p[i]) if b else 1-float(p[i]) for i,b in enumerate(bits))
        for n in range(4):
            for state in range(4):
                valid=(n<=sum(bits) and ((n==0 and state in (State.INSUFFICIENT,State.NOT_APPLICABLE))
                    or (n>=1 and state==State.SUPPORTED) or (n>=2 and state==State.CONFLICT)))
                if valid: valid_terms.append(prob*float(q[n])*float(f[state]))
    z=sum(valid_terms)
    got=float(contract_mass(support,fields,counts,torch.ones_like(support,dtype=torch.bool)))
    assert got==pytest.approx(z,abs=1e-14)
    kl=sum((v/z)*math.log((v/z)/v) for v in valid_terms)
    assert kl==pytest.approx(-math.log(z))
    assert 1-z <= -math.log(z)


def test_semantic_gradient_numerical_check_and_mask_isolation():
    torch.manual_seed(81)
    args=tuple(torch.randn(*shape,dtype=torch.float64,requires_grad=True) for shape in [(2,3),(2,4),(2,4)])
    mask=torch.tensor([[True,False,True],[False,False,False]])
    fn=lambda a,b,c:-contract_mass(a,b,c,mask).log().mean()
    assert torch.autograd.gradcheck(fn,args)
    grad=torch.autograd.grad(fn(*args),args)[0]
    assert torch.equal(grad[~mask],torch.zeros_like(grad[~mask]))


def test_no_candidates_extreme_logits_and_conflict_minimum():
    s=torch.tensor([[1000.,-1000.]],requires_grad=True)
    f=torch.tensor([[-1000.]*4],requires_grad=True)
    # Impossible conflict count=1 has negligible mass, but bounded loss stays finite.
    with torch.no_grad(): f[0,State.CONFLICT]=1000.
    n=torch.tensor([[-1000.,1000.,-1000.,-1000.]],requires_grad=True)
    mass=contract_mass(s,f,n,torch.ones_like(s,dtype=torch.bool))
    assert float(mass)==0.
    loss=-mass.clamp_min(1e-12).log().mean();loss.backward()
    assert torch.isfinite(loss) and all(torch.isfinite(x.grad).all() for x in (s,f,n))
    f=torch.zeros(1,4,dtype=torch.float64);n=torch.zeros(1,4,dtype=torch.float64)
    mass=contract_mass(s.detach().double(),f,n,torch.zeros_like(s,dtype=torch.bool))
    assert float(mass)==pytest.approx(.5*.25)
    assert capped_support_count(torch.empty(2,0),3).tolist()==[[1.,0.,0.,0.]]*2


def test_hard_loss_excludes_unknown_positive_and_unavailable_and_bounds_false_fill():
    labels=torch.tensor([[0,0],[0,-100],[0,1],[-100,-100],[0,-100]])
    mask=torch.tensor([[True,True],[True,True],[True,True],[False,False],[True,False]])
    counts=torch.tensor([0,0,0,0,0])
    assert hard_empty_rows(labels,mask,counts).tolist()==[True,False,False,False,True]
    logits=torch.tensor([[.3,-.7],[1.,1.],[1.,1.],[1.,1.],[-1.,1000.]],requires_grad=True)
    loss=hard_negative_support_loss(logits,labels,mask,counts,2/5)
    expected=(torch.nn.functional.softplus(logits[0]).sum()+torch.nn.functional.softplus(logits[4,0]))/2
    assert torch.allclose(loss,expected)
    loss.backward()
    assert torch.equal(logits.grad[1:4],torch.zeros_like(logits.grad[1:4]))
    assert logits.grad[4,1]==0
    assert 1 <= float(torch.nn.functional.softplus(logits[0]).sum())/math.log(2)


def test_empty_hard_batch_zero_grad_and_invalid_config_rejected():
    logits=torch.zeros(2,3,requires_grad=True)
    loss=hard_negative_support_loss(logits,torch.ones(2,3),torch.ones(2,3,dtype=torch.bool),torch.ones(2),.1)
    loss.backward()
    assert float(loss)==0 and torch.equal(logits.grad,torch.zeros_like(logits))
    with pytest.raises(ValueError): TrainingConfig(joint_contract_weight=.1)
    with pytest.raises(ValueError): TrainingConfig(joint_contract_weight=float('nan'))
