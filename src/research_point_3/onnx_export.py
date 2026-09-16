"""ONNX and representative-data export for RP3 edge deployment.

The functions in this module export an unquantized controller and an optional
representative calibration-input bundle.  They do **not** claim that INT8
quantization or post-quantization threshold calibration has been completed.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifacts import (
    canonical_json_bytes,
    file_sha256,
    normalized_text_sha256,
    stable_sha256,
)
from .contracts import ContractError
from .dataset import TensorizedTeacherDataset, collate_teacher_batch
from .model import LightweightEvidenceController, require_torch
from .training import TRAINING_MANIFEST_SCHEMA, load_controller_checkpoint

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


ONNX_EXPORT_SCHEMA = "rp3_lec_onnx_export_v1"
INT8_CALIBRATION_SCHEMA = "rp3_lec_int8_calibration_inputs_v1"
ONNX_INSTALL_HINT = (
    "ONNX export requires the optional 'onnx' package in addition to PyTorch "
    "(and onnxscript when required by the installed PyTorch exporter). Install "
    "compatible torch/onnx exporter packages on the model-capable machine."
)
NUMPY_INSTALL_HINT = (
    "INT8 calibration-input export requires NumPy. Install numpy on the "
    "model-capable deployment preparation machine."
)
MAX_CONTROLLER_PARAMETERS = 50_000_000


def _read_verified_memory_manifest(path: str | Path) -> tuple[dict[str, Any], Path]:
    """Load the exact compact-memory manifest bound to a deployment export."""

    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("artifact_type") != (
        "rp3_compact_evidence_memory"
    ):
        raise ContractError("manifest is not an RP3 compact evidence-memory manifest")
    data_file = Path(str(manifest.get("data_file", "")))
    if data_file.is_absolute() or ".." in data_file.parts:
        raise ContractError("compact evidence-memory data path must stay in its bundle")
    data_path = manifest_path.parent / data_file
    if not data_path.is_file() or normalized_text_sha256(data_path) != manifest.get(
        "data_sha256"
    ):
        raise ContractError("compact evidence-memory data SHA-256 mismatch")
    logical = str(manifest.get("logical_sha256", "")).lower()
    if len(logical) != 64 or any(c not in "0123456789abcdef" for c in logical):
        raise ContractError("compact evidence-memory logical SHA-256 is invalid")
    memory_id = str(manifest.get("memory_id", "")).strip()
    if not memory_id:
        raise ContractError("compact evidence-memory manifest has no memory_id")
    graph = manifest.get("teacher_graph")
    if not isinstance(graph, Mapping) or not str(graph.get("id", "")).strip():
        raise ContractError("compact evidence-memory manifest has no teacher graph binding")
    return manifest, manifest_path


def _read_verified_training_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != TRAINING_MANIFEST_SCHEMA:
        raise ContractError("manifest is not an RP3 LEC training manifest")
    expected = str(manifest.get("logical_sha256", "")).lower()
    unhashed = {key: value for key, value in manifest.items() if key != "logical_sha256"}
    if stable_sha256(unhashed) != expected:
        raise ContractError("training manifest logical SHA-256 mismatch")
    checkpoint_path = manifest_path.parent / str(manifest.get("checkpoint_file", ""))
    if not checkpoint_path.is_file():
        raise ContractError("training checkpoint referenced by manifest is missing")
    if file_sha256(checkpoint_path) != manifest.get("checkpoint_sha256"):
        raise ContractError("training checkpoint SHA-256 mismatch")
    manifest["_checkpoint_path"] = checkpoint_path
    manifest["_manifest_path"] = manifest_path
    return manifest


if torch is not None:

    class _OnnxControllerWrapper(torch.nn.Module):
        def __init__(self, controller: LightweightEvidenceController) -> None:
            super().__init__()
            self.controller = controller

        def forward(
            self,
            query_features: "torch.Tensor",
            candidate_features: "torch.Tensor",
            availability_mask: "torch.Tensor",
            selection_budget: "torch.Tensor",
        ) -> tuple["torch.Tensor", ...]:
            output = self.controller(
                query_features,
                candidate_features,
                availability_mask,
                selection_budget,
            )
            # Re-apply the two total-removal constraints with pure tensor ops.
            # This preserves fail-closed semantics even when a legacy tracer
            # specializes Python control flow in the eager model.
            no_evidence = ~availability_mask.to(dtype=torch.bool).any(
                dim=1, keepdim=True
            )
            floor = torch.finfo(output.route_logits.dtype).min
            route_class = torch.arange(
                output.route_logits.shape[-1], device=output.route_logits.device
            ).view(1, -1)
            route_allowed = ~(no_evidence & (route_class == 0))
            route_logits = torch.where(
                route_allowed,
                output.route_logits,
                torch.full_like(output.route_logits, floor),
            )
            state_class = torch.arange(
                output.field_state_logits.shape[-1],
                device=output.field_state_logits.device,
            ).view(1, 1, -1)
            disallowed_state = (state_class == 0) | (state_class == 3)
            field_allowed = ~(no_evidence.unsqueeze(-1) & disallowed_state)
            field_state_logits = torch.where(
                field_allowed,
                output.field_state_logits,
                torch.full_like(output.field_state_logits, floor),
            )
            return (
                output.rank_logits,
                output.support_logits,
                field_state_logits,
                output.cardinality_logits,
                route_logits,
            )


def export_controller_onnx(
    *,
    training_manifest_path: str | Path,
    memory_manifest_path: str | Path,
    output_dir: str | Path,
    max_candidates: int,
    opset_version: int = 17,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Export dynamic-batch/fixed-candidate-width FP32 ONNX and verify it."""

    require_torch()
    try:
        import onnx
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(ONNX_INSTALL_HINT) from exc
    if max_candidates < 1:
        raise ValueError("max_candidates must be >= 1")
    if opset_version < 17:
        raise ValueError("RP3 ONNX export requires opset_version >= 17")
    training = _read_verified_training_manifest(training_manifest_path)
    memory_manifest, verified_memory_manifest_path = _read_verified_memory_manifest(
        memory_manifest_path
    )
    if memory_manifest.get("logical_sha256") != training.get("memory_bundle_sha256"):
        raise ContractError(
            "deployment memory does not match the memory used by the trained controller"
        )
    if memory_manifest.get("teacher_graph") != training.get("teacher_graph"):
        raise ContractError(
            "deployment memory and trained controller bind different teacher graphs"
        )
    input_fingerprint = str(training.get("input_fingerprint", ""))
    controller, checkpoint = load_controller_checkpoint(
        training["_checkpoint_path"],
        expected_input_fingerprint=input_fingerprint,
        map_location="cpu",
    )
    controller.eval()
    if controller.parameter_count() >= MAX_CONTROLLER_PARAMETERS:
        raise ContractError("refusing to export an RP3 controller with >=50M parameters")
    config = controller.config
    controller_version = (
        "LEC_RP3_" + str(training.get("checkpoint_sha256", ""))[:16]
    )
    output = Path(output_dir)
    onnx_path = output / "rp3_lec_fp32.onnx"
    manifest_path = output / "onnx_export_manifest.json"
    if not overwrite and (onnx_path.exists() or manifest_path.exists()):
        raise RuntimeError("refusing to overwrite an existing RP3 ONNX export")
    output.mkdir(parents=True, exist_ok=True)
    wrapper = _OnnxControllerWrapper(controller)
    inputs = (
        torch.zeros(1, config.query_dim, dtype=torch.float32),
        torch.zeros(1, max_candidates, config.evidence_dim, dtype=torch.float32),
        torch.ones(1, max_candidates, dtype=torch.bool),
        torch.full((1,), min(config.max_cardinality, max_candidates), dtype=torch.long),
    )
    input_names = [
        "query_features",
        "candidate_features",
        "availability_mask",
        "selection_budget",
    ]
    output_names = [
        "rank_logits",
        "support_logits",
        "field_state_logits",
        "cardinality_logits",
        "route_logits",
    ]
    dynamic_axes = {
        **{name: {0: "batch"} for name in input_names},
        **{name: {0: "batch"} for name in output_names},
    }
    temporary = onnx_path.with_suffix(".onnx.tmp")
    torch.onnx.export(
        wrapper,
        inputs,
        temporary,
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=input_names,
        output_names=output_names,
        dynamic_axes=dynamic_axes,
    )
    model_proto = onnx.load(str(temporary))
    onnx.checker.check_model(model_proto, full_check=True)
    temporary.replace(onnx_path)
    manifest = {
        "schema": ONNX_EXPORT_SCHEMA,
        "status": "exported_fp32_unquantized",
        "source_training_manifest_sha256": str(training.get("logical_sha256")),
        "source_checkpoint_sha256": str(training.get("checkpoint_sha256")),
        "source_training_manifest_file_sha256": file_sha256(
            training["_manifest_path"]
        ),
        "input_fingerprint": input_fingerprint,
        "controller_version": controller_version,
        "checkpoint_epoch": int(checkpoint.get("epoch", 0)),
        "opset_version": int(opset_version),
        "onnx_file": onnx_path.name,
        "onnx_sha256": file_sha256(onnx_path),
        "onnx_checker_passed": True,
        "inputs": {
            "query_features": ["batch", config.query_dim],
            "candidate_features": ["batch", max_candidates, config.evidence_dim],
            "availability_mask": ["batch", max_candidates],
            "selection_budget": ["batch"],
        },
        "outputs": output_names,
        "dynamic_batch": True,
        "fixed_candidate_width": max_candidates,
        "runtime_binding": {
            "teacher_graph": dict(memory_manifest["teacher_graph"]),
            "memory": {
                "id": str(memory_manifest["memory_id"]),
                "logical_sha256": str(memory_manifest["logical_sha256"]),
                "manifest_file_sha256": file_sha256(
                    verified_memory_manifest_path
                ),
            },
            "feature_encoder_manifest": dict(
                training.get("feature_encoder_manifest", {})
            ),
            "feature_encoder_manifest_sha256": stable_sha256(
                training.get("feature_encoder_manifest", {})
            ),
            "development_calibration_source": {
                "corpus": "MP008",
                "input_fingerprint": training.get("development_set", {}).get(
                    "input_fingerprint"
                ),
                "trace_bundle_sha256": training.get("development_set", {}).get(
                    "trace_bundle_sha256"
                ),
                "memory_bundle_sha256": training.get("development_set", {}).get(
                    "memory_bundle_sha256"
                ),
                "feature_bundle_sha256": training.get("development_set", {}).get(
                    "feature_bundle_sha256"
                ),
                "used_for_gradients": False,
                "used_for_early_stopping_or_model_selection": False,
            },
        },
        "parameter_report": controller.parameter_report(),
        "quantization": {
            "completed": False,
            "target": "INT8_post_training_candidate",
            "calibration_inputs_required": True,
            "post_quantization_threshold_recalibration_required": True,
            "accuracy_and_contract_regression_required": True,
        },
        "deployment_claim_boundary": (
            "This artifact is a verified FP32 ONNX graph only; it is not an INT8 "
            "model and contains no target-hardware latency, memory, energy, or "
            "thermal measurements."
        ),
    }
    manifest["logical_sha256"] = stable_sha256(manifest)
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    return manifest


