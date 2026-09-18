"""Observable set interventions, paired initialization and old-model compatibility."""
from dataclasses import asdict
import pytest
torch = pytest.importorskip('torch')
from src.research_point_3.model import EvidenceControllerConfig, LightweightEvidenceController
from src.research_point_3.set_support import CandidateContextSupport
from src.research_point_3.training import CHECKPOINT_SCHEMA, load_controller_checkpoint


def model(mode):
    torch.manual_seed(713)
    return LightweightEvidenceController(EvidenceControllerConfig(4, 3, hidden_dim=12, dropout=.1, support_context=mode))


def inputs():
    generator = torch.Generator().manual_seed(85)
    return (torch.randn(2, 4, generator=generator), torch.randn(2, 4, 3, generator=generator),
            torch.tensor([[True, True, False, True], [False, False, False, False]]), torch.tensor([3, 3]))


def activate(module):
    with torch.no_grad():
        module.residual[-1].weight.copy_(torch.arange(1., 1+module.residual[-1].weight.numel()).view_as(module.residual[-1].weight))


def test_paired_initialization_capacity_outputs_and_rng():
    old = model('pointwise'); old_rng = torch.get_rng_state()
    local = model('local_residual'); local_rng = torch.get_rng_state()
    contextual = model('set_residual'); contextual_rng = torch.get_rng_state()
    assert torch.equal(old_rng, local_rng) and torch.equal(old_rng, contextual_rng)
    assert contextual.parameter_count() == local.parameter_count() > old.parameter_count()
    for key, value in old.state_dict().items():
        assert torch.equal(value, local.state_dict()[key]) and torch.equal(value, contextual.state_dict()[key])
    assert all(torch.equal(value, contextual.state_dict()[key]) for key, value in local.state_dict().items())
    args = inputs()
    for training in (False, True):
        outputs = []
        for net in (old, local, contextual):
            net.train(training); torch.manual_seed(190); outputs.append(net(*args))
        for key in ('rank_logits', 'support_logits', 'cardinality_logits', 'field_state_logits', 'route_logits'):
            assert torch.equal(getattr(outputs[0], key), getattr(outputs[1], key))
            assert torch.equal(getattr(outputs[0], key), getattr(outputs[2], key))


@pytest.mark.parametrize('mode', ['local_residual', 'set_residual'])
def test_permutation_equivariance_masked_input_independence_and_empty(mode):
    net = model(mode).eval(); activate(net.support_residual)
    q, e, mask, budget = inputs(); permutation = torch.tensor([3, 0, 2, 1])
    out = net(q, e, mask, budget); perm = net(q, e[:, permutation], mask[:, permutation], budget)
    for key in ('rank_logits', 'support_logits'):
        torch.testing.assert_close(getattr(perm, key), getattr(out, key)[:, permutation], atol=2e-6, rtol=2e-6)
    for key in ('cardinality_logits', 'field_state_logits', 'route_logits'):
        torch.testing.assert_close(getattr(perm, key), getattr(out, key), atol=2e-6, rtol=2e-6)
    changed = e.clone(); changed[~mask] = 1000.
    altered = net(q, changed, mask, budget)
    torch.testing.assert_close(altered.support_logits, out.support_logits, atol=0, rtol=0)
    assert torch.isfinite(out.support_logits).all()
    assert (torch.sigmoid(out.support_logits)[~mask] == 0).all()
    assert (out.cardinality_logits[1].argmax(-1) == 0).all()
    assert out.route_logits[1].argmax() != 0


def test_cross_candidate_sensitivity_and_gradient_are_only_in_set_arm():
    torch.manual_seed(808)
    h = torch.randn(1, 4, 12, requires_grad=True); mask = torch.tensor([[True, True, True, False]])
    local = CandidateContextSupport(12, 'local_residual'); contextual = CandidateContextSupport(12, 'set_residual')
    contextual.load_state_dict(local.state_dict()); activate(local); activate(contextual)
    local_grad = torch.autograd.grad(local(h, mask)[0, 0], h)[0]
    set_grad = torch.autograd.grad(contextual(h, mask)[0, 0], h)[0]
    assert local_grad[0, 1:].abs().sum() == 0
    assert set_grad[0, 1:3].abs().sum() > 1e-6 and set_grad[0, 3].abs().sum() == 0
    reduced = mask.clone(); reduced[0, 1] = False
    assert local(h, mask)[0, 0] == local(h, reduced)[0, 0]
    assert not torch.isclose(contextual(h, mask)[0, 0], contextual(h, reduced)[0, 0], atol=1e-6)


def test_singleton_matches_local_context_and_pool_removal_identity():
    h = torch.randn(1, 4, 12)
    local = CandidateContextSupport(12, 'local_residual'); contextual = CandidateContextSupport(12, 'set_residual')
    singleton = torch.tensor([[True, False, False, False]])
    assert torch.equal(local.context_features(h, singleton)[0, 0], contextual.context_features(h, singleton)[0, 0])
    before = contextual.context_features(h, torch.tensor([[True, True, True, False]]))[0, 0, 12:24]
    after = contextual.context_features(h, torch.tensor([[True, False, True, False]]))[0, 0, 12:24]
    torch.testing.assert_close(after-before, (before-h[0, 1])/2)


def test_old_checkpoint_loads_and_new_mode_roundtrips(tmp_path):
    for mode in ('pointwise', 'local_residual', 'set_residual'):
        net = model(mode); config = asdict(net.config)
        if mode == 'pointwise': config.pop('support_context')
        path = tmp_path/(mode+'.pt')
        torch.save({'schema': CHECKPOINT_SCHEMA, 'input_fingerprint': 'synthetic',
                    'model_config': config, 'model_state_dict': net.state_dict()}, path)
        loaded, _ = load_controller_checkpoint(path, expected_input_fingerprint='synthetic')
        assert loaded.config.support_context == mode
        assert all(torch.equal(v, loaded.state_dict()[k]) for k, v in net.state_dict().items())
    with pytest.raises(ValueError): EvidenceControllerConfig(4, 3, support_context='bad')
