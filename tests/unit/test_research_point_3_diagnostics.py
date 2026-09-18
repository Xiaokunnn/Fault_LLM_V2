"""Regression tests for diagnostic metric semantics and fail-closed boundaries."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.research_point_3.artifacts import stable_sha256, file_sha256
from src.research_point_3.contracts import DataSplit, DiagnosticRole, SupportVerdict
from src.research_point_3.diagnostics import binary_summary, prediction_row, risk_coverage, routing_summary, summarize
from src.research_point_3.model import CARD_FIELD_STATES
from scripts.diagnose_rp3_lec import validate_bindings, validate_protocol, run
from tests.unit.test_research_point_3_training_contract import _trace, _record


CONFIG = json.loads((Path(__file__).resolve().parents[2] / "configs/research_point_3/diagnostics_v1.json").read_text())


def test_ap_and_risk_curve_do_not_break_ties_using_labels():
    metric = binary_summary([.5, .5], [1, 0])
    assert metric["auprc_average_precision"] == .5
    assert metric["ece"] == 0
    assert binary_summary([.5, .5], [0, 1]) == metric
    rows = [{"eligible": True, "local_confidence": .8, "exact_set": exact} for exact in [True, False]]
    curve = risk_coverage(rows)
    assert len(curve["curve"]) == 1
    assert curve["curve"][0]["risk"] == .5
    assert curve == risk_coverage(rows[::-1])
    assert binary_summary([.9], [0])["auprc_average_precision"] is None
    assert binary_summary([], [])["f1"] is None


def test_no_answer_risk_is_undefined_not_zero():
    row = {"eligible": False, "exact_set": True, "teacher_selected_ids": [],
           "decoded_action": "abstain", "local_confidence": 0, "local_normalized_entropy": 1}
    summary = routing_summary([row], "R2_always_abstain", CONFIG)
    assert summary["local_teacher_disagreement"] is None
    assert summary["mean_route_regret"] == 0
    assert summary["teacher_call_avoidance_fraction"] == 1
    assert risk_coverage([row])["aurc_reachable"] is None


def test_route_baselines_use_common_declared_costs_and_no_teacher_calls():
    row = {"eligible": True, "exact_set": False, "teacher_selected_ids": ["E1"],
           "decoded_action": "fallback", "local_confidence": .6, "local_normalized_entropy": .9}
    local = routing_summary([row], "R0_always_local", CONFIG)
    teacher = routing_summary([row], "R1_always_teacher", CONFIG)
    assert local["mean_declared_utility_cost"] == 51
    assert local["mean_route_regret"] == 42
    assert teacher["mean_declared_utility_cost"] == 9
    assert teacher["replayed_final_answer_coverage"] == 1
    assert teacher["replayed_teacher_calls"] == 1 and teacher["actual_teacher_calls"] == 0
    assert routing_summary([row], "R3_confidence", CONFIG)["actions"]["fallback"] == 1


def test_requested_slot_metrics_expose_zero_cardinality_and_support_mask():
    trace = _trace("T1", DataSplit.TRAIN, scenario_id="S1", evidence_id="E1", doc_id="MP001")
    decisions = trace.evidence_decisions + (
        replace(trace.evidence_decisions[0], evidence_id="E2", rank=2, selected=False, support=SupportVerdict.NOT_ASSESSED),
        replace(trace.evidence_decisions[0], evidence_id="E3", rank=3, selected=False),
    )
    trace = replace(trace, query=replace(trace.query, requested_role=DiagnosticRole.SYMPTOM),
                    candidate_evidence_ids=("E1", "E2", "E3"), availability_mask=(True, True, False), evidence_decisions=decisions)
    records = {eid: _record(eid, DataSplit.TRAIN, "MP001") for eid in trace.candidate_evidence_ids}
    fields = np.zeros((1, 4, 4)); fields[:, :, CARD_FIELD_STATES.index("supported")] = 4
    counts = np.zeros((1, 4, 4)); counts[:, :, 0] = 4
    logits = [np.array([[3., 2., 100., 99.]]), np.full((1, 4), 8.), fields, counts, np.array([[8., 0., 0.]])]
    row = prediction_row(trace, records, logits, CONFIG)
    assert row["support_labels"] == [1]
    assert row["support_not_assessed_available"] == 1
    assert row["selected_ids"] == [] and not row["eligible"]
    m = summarize([row], CONFIG)
    assert m["fields"]["raw_all_slots"]["cardinality_accuracy"] == .75
    assert m["fields"]["raw_requested_slot"]["cardinality_accuracy"] == 0
    assert m["fields"]["raw_requested_slot"]["nonempty_target_predicted_zero_count"] == 1
    assert m["support"]["count"] == 1
    assert m["nonempty_exact_success"] == 0


def test_export_binding_rejects_wrong_model_or_training_config(tmp_path):
    fp32 = tmp_path / "fp32.onnx"; fp32.write_bytes(b"fp32 fixture")
    int8 = tmp_path / "controller.int8.onnx"; int8.write_bytes(b"int8 fixture")
    graph = {"id": "teacher", "sha256": "a" * 64}
    export = {"input_fingerprint": "build", "onnx_file": fp32.name, "onnx_sha256": file_sha256(fp32),
              "runtime_binding": {"memory": {"logical_sha256": "memory"}, "teacher_graph": graph}}
    quant = {"fp32_sha256": file_sha256(fp32), "int8_sha256": file_sha256(int8)}
    for name, value in [("onnx_export_manifest.json", export), ("quantization_manifest.json", quant)]:
        (tmp_path / name).write_text(json.dumps({**value, "logical_sha256": stable_sha256(value)}))
    prepared = SimpleNamespace(input_fingerprint="build", memory_manifest={"logical_sha256": "memory", "teacher_graph": graph})
    validate_bindings(tmp_path, prepared)
    prepared.input_fingerprint = "other"
    with pytest.raises(ValueError, match="training inputs"):
        validate_bindings(tmp_path, prepared)
    prepared.input_fingerprint = "build"
    int8.write_bytes(b"corrupt fixture")
    with pytest.raises(ValueError, match="INT8"):
        validate_bindings(tmp_path, prepared)


def test_no_overwrite_or_external_protocol(tmp_path):
    with pytest.raises(FileExistsError):
        run("does-not-exist", "does-not-exist", tmp_path, "does-not-exist")
    with pytest.raises(ValueError, match="build inputs only"):
        validate_protocol({**CONFIG, "external_inputs": "allowed"})
