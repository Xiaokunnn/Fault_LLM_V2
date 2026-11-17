from pathlib import Path
import torch
from torch.nn import functional as F
from role_io import *
from model import Neighborhood,Collaboration


def test_saturated_logit_absolute_loss_has_recovery_gradient():
    l=torch.tensor([15.],requires_grad=True);loss=F.binary_cross_entropy_with_logits(l,torch.tensor([.2]));loss.backward()
    assert l.grad.item()>.79
    assert (torch.sigmoid(l)*(1-torch.sigmoid(l))).item()<1e-5


def test_relative_ranking_does_not_fix_common_offset():
    a=torch.tensor(2.);b=torch.tensor(0.)
    torch.testing.assert_close(F.softplus(1-(a-b)),F.softplus(1-((a+50)-(b+50))))
    assert torch.sigmoid(a+50)>0.999 and torch.sigmoid(b+50)>0.999


def test_architecture_and_gate_parameter_scope_unchanged():
    m=Collaboration(15)
    assert sum(p.numel() for p in m.parameters())==100962
    assert sum(p.numel() for n,p in m.named_parameters() if n.startswith('trust.'))==545
    prior=read(PARENT/'code_freeze_pretest.json')['files']['code_collab_v1/model.py']
    assert file_sha(PILOT/'code_collab_v1/model.py')==prior


def test_pairs_are_schema_legal_no_target_copy_no_synthetic_feature():
    cat=read(RUN/'data/catalogue.json');aliases=read(NEW/'administrative_entity_aliases.json');R=len(cat['relations'])
    known={(x['h'],x['r']):set(x['tails']) for x in read(OUT/'data/train_positive_tails.json')}
    for p in read(OUT/'data/role_pairs_unfiltered.jsonl'):
        assert aliases[p['neighbor']]!=aliases[p['y']]
        assert p['negative_neighbor'] not in known[p['h'],p['r']] or p['negative_relation']!=p['r']
        for t,r in [(p['neighbor'],p['edge_relation']),(p['negative_neighbor'],p['negative_relation'])]:
            h=p['h']
            if r>=R:h,t=t,h;r-=R
            reg=cat['registry'][cat['relations'][r]]
            assert cat['entities'][h]['entity_type'] in reg['domain'] and cat['entities'][t]['entity_type'] in reg['range']
        assert p['features_identical'] and p['synthetic_proxy'] and not p['negative_is_proven_false']


def test_probe_queries_are_disjoint_from_pair_fit_queries():
    rows=read(OUT/'data/role_pairs_unfiltered.jsonl')
    fit={(r['h'],r['r']) for r in rows if r['split']=='fit'};probe={(r['h'],r['r']) for r in rows if r['split']=='probe'}
    assert not fit&probe


def test_exposure_reason_partition_and_historical_counts():
    counts=read(OUT/'data/candidate_exposure_summary.json')['counts'];s=read(RUN/'analysis/exposure_audit.json')['candidate_training_exposure']
    assert counts['used']==s['distinct_used']
    assert sum(v for k,v in counts.items() if k!='schema_illegal')==s['legal_pool']
    assert read(OUT/'data/candidate_exposure_summary.json')['quality_rejection_other_than_schema']==0


def test_utility_labels_are_only_declared_positive_negative_interventions():
    for seed in SEEDS:
        for r in read(OUT/f'data/utility_{seed}.jsonl'):
            assert r['strong_contrast']==(r['reference_u_plus']>1e-5 and r['reference_u_minus']<-1e-5)
            assert r['neighbor'] not in r['positive_tail_ids'] and r['negative_neighbor'] not in r['positive_tail_ids']
            assert not set(r['positive_tail_ids'])&set(r['competitor_ids'])


def test_fit_source_has_no_test_or_probe_selection():
    text=Path(__file__).with_name('train.py').read_text()
    for key in ['test_targets.jsonl','test_truth.json','/evaluation/']:assert key not in text
    assert 'probe_queries' in text and 'validation(model,data,graph,ev)' in text
