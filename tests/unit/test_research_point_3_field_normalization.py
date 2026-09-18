from dataclasses import replace
import copy

import pytest
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from src.research_point_3.losses import field_cross_entropy, masked_cross_entropy, IGNORE_INDEX
from src.research_point_3.training import TrainingConfig, _run_epoch
from src.research_point_3.model import LightweightEvidenceController, EvidenceControllerConfig
from src.research_point_3.dataset import TensorizedTeacherDataset, TensorizationConfig, collate_teacher_batch
from src.research_point_3.contracts import DataSplit, DiagnosticRole
from src.research_point_3.field_audit import counted_rate, field_task_metrics
from tests.unit.test_research_point_3_training_contract import _trace, _record, _features


def test_balanced_groups_keep_total_scale_and_reweight_gradients():
    logits = torch.tensor([[[.3, -.2]] * 4], requires_grad=True)
    labels = torch.zeros(1, 4, dtype=torch.long)
    mask = torch.tensor([[True, False, False, False]])
    old = field_cross_entropy(logits, labels, mask)
    old_grad = torch.autograd.grad(old, logits, retain_graph=True)[0]
    new = field_cross_entropy(logits, labels, mask, normalization="requested_balanced")
    new_grad = torch.autograd.grad(new, logits)[0]
    assert torch.equal(old, masked_cross_entropy(logits, labels))
    assert torch.allclose(new, old)
    assert torch.allclose(new_grad[:, 0], 2 * old_grad[:, 0])
    assert torch.allclose(new_grad[:, 1:], old_grad[:, 1:] * (2 / 3))


def test_balanced_uses_both_groups_and_explicit_formula():
    logits = torch.tensor([[[3., 0.], [0., 2.], [1., 0.], [0., 1.]]])
    labels = torch.tensor([[0, 1, 0, 1]])
    mask = torch.tensor([[False, True, False, False]])
    ce = F.cross_entropy(logits.flatten(0, 1), labels.flatten(), reduction="none")
    assert field_cross_entropy(logits, labels, mask, normalization="requested_balanced") == pytest.approx(float(.5 * ce[1] + .5 * ce[[0, 2, 3]].mean()))
    changed = labels.clone(); changed[0, 0] = 1
    assert field_cross_entropy(logits, changed, mask, normalization="requested_balanced") != field_cross_entropy(logits, labels, mask, normalization="requested_balanced")


@pytest.mark.parametrize("mask", [None, torch.zeros(1, 4, dtype=torch.bool), torch.ones(1, 4, dtype=torch.bool), torch.ones(1, 4)])
def test_balanced_rejects_missing_or_non_single_role_mask(mask):
    with pytest.raises(ValueError):
        field_cross_entropy(torch.zeros(1, 4, 4), torch.zeros(1, 4, dtype=torch.long), mask, normalization="requested_balanced")


def test_balanced_rejects_ignored_labels_and_unknown_mode():
    labels = torch.tensor([[0, IGNORE_INDEX, 0, 0]])
    mask = torch.tensor([[True, False, False, False]])
    with pytest.raises(ValueError, match="complete labels"):
        field_cross_entropy(torch.zeros(1, 4, 4), labels, mask, normalization="requested_balanced")
    with pytest.raises(ValueError):
        TrainingConfig(field_loss_normalization="requested_only")


def test_epoch_audit_does_not_change_rng_loss_or_optimizer_updates():
    torch.set_num_threads(1)
    trace = _trace("T1", DataSplit.TRAIN, scenario_id="S1", evidence_id="E1", doc_id="MP001")
    trace = replace(trace, query=replace(trace.query, requested_role=DiagnosticRole.SYMPTOM))
    dataset = TensorizedTeacherDataset((trace,), (_record("E1", DataSplit.TRAIN, "MP001"),),
                                      _features(("T1",), ("E1",)), TensorizationConfig(max_candidates=2))
    assert dataset[0]["requested_field_mask"].tolist() == [True, False, False, False]
    model = LightweightEvidenceController(EvidenceControllerConfig(query_dim=2, evidence_dim=3, hidden_dim=8, dropout=.1))
    runs = []
    for record in [False, True]:
        clone = copy.deepcopy(model)
        loader = DataLoader(dataset, batch_size=1, collate_fn=collate_teacher_batch)
        optimizer = torch.optim.AdamW(clone.parameters(), lr=3e-4)
        torch.manual_seed(17)
        metrics = _run_epoch(clone, loader, TrainingConfig(field_loss_normalization="requested_balanced", record_field_diagnostics=record), torch.device("cpu"), optimizer)
        runs.append((clone.state_dict(), metrics, torch.get_rng_state()))
    assert runs[0][1]["total"] == runs[1][1]["total"]
    assert torch.equal(runs[0][2], runs[1][2])
    assert all(torch.equal(value, runs[1][0][name]) for name, value in runs[0][0].items())
    assert runs[1][1]["field_diagnostics"]["used_for_model_selection"] is False


def test_empty_risk_reports_denominators_and_separates_no_available():
    row = {"scenario_id": "s", "requested_index": 0, "target_cardinalities": [0]*4,
           "raw_cardinalities": [1, 0, 0, 0], "decoded_cardinalities": [1, 0, 0, 0],
           "teacher_selected_ids": [], "selected_ids": ["e"], "available_ids": ["e"],
           "pointer": {"precision": 0., "recall": 0., "f1": 0.},
           "nonempty_exact_success": False, "proposal_contract_passed": True}
    result = field_task_metrics([row])
    assert result["teacher_empty_false_fill"] == counted_rate(1, 1)
    assert result["no_available_false_fill"] == counted_rate(0, 0)
    assert result["nonempty_target_raw_zero"]["rate"] is None
