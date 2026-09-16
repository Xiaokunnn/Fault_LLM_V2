"""Synthetic CPU integration only: never produces scientific experiment assets."""
from dataclasses import replace
import json
import sys

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")
pytest.importorskip("onnx")
ort = pytest.importorskip("onnxruntime")

from tests.unit.test_research_point_3_training_contract import _trace, _record, _features, _manifests
from src.research_point_3.artifacts import write_compact_evidence_memory_bundle, stable_sha256
from src.research_point_3.contracts import DataSplit
from src.research_point_3.dataset import PreparedTrainingData, TensorizedTeacherDataset, TensorizationConfig
from src.research_point_3.model import EvidenceControllerConfig
from src.research_point_3.training import TrainingConfig, train_evidence_controller
from src.research_point_3.onnx_export import export_controller_onnx, build_int8_calibration_input_bundle
from src.research_point_3.calibration import write_calibration_manifest_from_export
from src.research_point_3.onnx_runtime import OnnxEvidenceController


def test_synthetic_train_export_quantize_and_runtime_binding(tmp_path, monkeypatch):
    torch.set_num_threads(1)
    records = (
        _record("E1", DataSplit.TRAIN, "MP001"),
        replace(_record("E2", DataSplit.VALIDATION, "MP002"), memory_index=1),
    )
    dev_records = (_record("D1", DataSplit.DEVELOPMENT, "MP008"),)
    train = _trace("T1", DataSplit.TRAIN, scenario_id="S1", evidence_id="E1", doc_id="MP001")
    valid = _trace("T2", DataSplit.VALIDATION, scenario_id="S2", evidence_id="E2", doc_id="MP002")
    dev = _trace("D1", DataSplit.DEVELOPMENT, scenario_id="MP008:S3", evidence_id="D1", doc_id="MP008")
    features = _features(("T1", "T2"), ("E1", "E2"))
    dev_features = _features(("D1",), ("D1",))
    tensor = TensorizationConfig(max_candidates=4, max_cardinality=3)
    trace_manifest, _, freeze = _manifests()
    memory = write_compact_evidence_memory_bundle(
        tmp_path / "memory", records, memory_id="SYNTHETIC_TEST_ONLY",
        teacher_graph_id="TeacherGraph_RP3_v1", teacher_graph_sha256="a" * 64,
        teacher_system_identity_sha256="c" * 64,
    )
    dataset = lambda traces, recs, feat: TensorizedTeacherDataset(traces, recs, feat, tensor)
    prepared = PreparedTrainingData(
        train_dataset=dataset((train,), records, features),
        validation_dataset=dataset((valid,), records, features),
        development_dataset=dataset((dev,), dev_records, dev_features),
        trace_manifest=trace_manifest, memory_manifest=memory,
        development_trace_manifest={"logical_sha256": "d" * 64},
        development_memory_manifest={"logical_sha256": "e" * 64},
        teacher_freeze_manifest=freeze, feature_store=features,
        development_feature_store=dev_features,
        input_fingerprint="SYNTHETIC_BUILD_ONLY", development_fingerprint="SYNTHETIC_MP008_ONLY",
    )
    trained = train_evidence_controller(
        prepared, model_config=EvidenceControllerConfig(query_dim=2, evidence_dim=3, hidden_dim=8, dropout=0),
        training_config=TrainingConfig(epochs=2, batch_size=1, device="cpu"), output_dir=tmp_path / "train",
    )
    assert trained["status"] == "trained_unquantized"
    exported = tmp_path / "onnx"
    export = export_controller_onnx(
        training_manifest_path=tmp_path / "train/training_manifest.json",
        memory_manifest_path=tmp_path / "memory/manifest.json", output_dir=exported, max_candidates=4,
    )
    build_int8_calibration_input_bundle(prepared.development_dataset, output_dir=exported,
                                      source_input_fingerprint=prepared.development_fingerprint)
    from scripts.quantize_rp3_onnx import main as quantize
    monkeypatch.setattr(sys, "argv", ["quantize_rp3_onnx.py", "--export-dir", str(exported)])
    quantize()
    quantization = json.loads((exported / "quantization_manifest.json").read_text())
    assert quantization["qdq_nodes"] > 0
    assert quantization["accuracy_passed"] is False
    # Dynamic batch and total evidence removal must work even though tracing
    # and calibration observed batch size one and a nonempty candidate pool.
    session = ort.InferenceSession(str(exported / "controller.int8.onnx"), providers=["CPUExecutionProvider"])
    feed = {"query_features": np.zeros((2, 2), dtype=np.float32),
            "candidate_features": np.zeros((2, 4, 3), dtype=np.float32),
            "availability_mask": np.zeros((2, 4), dtype=np.bool_),
            "selection_budget": np.array([0, 3], dtype=np.int64)}
    outputs = session.run(None, feed)
    assert all(np.isfinite(x).all() for x in outputs)
    assert (np.argmax(outputs[4], axis=-1) != 0).all(), "empty evidence must not permit answer"
    assert (outputs[0] < -1e30).all()
    # Fixed dummy thresholds below ONLY exercise artifact binding, not fitting.
    write_calibration_manifest_from_export(
        exported / "calibration_manifest.json", support_threshold=.5, minimum_route_confidence=.5,
        quantized_model_path=exported / "controller.int8.onnx",
        onnx_export_manifest_path=exported / "onnx_export_manifest.json",
        metrics={"synthetic_test_only": True, "thresholds_fitted": False},
    )
    class SyntheticProvider:
        feature_encoder_manifest_sha256 = stable_sha256(features.encoder_manifest)

        def features_for(self, **kwargs):
            return [1., 2.], [[.1, .2, .3] for _ in kwargs["candidates"]]

    controller = OnnxEvidenceController(
        onnx_manifest_path=exported / "onnx_export_manifest.json",
        quantized_model_path=exported / "controller.int8.onnx",
        calibration_manifest_path=exported / "calibration_manifest.json",
        memory_manifest=memory, feature_provider=SyntheticProvider(), providers=["CPUExecutionProvider"],
    )
    assert controller.max_candidates == 4
    assert export["quantization"]["completed"] is False
