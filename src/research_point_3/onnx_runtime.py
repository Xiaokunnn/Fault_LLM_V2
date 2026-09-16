"""ONNX Runtime adapter for the version-bound RP3 evidence controller.

This module never embeds text and never searches the full evidence graph.  A
caller supplies frozen, precomputed query/candidate feature vectors through a
``FeatureProvider``.  The adapter verifies the exact ONNX bytes, tensor schema,
candidate width, graph/memory binding, and MP008 post-quantization calibration
before creating a runtime session.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from .artifacts import file_sha256, stable_sha256
from .calibration import ControllerCalibration
from .contracts import (
    CARD_SLOT_ROLES,
    CONTRACT_VERSION,
    CardFieldState,
    ContractError,
    DiagnosticRole,
    QueryContext,
    RouteAction,
)
from .decoding import DecodedCardField, DecodedEvidenceDecision
from .tool_api import (
    ControllerPrediction,
    ResolvedCandidate,
    RuntimeEvidenceError,
)

try:  # optional on code-generation and non-deployment machines
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:  # optional on code-generation and non-deployment machines
    import onnxruntime as ort
except ImportError:  # pragma: no cover
    ort = None

ONNX_RUNTIME_INSTALL_HINT = (
    "RP3 ONNX inference requires onnxruntime and numpy. Install compatible "
    "packages on the deployment machine; importing this module remains safe "
    "without them."
)
EXPECTED_INPUTS = (
    "query_features",
    "candidate_features",
    "availability_mask",
    "selection_budget",
)
EXPECTED_OUTPUTS = (
    "rank_logits",
    "support_logits",
    "field_state_logits",
    "cardinality_logits",
    "route_logits",
)
CARD_FIELD_STATES = tuple(state.value for state in CardFieldState)
ROUTE_ACTIONS = tuple(action.value for action in RouteAction)


@runtime_checkable
class FeatureProvider(Protocol):
    """Frozen encoder identity; online lightweight CPU features are permitted.

    Full BGE/ANN/graph retrieval is not part of the student feature boundary.
    """

    feature_encoder_manifest_sha256: str

    def features_for(
        self,
        *,
        query: QueryContext,
        candidates: tuple[ResolvedCandidate, ...],
        query_dimension: int,
        evidence_dimension: int,
    ) -> tuple[Sequence[float], Sequence[Sequence[float]]]:
        """Return one query vector and one vector per candidate in input order."""


def _manifest(path: Path, schema: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise ContractError(f"unexpected manifest schema at {path}")
    expected = str(value.get("logical_sha256", "")).lower()
    unhashed = {key: item for key, item in value.items() if key != "logical_sha256"}
    if stable_sha256(unhashed) != expected:
        raise ContractError(f"manifest logical SHA-256 mismatch at {path}")
    return value


def _finite_vector(values: Sequence[float], expected: int, name: str) -> list[float]:
    result = [float(value) for value in values]
    if len(result) != expected or any(not math.isfinite(value) for value in result):
        raise RuntimeEvidenceError(
            f"{name} must contain exactly {expected} finite values"
        )
    return result


def decode_numpy_output(
    *,
    rank_logits: Any,
    support_logits: Any,
    field_state_logits: Any,
    cardinality_logits: Any,
    route_logits: Any,
    candidate_ids: Sequence[str],
    candidate_roles: Sequence[DiagnosticRole],
    availability_mask: Sequence[bool],
    selection_budget: int,
    support_threshold: float,
    minimum_route_confidence: float,
) -> DecodedEvidenceDecision:
    """Pure-NumPy constrained decoder for a single edge request."""

    count = len(candidate_ids)
    rank = np.asarray(rank_logits)[0, :count]
    support = np.asarray(support_logits)[0, :count]
    field_states = np.asarray(field_state_logits)[0]
    cardinalities = np.asarray(cardinality_logits)[0]
    route = np.asarray(route_logits)[0]
    if rank.shape != (count,) or support.shape != (count,):
        raise RuntimeEvidenceError("ONNX pointer heads do not align with candidates")
    if field_states.shape[0] != len(CARD_SLOT_ROLES):
        raise RuntimeEvidenceError("ONNX field head does not match the card schema")
    if route.shape != (len(ROUTE_ACTIONS),):
        raise RuntimeEvidenceError("ONNX route head does not match RouteAction")
    if not all(
        np.isfinite(values).all()
        for values in (rank, support, field_states, cardinalities, route)
    ):
        raise RuntimeEvidenceError("ONNX controller emitted a non-finite value")
    support_probabilities = 1.0 / (1.0 + np.exp(-np.clip(support, -80.0, 80.0)))
    rank_order = np.argsort(-rank, kind="stable").tolist()
    safe_available = {
        index for index, available in enumerate(availability_mask) if bool(available)
    }
    direct_indices = {
        index
        for index in safe_available
        if float(support_probabilities[index]) >= support_threshold
    }
    direct_count_by_role = {
        role: sum(
            index in direct_indices and candidate_roles[index] == role
            for index in range(count)
        )
        for role in CARD_SLOT_ROLES
    }
    fields: list[DecodedCardField] = []
    for field_index, role in enumerate(CARD_SLOT_ROLES):
        state = CardFieldState(
            CARD_FIELD_STATES[int(np.argmax(field_states[field_index]))]
        )
        cardinality = int(np.argmax(cardinalities[field_index]))
        if state in {CardFieldState.INSUFFICIENT, CardFieldState.NOT_APPLICABLE}:
            cardinality = 0
        else:
            cardinality = min(cardinality, direct_count_by_role[role])
            if cardinality == 0 or (
                state == CardFieldState.CONFLICT and cardinality < 2
            ):
                state = CardFieldState.INSUFFICIENT
                cardinality = 0
        fields.append(DecodedCardField(role=role, state=state, cardinality=cardinality))
    remaining = {field.role: field.cardinality for field in fields}
    selected_indices: list[int] = []
    for index in rank_order:
        if len(selected_indices) >= selection_budget:
            break
        role = candidate_roles[index]
        if index in direct_indices and role in remaining and remaining[role] > 0:
            selected_indices.append(index)
            remaining[role] -= 1
    actual = {
        role: sum(candidate_roles[index] == role for index in selected_indices)
        for role in CARD_SLOT_ROLES
    }
    safe_fields: list[DecodedCardField] = []
    for field in fields:
        cardinality = actual[field.role]
        if cardinality == field.cardinality:
            state = field.state
        elif field.state == CardFieldState.CONFLICT and cardinality >= 2:
            state = CardFieldState.CONFLICT
        elif cardinality >= 1:
            state = CardFieldState.SUPPORTED
        else:
            state = CardFieldState.INSUFFICIENT
        safe_fields.append(
            DecodedCardField(role=field.role, state=state, cardinality=cardinality)
        )
    shifted = route - np.max(route)
    probabilities = np.exp(shifted) / np.exp(shifted).sum()
    route_index = int(np.argmax(probabilities))
    action = RouteAction(ROUTE_ACTIONS[route_index])
    confidence = float(probabilities[route_index])
    reasons: list[str] = []
    if len(selected_indices) < selection_budget:
        reasons.append("active_underfill")
    if not safe_available:
        action = RouteAction.ABSTAIN
        reasons.append("no_known_available_evidence")
    elif action == RouteAction.ANSWER and not selected_indices:
        action = RouteAction.FALLBACK
        reasons.append("answer_blocked_without_direct_support")
    elif action == RouteAction.ANSWER and confidence < minimum_route_confidence:
        action = RouteAction.FALLBACK
        reasons.append("answer_blocked_by_route_confidence")
    if not reasons:
        reasons.append("decoded_with_evidence_contract")
    return DecodedEvidenceDecision(
        selected_evidence_ids=tuple(candidate_ids[index] for index in selected_indices),
        direct_support_evidence_ids=tuple(
            candidate_ids[index] for index in rank_order if index in direct_indices
        ),
        ranked_evidence_ids=tuple(candidate_ids[index] for index in rank_order),
        candidate_order_rank_scores=tuple(float(value) for value in rank),
        support_probabilities=tuple(float(value) for value in support_probabilities),
        card_fields=tuple(safe_fields),
        route_action=action,
        route_confidence=confidence,
        rejected_evidence_ids=(),
        reason_codes=tuple(reasons),
    )


class OnnxEvidenceController:
    """Four-head LEC backed by a fully version-bound ONNX Runtime session."""

    def __init__(
        self,
        *,
        onnx_manifest_path: str | Path,
        quantized_model_path: str | Path,
        calibration_manifest_path: str | Path,
        memory_manifest: Mapping[str, Any],
        feature_provider: FeatureProvider,
        providers: Sequence[str] | None = None,
    ) -> None:
        if ort is None or np is None:  # pragma: no cover
            raise RuntimeError(ONNX_RUNTIME_INSTALL_HINT)
        from .onnx_export import ONNX_EXPORT_SCHEMA

        export_path = Path(onnx_manifest_path)
        export = _manifest(export_path, ONNX_EXPORT_SCHEMA)
        calibration = ControllerCalibration.read(calibration_manifest_path)
        model_path = Path(quantized_model_path)
        if file_sha256(model_path) != calibration.quantized_model_sha256:
            raise ContractError("quantized ONNX exact-byte SHA-256 mismatch")
        if calibration.contract_version != CONTRACT_VERSION:
            raise ContractError("calibration evidence-contract version mismatch")
        binding = export.get("runtime_binding")
        if not isinstance(binding, Mapping):
            raise ContractError("ONNX export has no graph/memory runtime binding")
        memory_binding = binding.get("memory")
        graph_binding = binding.get("teacher_graph")
        if not isinstance(memory_binding, Mapping) or not isinstance(graph_binding, Mapping):
            raise ContractError("ONNX export graph/memory binding is malformed")
        expected_memory = {
            "id": calibration.memory_id,
            "logical_sha256": calibration.memory_logical_sha256,
        }
        if {key: memory_binding.get(key) for key in expected_memory} != expected_memory:
            raise ContractError("ONNX export and calibration bind different memories")
        expected_graph = {
            "id": calibration.teacher_graph_id,
            "sha256": calibration.teacher_graph_sha256,
        }
        if {key: graph_binding.get(key) for key in expected_graph} != expected_graph:
            raise ContractError("ONNX export and calibration bind different teacher graphs")
        actual_memory = {
            "id": memory_manifest.get("memory_id"),
            "logical_sha256": memory_manifest.get("logical_sha256"),
        }
        if actual_memory != expected_memory:
            raise ContractError("runtime evidence memory does not match calibrated memory")
        actual_graph = memory_manifest.get("teacher_graph")
        if not isinstance(actual_graph, Mapping) or {
            key: actual_graph.get(key) for key in expected_graph
        } != expected_graph:
            raise ContractError("runtime evidence memory binds a different teacher graph")
        if export.get("controller_version") != calibration.controller_version:
            raise ContractError("controller version differs from MP008 calibration")
        development = binding.get("development_calibration_source")
        expected_development = {
            "input_fingerprint": calibration.development_input_fingerprint,
            "trace_bundle_sha256": calibration.development_trace_bundle_sha256,
            "memory_bundle_sha256": calibration.development_memory_bundle_sha256,
            "feature_bundle_sha256": calibration.development_feature_bundle_sha256,
        }
        if not isinstance(development, Mapping) or {
            key: development.get(key) for key in expected_development
        } != expected_development:
            raise ContractError("MP008 calibration data identity differs from ONNX export")
        provider_hash = str(
            getattr(feature_provider, "feature_encoder_manifest_sha256", "")
        ).lower()
        if provider_hash != calibration.feature_encoder_manifest_sha256:
            raise ContractError("feature provider encoder identity mismatch")

        inputs = export.get("inputs", {})
        self.query_dimension = int(inputs.get("query_features", [0, 0])[1])
        candidate_shape = inputs.get("candidate_features", [0, 0, 0])
        self.max_candidates = int(export.get("fixed_candidate_width", 0))
        self.evidence_dimension = int(candidate_shape[2])
        if self.max_candidates < 1 or int(candidate_shape[1]) != self.max_candidates:
            raise ContractError("ONNX export candidate-width contract is invalid")
        if self.query_dimension < 1 or self.evidence_dimension < 1:
            raise ContractError("ONNX export feature dimensions are invalid")
        if tuple(export.get("outputs", ())) != EXPECTED_OUTPUTS:
            raise ContractError("ONNX export output-head contract is invalid")

        options = providers or ("CPUExecutionProvider",)
        try:
            self._session = ort.InferenceSession(str(model_path), providers=list(options))
        except Exception as exc:
            raise RuntimeError("failed to create the version-bound ONNX Runtime session") from exc
        session_inputs = tuple(value.name for value in self._session.get_inputs())
        session_outputs = tuple(value.name for value in self._session.get_outputs())
        if session_inputs != EXPECTED_INPUTS or session_outputs != EXPECTED_OUTPUTS:
            raise ContractError("ONNX graph input/output names differ from frozen manifest")
        self._validate_session_shapes()
        self.feature_provider = feature_provider
        self.calibration = calibration
        self.controller_version = calibration.controller_version
        self.support_threshold = calibration.support_threshold
        self.minimum_route_confidence = calibration.minimum_route_confidence
        self.memory_id = calibration.memory_id
        self.memory_logical_sha256 = calibration.memory_logical_sha256
        self.teacher_graph_id = calibration.teacher_graph_id
        self.teacher_graph_sha256 = calibration.teacher_graph_sha256

    def _validate_session_shapes(self) -> None:
        shapes = {value.name: value.shape for value in self._session.get_inputs()}
        query = shapes["query_features"]
        candidates = shapes["candidate_features"]
        mask = shapes["availability_mask"]
        if len(query) != 2 or query[1] != self.query_dimension:
            raise ContractError("ONNX query feature dimension mismatch")
        if len(candidates) != 3 or tuple(candidates[1:]) != (
            self.max_candidates,
            self.evidence_dimension,
        ):
            raise ContractError("ONNX candidate feature shape mismatch")
        if len(mask) != 2 or mask[1] != self.max_candidates:
            raise ContractError("ONNX availability-mask width mismatch")
        outputs = {value.name: value.shape for value in self._session.get_outputs()}
        if tuple(outputs["field_state_logits"][-2:]) != (
            len(CARD_SLOT_ROLES),
            len(CARD_FIELD_STATES),
        ):
            raise ContractError("ONNX field-state head does not match card contract")
        if outputs["route_logits"][-1] != len(ROUTE_ACTIONS):
            raise ContractError("ONNX route head does not match route contract")

    def predict(
        self,
        *,
        query: QueryContext,
        candidates: tuple[ResolvedCandidate, ...],
        selection_budget: int,
    ) -> ControllerPrediction:
        if not candidates or len(candidates) > self.max_candidates:
            raise RuntimeEvidenceError(
                f"candidate count must be in [1, {self.max_candidates}]"
            )
        query_values, candidate_values = self.feature_provider.features_for(
            query=query,
            candidates=candidates,
            query_dimension=self.query_dimension,
            evidence_dimension=self.evidence_dimension,
        )
        query_vector = _finite_vector(
            query_values, self.query_dimension, "query feature vector"
        )
        if len(candidate_values) != len(candidates):
            raise RuntimeEvidenceError("feature provider must return one vector per candidate")
        candidate_vectors = [
            _finite_vector(values, self.evidence_dimension, f"candidate feature {index}")
            for index, values in enumerate(candidate_values)
        ]
        width = self.max_candidates
        features = np.zeros((1, width, self.evidence_dimension), dtype=np.float32)
        availability = np.zeros((1, width), dtype=np.bool_)
        candidate_ids: list[str] = []
        candidate_roles: list[str] = []
        for index, (candidate, vector) in enumerate(zip(candidates, candidate_vectors)):
            features[0, index] = np.asarray(vector, dtype=np.float32)
            availability[0, index] = bool(candidate.available)
            candidate_ids.append(candidate.evidence_id)
            role = candidate.record.role.value if candidate.record is not None else "context"
            candidate_roles.append(role)
        # Fixed-width padding uses unique, unavailable sentinel IDs.  They are
        # unknown to the memory and therefore cannot survive constrained decode.
        for index in range(len(candidates), width):
            candidate_ids.append(f"__PAD_{index}__")
            candidate_roles.append("context")
        raw = self._session.run(
            list(EXPECTED_OUTPUTS),
            {
                "query_features": np.asarray([query_vector], dtype=np.float32),
                "candidate_features": features,
                "availability_mask": availability,
                "selection_budget": np.asarray([selection_budget], dtype=np.int64),
            },
        )
        decoded = decode_numpy_output(
            rank_logits=raw[0],
            support_logits=raw[1],
            field_state_logits=raw[2],
            cardinality_logits=raw[3],
            route_logits=raw[4],
            candidate_ids=candidate_ids[: len(candidates)],
            candidate_roles=tuple(
                DiagnosticRole(value) for value in candidate_roles[: len(candidates)]
            ),
            availability_mask=availability[0, : len(candidates)].tolist(),
            selection_budget=selection_budget,
            support_threshold=self.support_threshold,
            minimum_route_confidence=self.minimum_route_confidence,
        )
        return ControllerPrediction.from_decoded(
            decoded, tuple(candidate_ids[: len(candidates)])
        )


__all__ = [
    "EXPECTED_INPUTS",
    "EXPECTED_OUTPUTS",
    "FeatureProvider",
    "ONNX_RUNTIME_INSTALL_HINT",
    "OnnxEvidenceController",
    "decode_numpy_output",
]
