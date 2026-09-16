"""Version-bound MP008 calibration artifacts for RP3 edge inference.

Calibration is deliberately separated from training and ONNX export.  The
artifact produced on a model-capable machine binds thresholds to the exact
quantized model bytes, compact evidence memory, teacher graph, controller
version, and MP008 development bundle.  Runtime code therefore never accepts
ad-hoc numeric thresholds from a caller.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .artifacts import canonical_json_bytes, file_sha256, stable_sha256
from .contracts import CONTRACT_VERSION, ContractError


CALIBRATION_MANIFEST_SCHEMA = "rp3_lec_mp008_post_quant_calibration_v1"
CALIBRATION_STATUS = "calibrated_on_mp008_post_quantization"


def _sha256(value: Any, name: str) -> str:
    digest = str(value or "").strip().lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ContractError(f"{name} must be a 64-character hexadecimal SHA-256")
    return digest


def _probability(value: Any, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ContractError(f"{name} must be finite and in [0, 1]")
    return number


@dataclass(frozen=True)
class ControllerCalibration:
    """Thresholds and identities that must travel together at inference."""

    controller_version: str
    support_threshold: float
    minimum_route_confidence: float
    quantized_model_sha256: str
    development_input_fingerprint: str
    development_trace_bundle_sha256: str
    development_memory_bundle_sha256: str
    development_feature_bundle_sha256: str
    memory_id: str
    memory_logical_sha256: str
    teacher_graph_id: str
    teacher_graph_sha256: str
    feature_encoder_manifest_sha256: str
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "controller_version",
            "development_input_fingerprint",
            "memory_id",
            "teacher_graph_id",
            "contract_version",
        ):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ContractError(f"{name} must be non-empty")
            object.__setattr__(self, name, value)
        object.__setattr__(
            self, "support_threshold", _probability(self.support_threshold, "support_threshold")
        )
        object.__setattr__(
            self,
            "minimum_route_confidence",
            _probability(self.minimum_route_confidence, "minimum_route_confidence"),
        )
        for name in (
            "quantized_model_sha256",
            "development_trace_bundle_sha256",
            "development_memory_bundle_sha256",
            "development_feature_bundle_sha256",
            "memory_logical_sha256",
            "teacher_graph_sha256",
            "feature_encoder_manifest_sha256",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, Any]) -> "ControllerCalibration":
        if manifest.get("schema") != CALIBRATION_MANIFEST_SCHEMA:
            raise ContractError("manifest is not an RP3 MP008 calibration artifact")
        if manifest.get("status") != CALIBRATION_STATUS:
            raise ContractError("MP008 calibration artifact is not complete")
        expected = _sha256(manifest.get("logical_sha256"), "logical_sha256")
        payload = {key: value for key, value in manifest.items() if key != "logical_sha256"}
        if stable_sha256(payload) != expected:
            raise ContractError("MP008 calibration manifest logical SHA-256 mismatch")
        development = manifest.get("development_set")
        deployment = manifest.get("deployment_binding")
        thresholds = manifest.get("thresholds")
        if not all(isinstance(value, Mapping) for value in (development, deployment, thresholds)):
            raise ContractError("calibration manifest is missing a governed binding section")
        graph = deployment.get("teacher_graph")
        memory = deployment.get("memory")
        if not isinstance(graph, Mapping) or not isinstance(memory, Mapping):
            raise ContractError("calibration manifest graph/memory binding is missing")
        if development.get("corpus") != "MP008" or development.get("split") != "development":
            raise ContractError("calibration thresholds must be fitted on MP008 development only")
        return cls(
            controller_version=deployment.get("controller_version", ""),
            support_threshold=thresholds.get("support_probability", -1),
            minimum_route_confidence=thresholds.get("minimum_route_confidence", -1),
            quantized_model_sha256=deployment.get("quantized_model_sha256", ""),
            development_input_fingerprint=development.get("input_fingerprint", ""),
            development_trace_bundle_sha256=development.get("trace_bundle_sha256", ""),
            development_memory_bundle_sha256=development.get("memory_bundle_sha256", ""),
            development_feature_bundle_sha256=development.get("feature_bundle_sha256", ""),
            memory_id=memory.get("id", ""),
            memory_logical_sha256=memory.get("logical_sha256", ""),
            teacher_graph_id=graph.get("id", ""),
            teacher_graph_sha256=graph.get("sha256", ""),
            feature_encoder_manifest_sha256=deployment.get(
                "feature_encoder_manifest_sha256", ""
            ),
            contract_version=deployment.get("contract_version", ""),
        )

    @classmethod
    def read(cls, path: str | Path) -> "ControllerCalibration":
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ContractError("calibration manifest must be a JSON object")
        return cls.from_manifest(value)


def write_calibration_manifest(
    output_path: str | Path,
    *,
    support_threshold: float,
    minimum_route_confidence: float,
    quantized_model_path: str | Path,
    onnx_export_manifest: Mapping[str, Any],
    development_input_fingerprint: str,
    development_trace_bundle_sha256: str,
    development_memory_bundle_sha256: str,
    development_feature_bundle_sha256: str,
    metrics: Mapping[str, Any],
    overwrite: bool = False,
) -> dict[str, Any]:
    """Freeze already-fitted MP008 thresholds; this function does not fit them."""

    model_path = Path(quantized_model_path)
    if not model_path.is_file():
        raise ContractError("quantized ONNX model is missing")
    binding = onnx_export_manifest.get("runtime_binding")
    if not isinstance(binding, Mapping):
        raise ContractError("ONNX export manifest has no runtime binding")
    graph = binding.get("teacher_graph")
    memory = binding.get("memory")
    if not isinstance(graph, Mapping) or not isinstance(memory, Mapping):
        raise ContractError("ONNX export manifest has no graph/memory binding")
    payload = {
        "schema": CALIBRATION_MANIFEST_SCHEMA,
        "status": CALIBRATION_STATUS,
        "thresholds": {
            "support_probability": _probability(support_threshold, "support_threshold"),
            "minimum_route_confidence": _probability(
                minimum_route_confidence, "minimum_route_confidence"
            ),
        },
        "development_set": {
            "corpus": "MP008",
            "split": "development",
            "input_fingerprint": str(development_input_fingerprint),
            "trace_bundle_sha256": _sha256(
                development_trace_bundle_sha256, "development_trace_bundle_sha256"
            ),
            "memory_bundle_sha256": _sha256(
                development_memory_bundle_sha256, "development_memory_bundle_sha256"
            ),
            "feature_bundle_sha256": _sha256(
                development_feature_bundle_sha256, "development_feature_bundle_sha256"
            ),
            "used_for_gradients": False,
            "used_for_early_stopping_or_model_selection": False,
        },
        "deployment_binding": {
            "controller_version": str(onnx_export_manifest.get("controller_version", "")),
            "quantized_model_sha256": file_sha256(model_path),
            "memory": {
                "id": str(memory.get("id", "")),
                "logical_sha256": _sha256(memory.get("logical_sha256"), "memory.sha256"),
            },
            "teacher_graph": {
                "id": str(graph.get("id", "")),
                "sha256": _sha256(graph.get("sha256"), "teacher_graph.sha256"),
            },
            "feature_encoder_manifest_sha256": _sha256(
                binding.get("feature_encoder_manifest_sha256"),
                "feature_encoder_manifest_sha256",
            ),
            "contract_version": CONTRACT_VERSION,
        },
        "metrics": dict(metrics),
        "threshold_source": "offline_MP008_post_quantization_calibration",
        "online_threshold_override_allowed": False,
        "human_expert_reviewed": False,
    }
    payload["logical_sha256"] = stable_sha256(payload)
    # Parse our own payload before it becomes a frozen deployment artifact.
    ControllerCalibration.from_manifest(payload)
    path = Path(output_path)
    if path.exists() and not overwrite:
        raise RuntimeError("refusing to overwrite an existing calibration manifest")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(payload))
    return payload


def write_calibration_manifest_from_export(
    output_path: str | Path,
    *,
    support_threshold: float,
    minimum_route_confidence: float,
    quantized_model_path: str | Path,
    onnx_export_manifest_path: str | Path,
    metrics: Mapping[str, Any],
    overwrite: bool = False,
) -> dict[str, Any]:
    """Freeze thresholds using the MP008 identities recorded at ONNX export."""

    export_path = Path(onnx_export_manifest_path)
    export = json.loads(export_path.read_text(encoding="utf-8"))
    if not isinstance(export, Mapping):
        raise ContractError("ONNX export manifest must be a JSON object")
    expected = _sha256(export.get("logical_sha256"), "onnx_export.logical_sha256")
    if stable_sha256(
        {key: value for key, value in export.items() if key != "logical_sha256"}
    ) != expected:
        raise ContractError("ONNX export manifest logical SHA-256 mismatch")
    binding = export.get("runtime_binding")
    development = (
        binding.get("development_calibration_source")
        if isinstance(binding, Mapping)
        else None
    )
    if not isinstance(development, Mapping) or development.get("corpus") != "MP008":
        raise ContractError("ONNX export has no MP008 development binding")
    return write_calibration_manifest(
        output_path,
        support_threshold=support_threshold,
        minimum_route_confidence=minimum_route_confidence,
        quantized_model_path=quantized_model_path,
        onnx_export_manifest=export,
        development_input_fingerprint=str(development.get("input_fingerprint", "")),
        development_trace_bundle_sha256=str(
            development.get("trace_bundle_sha256", "")
        ),
        development_memory_bundle_sha256=str(
            development.get("memory_bundle_sha256", "")
        ),
        development_feature_bundle_sha256=str(
            development.get("feature_bundle_sha256", "")
        ),
        metrics=metrics,
        overwrite=overwrite,
    )


__all__ = [
    "CALIBRATION_MANIFEST_SCHEMA",
    "CALIBRATION_STATUS",
    "ControllerCalibration",
    "write_calibration_manifest",
    "write_calibration_manifest_from_export",
]
