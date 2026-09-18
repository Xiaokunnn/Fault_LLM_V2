"""Fail-closed tensorization of frozen RP3 teacher supervision.

This module never creates embeddings.  A model-capable preparation machine must
export explicit query/evidence feature vectors, together with its encoder
manifest.  Training only consumes those frozen vectors and the governed
``TeacherTrace`` / ``CompactEvidenceRecord`` contracts.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .artifacts import (
    canonical_json_bytes,
    read_compact_evidence_memory_bundle,
    read_teacher_trace_bundle,
    stable_sha256,
    validate_trace_memory_references,
)
from .contracts import (
    CARD_SLOT_ROLES,
    CardFieldState,
    CompactEvidenceRecord,
    ContractError,
    DataSplit,
    RouteAction,
    SupportVerdict,
    TeacherTrace,
)
from .losses import IGNORE_INDEX, EvidenceControllerTargets
from .model import CARD_FIELD_STATES, ROUTE_ACTIONS, require_torch
from .splits import (
    assert_training_trace_boundary,
    corpus_partition,
    trace_group_tokens,
)
from .teacher_freeze import TEACHER_FREEZE_ID, TEACHER_FREEZE_SCHEMA

try:
    import torch
    from torch.utils.data import Dataset
except ImportError:  # pragma: no cover
    torch = None

    class Dataset:  # type: ignore[no-redef]
        pass


FEATURE_BUNDLE_SCHEMA = "rp3_explicit_feature_bundle_v1"


def _finite_vector(values: Sequence[Any], name: str) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)):
        raise ContractError(f"{name} must be a numeric array")
    result = tuple(float(value) for value in values)
    if not result or any(not math.isfinite(value) for value in result):
        raise ContractError(f"{name} must contain finite values and cannot be empty")
    return result


@dataclass(frozen=True)
class ExplicitFeatureStore:
    """Precomputed features plus provenance; no encoder is invoked here."""

    query_features: Mapping[str, tuple[float, ...]]
    evidence_features: Mapping[str, tuple[float, ...]]
    query_dimension: int
    evidence_dimension: int
    encoder_manifest: Mapping[str, Any]
    logical_sha256: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExplicitFeatureStore":
        if data.get("schema") != FEATURE_BUNDLE_SCHEMA:
            raise ContractError(
                f"feature bundle schema must be {FEATURE_BUNDLE_SCHEMA}"
            )
        payload = {str(key): value for key, value in data.items() if key != "logical_sha256"}
        expected_hash = str(data.get("logical_sha256", "")).lower()
        actual_hash = stable_sha256(payload)
        if expected_hash != actual_hash:
            raise ContractError("explicit feature bundle logical SHA-256 mismatch")
        query_dim = int(data.get("query_dimension", 0))
        evidence_dim = int(data.get("evidence_dimension", 0))
        if query_dim < 1 or evidence_dim < 1:
            raise ContractError("feature dimensions must be >= 1")
        query_data = data.get("query_features", {})
        evidence_data = data.get("evidence_features", {})
        if not isinstance(query_data, Mapping) or not isinstance(evidence_data, Mapping):
            raise ContractError("query_features and evidence_features must be objects")
        query_features = {
            str(key): _finite_vector(value, f"query_features[{key!r}]")
            for key, value in query_data.items()
        }
        evidence_features = {
            str(key): _finite_vector(value, f"evidence_features[{key!r}]")
            for key, value in evidence_data.items()
        }
        if any(len(vector) != query_dim for vector in query_features.values()):
            raise ContractError("a query feature vector disagrees with query_dimension")
        if any(len(vector) != evidence_dim for vector in evidence_features.values()):
            raise ContractError("an evidence feature vector disagrees with evidence_dimension")
        encoder_manifest = data.get("encoder_manifest", {})
        if not isinstance(encoder_manifest, Mapping) or not encoder_manifest:
            raise ContractError("feature bundle must preserve a non-empty encoder_manifest")
        return cls(
            query_features=query_features,
            evidence_features=evidence_features,
            query_dimension=query_dim,
            evidence_dimension=evidence_dim,
            encoder_manifest=dict(encoder_manifest),
            logical_sha256=actual_hash,
        )

    @classmethod
    def read(cls, path: str | Path) -> "ExplicitFeatureStore":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            raise ContractError("explicit feature bundle must be a JSON object")
        return cls.from_dict(data)

    @staticmethod
    def build_payload(
        *,
        query_features: Mapping[str, Sequence[float]],
        evidence_features: Mapping[str, Sequence[float]] | None,
        query_dimension: int,
        evidence_dimension: int,
        encoder_manifest: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Build a canonically hashable payload for an external feature exporter."""

        payload = {
            "schema": FEATURE_BUNDLE_SCHEMA,
            "query_dimension": int(query_dimension),
            "evidence_dimension": int(evidence_dimension),
            "query_features": {
                str(key): [float(value) for value in vector]
                for key, vector in sorted(query_features.items())
            },
            "evidence_features": {
                str(key): [float(value) for value in vector]
                for key, vector in sorted((evidence_features or {}).items())
            },
            "encoder_manifest": dict(encoder_manifest),
            "generation_boundary": "precomputed_externally_no_embedding_generated_in_training",
        }
        payload["logical_sha256"] = stable_sha256(payload)
        return payload


