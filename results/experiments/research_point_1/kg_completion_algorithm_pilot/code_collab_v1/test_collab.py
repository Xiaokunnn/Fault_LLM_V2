import numpy as np
import torch
from collab_io import RUN,read,OLD
from model import Collaboration,Neighborhood


def fake_pack(batch=3,N=4):
    return dict(idx=torch.tensor([[1,2,3,4]]*batch),rel=torch.tensor([[1,2,3,4]]*batch),
        features=torch.rand(batch,N,12),mask=torch.ones(batch,N,dtype=torch.bool),base=torch.zeros(batch,N,dtype=torch.bool),
        fixed=torch.full((batch,N),.1),logic=torch.ones(batch,N,30))


def test_zero_initial_residual_equals_backbone():
    torch.manual_seed(9);m=Collaboration(15);q=torch.nn.functional.normalize(torch.randn(3,512),dim=-1);e=torch.randn(9,512)
    out=m(q,torch.tensor([1,2,3]),e,fake_pack())
    torch.testing.assert_close(out,q)


def test_absolute_gate_and_null_have_finite_nonzero_gradients():
    torch.manual_seed(8);m=Collaboration(15);torch.nn.init.normal_(m.output.weight,std=.01)
    q=torch.nn.functional.normalize(torch.randn(3,512),dim=-1);e=torch.nn.functional.normalize(torch.randn(9,512),dim=-1)
    out,details=m(q,torch.tensor([1,2,3]),e,fake_pack(),True)
    (out*torch.randn_like(out)).sum().backward()
    assert m.trust[-1].weight.grad.abs().sum()>0 and torch.isfinite(m.trust[-1].weight.grad).all()
    assert m.null_logit.grad.abs().sum()>0
    assert ((details['gates']>=0)&(details['gates']<=1)).all()


def test_permutation_invariance_and_empty_context():
    torch.manual_seed(4);m=Collaboration(15);torch.nn.init.normal_(m.output.weight,std=.01)
    q=torch.nn.functional.normalize(torch.randn(3,512),dim=-1);e=torch.nn.functional.normalize(torch.randn(9,512),dim=-1);p=fake_pack()
    a=m(q,torch.tensor([1,2,3]),e,p)
    pp={k:v[:,[2,0,3,1]] for k,v in p.items()}
    torch.testing.assert_close(a,m(q,torch.tensor([1,2,3]),e,pp))
    p['mask'][:]=False
    torch.testing.assert_close(q,m(q,torch.tensor([1,2,3]),e,p))


def test_training_context_excludes_family_pair_and_candidate_source_page():
    graph=Neighborhood('full',14112026)
    for q in read(RUN/'data/train_base.jsonl'):
        g=graph.ids[q['id']];meta=graph.meta[g]
        for h in [q['triple'][0],q['triple'][2]]:
            for _,_,e in graph.entries(h,q['id']):
                assert e['group_id']!=g and e['pair'] not in meta['pairs']
                assert e['is_base'] or not set(map(tuple,e['pages']))&set(map(tuple,meta['pages']))


def test_no_held_targets_in_training_modules():
    from pathlib import Path
    for name in ['fit_collab.py','model.py','cache_text.py','baselines.py']:
        text=Path(__file__).with_name(name).read_text()
        for forbidden in ['test_targets.jsonl','test_truth.json','/audit_only/']:
            assert forbidden not in text


def test_cold_fold_is_unchanged():
    if RUN.name=='cold':
        assert read(RUN/'data/train_base.jsonl')==read(OLD/'data/train_base.jsonl')
        assert read(RUN/'data/validation_targets.jsonl')==read(OLD/'data/validation_targets.jsonl')


def test_learned_head_retains_relation_direction():
    torch.manual_seed(2);m=Collaboration(15);torch.nn.init.normal_(m.output.weight,std=.05)
    q=torch.nn.functional.normalize(torch.randn(3,512),dim=-1);e=torch.nn.functional.normalize(torch.randn(9,512),dim=-1);p=fake_pack()
    a=m(q,torch.tensor([1,2,3]),e,p);p['rel']+=15
    assert not torch.allclose(a,m(q,torch.tensor([1,2,3]),e,p))