def build_int8_calibration_input_bundle(
    dataset: TensorizedTeacherDataset,
    *,
    output_dir: str | Path,
    source_input_fingerprint: str,
    max_samples: int = 128,
    batch_size: int = 1,
    seed: int = 20260813,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write deterministic representative inputs, without quantizing the model."""

    require_torch()
    if np is None:  # pragma: no cover
        raise RuntimeError(NUMPY_INSTALL_HINT)
    if max_samples < 1 or batch_size < 1:
        raise ValueError("max_samples and batch_size must be >= 1")
    if not source_input_fingerprint:
        raise ContractError("source_input_fingerprint must be non-empty")
    sample_count = min(len(dataset), max_samples)
    indices = list(range(len(dataset)))
    random.Random(int(seed)).shuffle(indices)
    indices = sorted(indices[:sample_count])
    rows = [dataset[index] for index in indices]
    batch = collate_teacher_batch(rows)
    output = Path(output_dir)
    data_path = output / "int8_calibration_inputs.npz"
    manifest_path = output / "int8_calibration_manifest.json"
    if not overwrite and (data_path.exists() or manifest_path.exists()):
        raise RuntimeError("refusing to overwrite existing INT8 calibration inputs")
    output.mkdir(parents=True, exist_ok=True)
    temporary = data_path.with_suffix(".npz.tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(
            handle,
            query_features=batch["query_features"].cpu().numpy(),
            candidate_features=batch["candidate_features"].cpu().numpy(),
            availability_mask=batch["availability_mask"].cpu().numpy(),
            selection_budget=batch["selection_budget"].cpu().numpy(),
        )
    temporary.replace(data_path)
    manifest = {
        "schema": INT8_CALIBRATION_SCHEMA,
        "status": "representative_inputs_ready_quantization_not_run",
        "source_input_fingerprint": source_input_fingerprint,
        "sample_count": sample_count,
        "batch_size_for_reader": batch_size,
        "seed": int(seed),
        "selected_dataset_indices": indices,
        "data_file": data_path.name,
        "data_sha256": file_sha256(data_path),
        "input_names": [
            "query_features",
            "candidate_features",
            "availability_mask",
            "selection_budget",
        ],
        "quantization_completed": False,
        "post_quantization_threshold_recalibration_required": True,
    }
    manifest["logical_sha256"] = stable_sha256(manifest)
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    return manifest


class NumpyInt8CalibrationDataReader:
    """Duck-typed ONNX Runtime calibration reader over a verified NPZ bundle."""

    def __init__(self, manifest_path: str | Path) -> None:
        if np is None:  # pragma: no cover
            raise RuntimeError(NUMPY_INSTALL_HINT)
        path = Path(manifest_path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("schema") != INT8_CALIBRATION_SCHEMA:
            raise ContractError("manifest is not an RP3 INT8 calibration-input bundle")
        expected = str(manifest.get("logical_sha256", ""))
        if stable_sha256(
            {key: value for key, value in manifest.items() if key != "logical_sha256"}
        ) != expected:
            raise ContractError("INT8 calibration manifest logical SHA-256 mismatch")
        data_path = path.parent / str(manifest.get("data_file", ""))
        if file_sha256(data_path) != manifest.get("data_sha256"):
            raise ContractError("INT8 calibration input SHA-256 mismatch")
        archive = np.load(data_path, allow_pickle=False)
        self._arrays = {name: archive[name] for name in manifest["input_names"]}
        self._sample_count = int(manifest["sample_count"])
        self._batch_size = int(manifest["batch_size_for_reader"])
        self._offset = 0

    def get_next(self) -> dict[str, Any] | None:
        if self._offset >= self._sample_count:
            return None
        end = min(self._offset + self._batch_size, self._sample_count)
        result = {
            name: values[self._offset : end]
            for name, values in self._arrays.items()
        }
        self._offset = end
        return result

    def rewind(self) -> None:
        self._offset = 0


__all__ = [
    "INT8_CALIBRATION_SCHEMA",
    "ONNX_EXPORT_SCHEMA",
    "NumpyInt8CalibrationDataReader",
    "build_int8_calibration_input_bundle",
    "export_controller_onnx",
]