@dataclass(frozen=True)
class TensorizationConfig:
    max_candidates: int = 32
    max_cardinality: int = 3
    require_validation_split: bool = True

    def __post_init__(self) -> None:
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be >= 1")
        if self.max_cardinality < 1:
            raise ValueError("max_cardinality must be >= 1")


@dataclass(frozen=True)
class PreparedTrainingData:
    train_dataset: "TensorizedTeacherDataset"
    validation_dataset: "TensorizedTeacherDataset"
    development_dataset: "TensorizedTeacherDataset | None"
    trace_manifest: Mapping[str, Any]
    memory_manifest: Mapping[str, Any]
    development_trace_manifest: Mapping[str, Any] | None
    development_memory_manifest: Mapping[str, Any] | None
    teacher_freeze_manifest: Mapping[str, Any]
    feature_store: ExplicitFeatureStore
    development_feature_store: ExplicitFeatureStore | None
    input_fingerprint: str
    development_fingerprint: str | None


def _validate_teacher_freeze_manifest(manifest: Mapping[str, Any]) -> str:
    if manifest.get("schema") != TEACHER_FREEZE_SCHEMA:
        raise ContractError("teacher freeze manifest has an unknown schema")
    if manifest.get("freeze_id") != TEACHER_FREEZE_ID:
        raise ContractError("teacher freeze manifest has an unknown freeze ID")
    if manifest.get("teacher_graph_id") != "TeacherGraph_RP3_v1":
        raise ContractError("training requires the explicit TeacherGraph_RP3_v1 freeze")
    if manifest.get("status") != "frozen":
        raise ContractError("TeacherGraph_RP3_v1 is blocked or not frozen")
    expected = str(
        manifest.get("freeze_manifest_logical_sha256", "")
    ).lower()
    unhashed = {
        key: value
        for key, value in manifest.items()
        if key != "freeze_manifest_logical_sha256"
    }
    actual = stable_sha256(unhashed)
    if expected != actual:
        raise ContractError("teacher freeze manifest logical SHA-256 mismatch")
    checks = manifest.get("checks", ())
    if not isinstance(checks, list) or not checks or any(
        not isinstance(item, Mapping) or item.get("ok") is not True for item in checks
    ):
        raise ContractError("teacher freeze manifest contains a failed or malformed check")
    return actual


def _freeze_identities(manifest: Mapping[str, Any]) -> tuple[str, str]:
    graph_hash = str(manifest.get("immutable_graph_logical_sha256", "")).lower()
    system_hash = str(manifest.get("teacher_system_identity_sha256", "")).lower()
    for value, name in (
        (graph_hash, "immutable_graph_logical_sha256"),
        (system_hash, "teacher_system_identity_sha256"),
    ):
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ContractError(f"teacher freeze has no valid {name}")
    return graph_hash, system_hash


