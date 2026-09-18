from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from scripts.run_rp3_head_ablations import materialize_config
from src.research_point_3.ablations import ablation_row, ablation_summary, seed_statistics
from src.research_point_3.contracts import DataSplit, DiagnosticRole
from src.research_point_3.losses import EvidenceControllerTargets, LossWeights, compute_evidence_controller_loss
from src.research_point_3.model import EvidenceControllerOutput
from tests.unit.test_research_point_3_training_contract import _trace, _record
from tests.unit.test_research_point_3_diagnostics import CONFIG

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "configs/research_point_3/head_ablation_v1.json").read_text())


def test_ablation_decoder_ignores_disabled_heads_but_keeps_availability():
    trace = _trace("T", DataSplit.TRAIN, scenario_id="S", evidence_id="E1", doc_id="MP001")
    trace = replace(trace, query=replace(trace.query, requested_role=DiagnosticRole.SYMPTOM),
                    candidate_evidence_ids=("E1", "E2"), availability_mask=(True, False),
                    evidence_decisions=trace.evidence_decisions + (replace(trace.evidence_decisions[0], evidence_id="E2", rank=2, selected=False),))
    records = {eid: _record(eid, DataSplit.TRAIN, "MP001") for eid in trace.candidate_evidence_ids}
    counts = np.zeros((1, 4, 4)); counts[:, :, 0] = 9
    logits = [np.array([[1., 100.]]), np.array([[-9., 9.]]), np.zeros((1, 4, 4)), counts, np.array([[0., 0., 9.]])]
    rank = ablation_row(trace, records, logits, CONFIG, "rank_only")
    assert rank["selected_ids"] == ["E1"] and rank["support_contract_enabled"] is False
    assert ablation_row(trace, records, logits, CONFIG, "rank_support")["selected_ids"] == []
    logits[1][0, 0] = 9
    assert ablation_row(trace, records, logits, CONFIG, "rank_support")["selected_ids"] == ["E1"]
    assert ablation_row(trace, records, logits, CONFIG, "full_local")["selected_ids"] == []
    summary = ablation_summary([rank], CONFIG, "rank_only")
    assert summary["support"] is None and summary["fields"] is None
    assert summary["deployment_allowed"] is False


@pytest.mark.parametrize("arm", ["A1", "A2", "A3"])
def test_inactive_heads_receive_no_gradient_even_for_interventions(arm):
    output = EvidenceControllerOutput(
        rank_logits=torch.randn(1, 2, requires_grad=True), support_logits=torch.randn(1, 2, requires_grad=True),
        field_state_logits=torch.randn(1, 4, 4, requires_grad=True), cardinality_logits=torch.randn(1, 4, 4, requires_grad=True),
        route_logits=torch.randn(1, 3, requires_grad=True), availability_mask=torch.ones(1, 2, dtype=torch.bool))
    targets = EvidenceControllerTargets(teacher_rank_scores=torch.tensor([[1., 0.]]), support_labels=torch.tensor([[1, 0]]),
        field_state_labels=torch.zeros(1, 4, dtype=torch.long), cardinality_labels=torch.ones(1, 4, dtype=torch.long),
        route_labels=torch.tensor([0]), route_action_costs=torch.tensor([[1., 9., 12.]]))
    weights = PROTOCOL["arms"][arm]["loss_weights"]
    loss = compute_evidence_controller_loss(output, targets, weights=LossWeights(**weights), intervention_pair=(output, targets))
    loss.total.backward()
    names = {"ranking": "rank_logits", "support": "support_logits", "field_state": "field_state_logits", "cardinality": "cardinality_logits", "route": "route_logits"}
    for task, name in names.items():
        gradient = getattr(output, name).grad
        if weights[task] == 0:
            assert gradient is None or torch.count_nonzero(gradient) == 0
        else:
            assert gradient is not None and torch.count_nonzero(gradient) > 0


def test_materialized_training_configs_detach_development_and_do_not_mutate_base():
    base = json.loads((ROOT / PROTOCOL["base_config"]).read_text())
    config = materialize_config(base, PROTOCOL, "A1", PROTOCOL["seeds"][0])
    assert not any(k.startswith("development") for k in config)
    assert config["training"]["seed"] == 7042027
    assert base["training"]["seed"] == 7042026
    assert config["model"] == base["model"]
    assert config["training"]["loss_weights"]["intervention"] == 0


def test_seed_intervals_are_not_pseudoreplicated_or_clipped():
    report = seed_statistics([0., 0., 1.])
    assert report["seeds"] == 3
    assert report["descriptive_t95_df2"][0] < 0
    with pytest.raises(ValueError):
        seed_statistics([0., 1., 0., 1.])