def assert_group_disjoint_splits(
    traces: Iterable[TeacherTrace],
    *,
    split_mode: str = "inductive_evidence_holdout",
) -> None:
    """Validate leakage keys appropriate to the declared evaluation estimand."""

    owners: dict[str, DataSplit] = {}
    for trace in traces:
        if trace.split not in {DataSplit.TRAIN, DataSplit.VALIDATION}:
            raise ContractError("training tensorization accepts train/validation traces only")
        if split_mode == "fixed_memory_query_generalization":
            tokens = {f"scenario:{trace.query.scenario_id}"}
        elif split_mode == "inductive_evidence_holdout":
            tokens = set(trace_group_tokens(trace))
            tokens.update(f"evidence:{item}" for item in trace.candidate_evidence_ids)
        else:
            raise ContractError(f"unknown training split mode: {split_mode}")
        for token in tokens:
            previous = owners.setdefault(token, trace.split)
            if previous != trace.split:
                raise ContractError(
                    f"group leakage across train/validation for {token}: "
                    f"{previous.value} vs {trace.split.value}"
                )


def assert_development_disjoint_from_build(
    build_traces: Iterable[TeacherTrace],
    development_traces: Iterable[TeacherTrace],
    development_records: Iterable[CompactEvidenceRecord] = (),
) -> None:
    """Keep MP008 calibration groups outside both build-set learning splits."""

    build_tokens: set[str] = set()
    for trace in build_traces:
        build_tokens.update(trace_group_tokens(trace))
        build_tokens.update(f"evidence:{item}" for item in trace.candidate_evidence_ids)
    for trace in development_traces:
        development_tokens = set(trace_group_tokens(trace))
        development_tokens.update(
            f"evidence:{item}" for item in trace.candidate_evidence_ids
        )
        overlap = sorted(build_tokens & development_tokens)
        if overlap:
            raise ContractError(
                "MP008 development groups overlap build-set train/validation: "
                + ", ".join(overlap)
            )
    for record in development_records:
        memory_tokens = {
            f"claim:{record.claim_id}",
            f"source_family:{record.provenance.source_family_id}",
            f"evidence:{record.evidence_id}",
        }
        overlap = sorted(build_tokens & memory_tokens)
        if overlap:
            raise ContractError(
                "MP008 development memory overlaps build-set train/validation: "
                + ", ".join(overlap)
            )


def _graph_binding(manifest: Mapping[str, Any], name: str) -> tuple[str, str]:
    graph = manifest.get("teacher_graph")
    if not isinstance(graph, Mapping):
        raise ContractError(f"{name} has no teacher_graph binding")
    graph_id = str(graph.get("id", ""))
    graph_hash = str(graph.get("sha256", "")).lower()
    if graph_id != "TeacherGraph_RP3_v1" or len(graph_hash) != 64:
        raise ContractError(f"{name} has an invalid teacher graph binding")
    return graph_id, graph_hash


def validate_training_sources(
    traces: Sequence[TeacherTrace],
    records: Sequence[CompactEvidenceRecord],
    trace_manifest: Mapping[str, Any],
    memory_manifest: Mapping[str, Any],
    teacher_freeze_manifest: Mapping[str, Any],
) -> str:
    """Validate teacher identity, replay binding, split boundary and references."""

    freeze_hash = _validate_teacher_freeze_manifest(teacher_freeze_manifest)
    frozen_graph_hash, frozen_system_hash = _freeze_identities(teacher_freeze_manifest)
    split_protocol = trace_manifest.get("split_protocol", {})
    if not isinstance(split_protocol, Mapping):
        raise ContractError("trace manifest split_protocol must be a JSON object")
    split_mode = str(split_protocol.get("mode", ""))
    assert_training_trace_boundary(traces, split_mode=split_mode)
    assert_group_disjoint_splits(traces, split_mode=split_mode)
    validate_trace_memory_references(traces, records)
    trace_graph = _graph_binding(trace_manifest, "trace manifest")
    memory_graph = _graph_binding(memory_manifest, "memory manifest")
    if trace_graph != memory_graph:
        raise ContractError("trace and evidence-memory bundles bind different teacher graphs")
    # The teacher graph bundle is explicitly bound to the immutable freeze
    # manifest itself.  A second optional field must never weaken that binding.
    if trace_graph[1] != frozen_graph_hash:
        raise ContractError(
            "training bundles are not bound to the frozen immutable graph identity"
        )
    trace_system_hash = str(trace_manifest.get("teacher_system_identity_sha256", "")).lower()
    memory_system_hash = str(memory_manifest.get("teacher_system_identity_sha256", "")).lower()
    if trace_system_hash != frozen_system_hash or memory_system_hash != frozen_system_hash:
        raise ContractError(
            "training bundles are not bound to the frozen teacher-system identity"
        )
    replay_hash = str(trace_manifest.get("teacher_replay_sha256", "")).lower()
    allowed_replay_hashes = {
        str(item.get("sha256", "")).lower()
        for item in teacher_freeze_manifest.get("replay_artifacts", ())
        if isinstance(item, Mapping)
        and str(item.get("path", "")).endswith("retrieval_replay.jsonl")
    }
    if replay_hash not in allowed_replay_hashes:
        raise ContractError("teacher traces are not bound to a frozen RP2 replay artifact")
    return freeze_hash


def validate_development_sources(
    traces: Sequence[TeacherTrace],
    records: Sequence[CompactEvidenceRecord],
    trace_manifest: Mapping[str, Any],
    memory_manifest: Mapping[str, Any],
    teacher_freeze_manifest: Mapping[str, Any],
    *,
    expected_graph_binding: tuple[str, str],
) -> str:
    """Validate an MP008-only bundle that is forbidden from gradient training."""

    freeze_hash = _validate_teacher_freeze_manifest(teacher_freeze_manifest)
    frozen_graph_hash, frozen_system_hash = _freeze_identities(teacher_freeze_manifest)
    if not traces:
        raise ContractError("development trace bundle cannot be empty")
    if any(trace.split != DataSplit.DEVELOPMENT for trace in traces):
        raise ContractError("development bundle must contain DataSplit.DEVELOPMENT only")
    if any(
        corpus_partition(document_id) != "development"
        for trace in traces
        for document_id in trace.document_group_ids
    ):
        raise ContractError("development traces must be sourced only from MP008")
    if any(record.partition != DataSplit.DEVELOPMENT for record in records):
        raise ContractError("development memory must contain DataSplit.DEVELOPMENT only")
    if any(corpus_partition(record.provenance.doc_id) != "development" for record in records):
        raise ContractError("development evidence memory must be sourced only from MP008")
    validate_trace_memory_references(traces, records)
    trace_graph = _graph_binding(trace_manifest, "development trace manifest")
    memory_graph = _graph_binding(memory_manifest, "development memory manifest")
    if trace_graph != memory_graph or trace_graph != expected_graph_binding:
        raise ContractError(
            "development bundles must bind the same frozen TeacherGraph_RP3_v1 "
            "as the build-set training bundles"
        )
    if trace_graph[1] != frozen_graph_hash:
        raise ContractError(
            "development bundles are not bound to the frozen immutable graph identity"
        )
    trace_system_hash = str(trace_manifest.get("teacher_system_identity_sha256", "")).lower()
    memory_system_hash = str(memory_manifest.get("teacher_system_identity_sha256", "")).lower()
    if trace_system_hash != frozen_system_hash or memory_system_hash != frozen_system_hash:
        raise ContractError(
            "development bundles are not bound to the frozen teacher-system identity"
        )
    replay_hash = str(trace_manifest.get("teacher_replay_sha256", "")).lower()
    if len(replay_hash) != 64 or any(
        character not in "0123456789abcdef" for character in replay_hash
    ):
        raise ContractError("development trace bundle has no valid replay SHA-256")
    build_replay_hashes = {
        str(item.get("sha256", "")).lower()
        for item in teacher_freeze_manifest.get("replay_artifacts", ())
        if isinstance(item, Mapping)
        and str(item.get("path", "")).endswith("retrieval_replay.jsonl")
    }
    if replay_hash in build_replay_hashes:
        raise ContractError(
            "MP008 development traces must bind a distinct development replay, "
            "not the build-set RP2 replay"
        )
    return freeze_hash


def _explicit_route_action_costs(trace: TeacherTrace) -> tuple[float, ...]:
    explicit_costs = trace.metadata.get("route_action_costs")
    if not isinstance(explicit_costs, Mapping):
        raise ContractError(
            f"trace {trace.trace_id} must explicitly declare "
            "metadata.route_action_costs for every RouteAction"
        )
    missing_costs = [action for action in ROUTE_ACTIONS if action not in explicit_costs]
    extra_costs = sorted(set(str(key) for key in explicit_costs) - set(ROUTE_ACTIONS))
    if missing_costs or extra_costs:
        raise ContractError(
            "metadata.route_action_costs must contain exactly: "
            + ", ".join(ROUTE_ACTIONS)
        )
    route_costs = tuple(float(explicit_costs[action]) for action in ROUTE_ACTIONS)
    if any(not math.isfinite(value) or value < 0 for value in route_costs):
        raise ContractError("route action costs must be finite and non-negative")
    return route_costs


class TensorizedTeacherDataset(Dataset):
    """Fixed-width tensor view of complete teacher decision traces."""

    def __init__(
        self,
        traces: Sequence[TeacherTrace],
        records: Sequence[CompactEvidenceRecord],
        features: ExplicitFeatureStore,
        config: TensorizationConfig,
    ) -> None:
        require_torch()
        self.traces = tuple(traces)
        self.records = {record.evidence_id: record for record in records}
        self.features = features
        self.config = config
        if not self.traces:
            raise ContractError("a tensorized dataset cannot be empty")
        for trace in self.traces:
            if trace.trace_id not in features.query_features:
                raise ContractError(f"missing explicit query feature for {trace.trace_id}")
            if len(trace.candidate_evidence_ids) > config.max_candidates:
                raise ContractError(
                    f"trace {trace.trace_id} has {len(trace.candidate_evidence_ids)} "
                    f"candidates, exceeding fixed width {config.max_candidates}"
                )
            if trace.selection_budget > config.max_cardinality:
                raise ContractError(
                    f"trace {trace.trace_id} selection budget exceeds the configured "
                    "cardinality bound"
                )
            self._validate_trace_features(trace)
            _explicit_route_action_costs(trace)

    def _evidence_vector(self, evidence_id: str) -> tuple[float, ...]:
        if evidence_id in self.features.evidence_features:
            return self.features.evidence_features[evidence_id]
        record = self.records[evidence_id]
        if not record.feature_vector:
            raise ContractError(
                f"evidence {evidence_id} has no explicit feature in either feature "
                "bundle or compact memory"
            )
        if len(record.feature_vector) != self.features.evidence_dimension:
            raise ContractError(
                f"evidence {evidence_id} feature disagrees with evidence_dimension"
            )
        return record.feature_vector

    def _validate_trace_features(self, trace: TeacherTrace) -> None:
        if len(self.features.query_features[trace.trace_id]) != self.features.query_dimension:
            raise ContractError(f"query feature dimension mismatch for {trace.trace_id}")
        for evidence_id in trace.candidate_evidence_ids:
            if evidence_id not in self.records:
                raise ContractError(f"unknown evidence pointer {evidence_id}")
            self._evidence_vector(evidence_id)
        for slot in trace.diagnosis_card.slots:
            if len(slot.items) > self.config.max_cardinality:
                raise ContractError(
                    f"trace {trace.trace_id} card cardinality exceeds configured bound"
                )

    def __len__(self) -> int:
        return len(self.traces)

    def __getitem__(self, index: int) -> dict[str, Any]:
        trace = self.traces[index]
        width = self.config.max_candidates
        evidence_dim = self.features.evidence_dimension
        candidate_features = torch.zeros(width, evidence_dim, dtype=torch.float32)
        availability_mask = torch.zeros(width, dtype=torch.bool)
        teacher_rank_scores = torch.zeros(width, dtype=torch.float32)
        support_labels = torch.full((width,), IGNORE_INDEX, dtype=torch.long)
        candidate_ids = [""] * width
        for position, decision in enumerate(trace.evidence_decisions):
            candidate_ids[position] = decision.evidence_id
            candidate_features[position] = torch.tensor(
                self._evidence_vector(decision.evidence_id), dtype=torch.float32
            )
            availability_mask[position] = bool(trace.availability_mask[position])
            teacher_rank_scores[position] = float(decision.teacher_score)
            if decision.support == SupportVerdict.DIRECT:
                support_labels[position] = 1
            elif decision.support in {SupportVerdict.INDIRECT, SupportVerdict.IRRELEVANT}:
                support_labels[position] = 0

        field_states = torch.tensor(
            [CARD_FIELD_STATES.index(slot.state.value) for slot in trace.diagnosis_card.slots],
            dtype=torch.long,
        )
        cardinalities = torch.tensor(
            [len(slot.items) for slot in trace.diagnosis_card.slots], dtype=torch.long
        )
        route_label = torch.tensor(
            IGNORE_INDEX if trace.metadata.get("route_supervision_status") == "pending_student_rollout"
            else ROUTE_ACTIONS.index(trace.route.action.value), dtype=torch.long
        )
        route_costs = _explicit_route_action_costs(trace)
        return {
            "trace_id": trace.trace_id,
            "scenario_id": trace.query.scenario_id,
            "perturbation_id": trace.perturbation_id,
            "is_intervention": trace.perturbation_id != "original",
            "candidate_evidence_ids": tuple(candidate_ids),
            "query_features": torch.tensor(
                self.features.query_features[trace.trace_id], dtype=torch.float32
            ),
            "candidate_features": candidate_features,
            "availability_mask": availability_mask,
            "selection_budget": torch.tensor(trace.selection_budget, dtype=torch.long),
            "teacher_rank_scores": teacher_rank_scores,
            "support_labels": support_labels,
            "field_state_labels": field_states,
            "cardinality_labels": cardinalities,
            "requested_field_mask": torch.tensor(
                [role == trace.query.requested_role for role in CARD_SLOT_ROLES], dtype=torch.bool
            ),
            "requested_candidate_mask": torch.tensor(
                [bool(eid) and self.records[eid].role == trace.query.requested_role for eid in candidate_ids],
                dtype=torch.bool
            ),
            "route_labels": route_label,
            "route_action_costs": torch.tensor(route_costs, dtype=torch.float32),
        }


def collate_teacher_batch(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Collate tensors and preserve symbolic IDs outside the model input."""

    require_torch()
    if not rows:
        raise ContractError("cannot collate an empty teacher batch")
    tensor_keys = (
        "query_features",
        "candidate_features",
        "availability_mask",
        "selection_budget",
        "teacher_rank_scores",
        "support_labels",
        "field_state_labels",
        "cardinality_labels",
        "requested_field_mask",
        "requested_candidate_mask",
        "route_labels",
        "route_action_costs",
    )
    result: dict[str, Any] = {
        key: torch.stack([row[key] for row in rows]) for key in tensor_keys
    }
    for key in (
        "trace_id",
        "scenario_id",
        "perturbation_id",
        "is_intervention",
        "candidate_evidence_ids",
    ):
        result[key] = tuple(row[key] for row in rows)
    result["targets"] = EvidenceControllerTargets(
        teacher_rank_scores=result["teacher_rank_scores"],
        support_labels=result["support_labels"],
        field_state_labels=result["field_state_labels"],
        cardinality_labels=result["cardinality_labels"],
        requested_field_mask=result["requested_field_mask"],
        route_labels=result["route_labels"],
        route_action_costs=result["route_action_costs"],
    )
    return result


def prepare_training_data(
    *,
    trace_bundle_dir: str | Path,
    memory_bundle_dir: str | Path,
    teacher_freeze_path: str | Path,
    feature_bundle_path: str | Path,
    config: TensorizationConfig,
    development_trace_bundle_dir: str | Path | None = None,
    development_memory_bundle_dir: str | Path | None = None,
    development_feature_bundle_path: str | Path | None = None,
) -> PreparedTrainingData:
    """Load, verify, and tensorize already-frozen RP3 inputs."""

    require_torch()
    traces, trace_manifest = read_teacher_trace_bundle(
        trace_bundle_dir, purpose="training"
    )
    records, memory_manifest = read_compact_evidence_memory_bundle(
        memory_bundle_dir, purpose="training"
    )
    freeze_manifest = json.loads(Path(teacher_freeze_path).read_text(encoding="utf-8"))
    if not isinstance(freeze_manifest, Mapping):
        raise ContractError("teacher freeze manifest must be a JSON object")
    freeze_hash = validate_training_sources(
        traces, records, trace_manifest, memory_manifest, freeze_manifest
    )
    features = ExplicitFeatureStore.read(feature_bundle_path)
    train_rows = tuple(trace for trace in traces if trace.split == DataSplit.TRAIN)
    validation_rows = tuple(
        trace for trace in traces if trace.split == DataSplit.VALIDATION
    )
    if not train_rows:
        raise ContractError("teacher bundle contains no training traces")
    if config.require_validation_split and not validation_rows:
        raise ContractError("teacher bundle contains no group-disjoint validation traces")
    train_dataset = TensorizedTeacherDataset(train_rows, records, features, config)
    # A zero-sized validation set is deliberately not represented: disabling the
    # gate permits dataset diagnostic work only. ``train_evidence_controller``
    # rejects this fallback, so it can never drive early stopping/model selection.
    validation_dataset = TensorizedTeacherDataset(
        validation_rows or train_rows, records, features, config
    )
    development_paths = (
        development_trace_bundle_dir,
        development_memory_bundle_dir,
        development_feature_bundle_path,
    )
    if any(value is not None for value in development_paths) and not all(
        value is not None for value in development_paths
    ):
        raise ContractError(
            "development trace, memory, and feature bundles must be supplied together"
        )
    development_dataset: TensorizedTeacherDataset | None = None
    development_trace_manifest: Mapping[str, Any] | None = None
    development_memory_manifest: Mapping[str, Any] | None = None
    development_features: ExplicitFeatureStore | None = None
    development_fingerprint: str | None = None
    if all(value is not None for value in development_paths):
        development_traces, development_trace_manifest = read_teacher_trace_bundle(
            development_trace_bundle_dir, purpose="development"  # type: ignore[arg-type]
        )
        development_records, development_memory_manifest = (
            read_compact_evidence_memory_bundle(
                development_memory_bundle_dir, purpose="development"  # type: ignore[arg-type]
            )
        )
        validate_development_sources(
            development_traces,
            development_records,
            development_trace_manifest,
            development_memory_manifest,
            freeze_manifest,
            expected_graph_binding=_graph_binding(trace_manifest, "trace manifest"),
        )
        assert_development_disjoint_from_build(
            traces, development_traces, development_records
        )
        development_features = ExplicitFeatureStore.read(
            development_feature_bundle_path  # type: ignore[arg-type]
        )
        if (
            development_features.query_dimension != features.query_dimension
            or development_features.evidence_dimension != features.evidence_dimension
        ):
            raise ContractError(
                "development features must use the same dimensions as training features"
            )
        if dict(development_features.encoder_manifest) != dict(features.encoder_manifest):
            raise ContractError(
                "development features must use the same frozen encoder manifest"
            )
        development_dataset = TensorizedTeacherDataset(
            development_traces, development_records, development_features, config
        )
        development_fingerprint = stable_sha256(
            {
                "purpose": "mp008_development_calibration_only",
                "trace_bundle": development_trace_manifest.get("logical_sha256"),
                "memory_bundle": development_memory_manifest.get("logical_sha256"),
                "teacher_freeze": freeze_hash,
                "feature_bundle": development_features.logical_sha256,
                "max_candidates": config.max_candidates,
                "max_cardinality": config.max_cardinality,
            }
        )
    fingerprint = stable_sha256(
        {
            "trace_bundle": trace_manifest.get("logical_sha256"),
            "memory_bundle": memory_manifest.get("logical_sha256"),
            "teacher_freeze": freeze_hash,
            "feature_bundle": features.logical_sha256,
            "max_candidates": config.max_candidates,
            "max_cardinality": config.max_cardinality,
        }
    )
    return PreparedTrainingData(
        train_dataset=train_dataset,
        validation_dataset=validation_dataset,
        development_dataset=development_dataset,
        trace_manifest=trace_manifest,
        memory_manifest=memory_manifest,
        development_trace_manifest=development_trace_manifest,
        development_memory_manifest=development_memory_manifest,
        teacher_freeze_manifest=freeze_manifest,
        feature_store=features,
        development_feature_store=development_features,
        input_fingerprint=fingerprint,
        development_fingerprint=development_fingerprint,
    )


__all__ = [
    "FEATURE_BUNDLE_SCHEMA",
    "ExplicitFeatureStore",
    "PreparedTrainingData",
    "TensorizationConfig",
    "TensorizedTeacherDataset",
    "assert_development_disjoint_from_build",
    "assert_group_disjoint_splits",
    "collate_teacher_batch",
    "prepare_training_data",
    "validate_development_sources",
    "validate_training_sources",
]
