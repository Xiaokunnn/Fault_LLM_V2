"""Deterministic training and checkpointing for the RP3 evidence controller."""

from __future__ import annotations

import json
import os
import platform
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifacts import canonical_json_bytes, file_sha256, stable_sha256
from .contracts import ContractError
from .dataset import PreparedTrainingData, collate_teacher_batch
from .losses import (
    EvidenceControllerTargets,
    LossWeights,
    compute_evidence_controller_loss,
)
from .model import (
    EvidenceControllerConfig,
    EvidenceControllerOutput,
    LightweightEvidenceController,
    require_torch,
)

try:
    import torch
    from torch.utils.data import DataLoader
except ImportError:  # pragma: no cover
    torch = None
    DataLoader = None


TRAINING_MANIFEST_SCHEMA = "rp3_lec_training_manifest_v1"
CHECKPOINT_SCHEMA = "rp3_lec_checkpoint_v1"
MAX_CONTROLLER_PARAMETERS = 50_000_000


@dataclass(frozen=True)
class TrainingConfig:
    epochs: int = 30
    batch_size: int = 16
    learning_rate: float = 3e-4
    weight_decay: float = 1e-4
    gradient_clip_norm: float = 1.0
    seed: int = 20260813
    device: str = "auto"
    num_workers: int = 0
    early_stopping_patience: int = 5
    temperatures: tuple[float, ...] = (1.0, 2.0, 4.0)
    expected_route_cost_weight: float = 1.0
    route_class_weights: tuple[float, ...] | None = None
    loss_weights: LossWeights = LossWeights()
    field_loss_normalization: str = "all_fields"
    record_field_diagnostics: bool = False
    hard_negative_support_weight: float = 0.0
    joint_contract_weight: float = 0.0
    hard_negative_reference_rate: float | None = None
    positive_step_guard: bool = False
    positive_guard_margin: float = 0.1
    positive_guard_backtracks: int = 8
    positive_guard_tolerance: float = 1e-7

    def __post_init__(self) -> None:
        import math
        if type(self.positive_step_guard) is not bool:
            raise ValueError("positive_step_guard must be boolean")
        if (not 0 < self.positive_guard_margin < 1 or type(self.positive_guard_backtracks) is not int
                or self.positive_guard_backtracks < 0 or not math.isfinite(self.positive_guard_tolerance)
                or self.positive_guard_tolerance < 0):
            raise ValueError("invalid positive guard constants")
        if any(not math.isfinite(x) or x < 0 for x in (self.hard_negative_support_weight, self.joint_contract_weight)):
            raise ValueError("joint auxiliary weights must be finite and nonnegative")
        if self.hard_negative_support_weight or self.joint_contract_weight:
            if self.hard_negative_reference_rate is None or not 0 < self.hard_negative_reference_rate <= 1:
                raise ValueError("joint training requires a frozen hard-negative train reference rate")
        if self.field_loss_normalization not in {"all_fields", "requested_balanced"}:
            raise ValueError("unknown field_loss_normalization")
        if type(self.record_field_diagnostics) is not bool:
            raise ValueError("record_field_diagnostics must be boolean")
        for name in ("epochs", "batch_size"):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be >= 1")
        if self.learning_rate <= 0 or self.weight_decay < 0:
            raise ValueError("learning_rate must be > 0 and weight_decay must be >= 0")
        if self.gradient_clip_norm < 0:
            raise ValueError("gradient_clip_norm must be >= 0")
        if self.num_workers != 0:
            raise ValueError(
                "deterministic RP3 training currently requires num_workers=0"
            )
        if self.early_stopping_patience < 0:
            raise ValueError("early_stopping_patience must be >= 0")
        if not self.temperatures or any(value <= 0 for value in self.temperatures):
            raise ValueError("temperatures must be non-empty and > 0")
        if self.expected_route_cost_weight < 0:
            raise ValueError("expected_route_cost_weight must be >= 0")
        if self.route_class_weights is not None:
            if len(self.route_class_weights) != 3 or any(
                value < 0 for value in self.route_class_weights
            ):
                raise ValueError("route_class_weights must contain three non-negative values")


def set_deterministic_seed(seed: int) -> None:
    """Configure Python/PyTorch determinism and recordable seed semantics."""

    require_torch()
    seed = int(seed)
    random.seed(seed)
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True


def resolve_device(requested: str) -> "torch.device":
    require_torch()
    value = str(requested).strip().lower()
    if value == "auto":
        value = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(value)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested for RP3 training but is unavailable")
    return device


def _targets_on_device(batch: Mapping[str, Any], device: "torch.device") -> EvidenceControllerTargets:
    return EvidenceControllerTargets(
        teacher_rank_scores=batch["teacher_rank_scores"].to(device),
        support_labels=batch["support_labels"].to(device),
        field_state_labels=batch["field_state_labels"].to(device),
        cardinality_labels=batch["cardinality_labels"].to(device),
        route_labels=batch["route_labels"].to(device),
        route_action_costs=batch["route_action_costs"].to(device),
        requested_field_mask=(batch["requested_field_mask"].to(device) if "requested_field_mask" in batch else None),
    )


def _select_rows(
    output: EvidenceControllerOutput,
    targets: EvidenceControllerTargets,
    indices: "torch.Tensor",
) -> tuple[EvidenceControllerOutput, EvidenceControllerTargets]:
    selected_output = EvidenceControllerOutput(
        rank_logits=output.rank_logits.index_select(0, indices),
        support_logits=output.support_logits.index_select(0, indices),
        field_state_logits=output.field_state_logits.index_select(0, indices),
        cardinality_logits=output.cardinality_logits.index_select(0, indices),
        route_logits=output.route_logits.index_select(0, indices),
        availability_mask=output.availability_mask.index_select(0, indices),
    )
    selected_targets = EvidenceControllerTargets(
        teacher_rank_scores=targets.teacher_rank_scores.index_select(0, indices),
        support_labels=targets.support_labels.index_select(0, indices),
        field_state_labels=targets.field_state_labels.index_select(0, indices),
        cardinality_labels=targets.cardinality_labels.index_select(0, indices),
        route_labels=targets.route_labels.index_select(0, indices),
        route_action_costs=(
            targets.route_action_costs.index_select(0, indices)
            if targets.route_action_costs is not None
            else None
        ),
        requested_field_mask=(targets.requested_field_mask.index_select(0, indices)
                              if targets.requested_field_mask is not None else None),
    )
    return selected_output, selected_targets


def _run_epoch(
    model: LightweightEvidenceController,
    loader: "DataLoader",
    config: TrainingConfig,
    device: "torch.device",
    optimizer: "torch.optim.Optimizer | None",
    positive_guard: Any = None,
) -> dict[str, Any]:
    training = optimizer is not None
    model.train(training)
    sums = {
        name: 0.0
        for name in (
            "total",
            "ranking",
            "support",
            "field_state",
            "cardinality",
            "route",
            "intervention_augmented_supervision",
            "calibration",
        )
    }
    row_count = 0
    guard_steps = []
    audit = None
    if config.record_field_diagnostics:
        from .field_audit import EpochFieldAudit
        audit = EpochFieldAudit(loader.dataset)
    route_weights = (
        torch.tensor(config.route_class_weights, dtype=torch.float32, device=device)
        if config.route_class_weights is not None
        else None
    )
    context = torch.enable_grad if training else torch.no_grad
    with context():
        for batch in loader:
            query = batch["query_features"].to(device)
            candidates = batch["candidate_features"].to(device)
            mask = batch["availability_mask"].to(device)
            budget = batch["selection_budget"].to(device)
            targets = _targets_on_device(batch, device)
            if training:
                optimizer.zero_grad(set_to_none=True)
            output = model(query, candidates, mask, budget)
            intervention_augmented_supervision = None
            intervention_indices = [
                index
                for index, flag in enumerate(batch["is_intervention"])
                if bool(flag)
            ]
            if intervention_indices:
                index_tensor = torch.tensor(
                    intervention_indices, dtype=torch.long, device=device
                )
                intervention_augmented_supervision = _select_rows(
                    output, targets, index_tensor
                )
            losses = compute_evidence_controller_loss(
                output,
                targets,
                weights=config.loss_weights,
                temperatures=config.temperatures,
                route_class_weights=route_weights,
                expected_route_cost_weight=config.expected_route_cost_weight,
                field_loss_normalization=config.field_loss_normalization,
                intervention_pair=intervention_augmented_supervision,
            )
            if not torch.isfinite(losses.total):
                raise RuntimeError("non-finite RP3 training loss; aborting fail-closed")
            if config.hard_negative_support_weight or config.joint_contract_weight:
                from .joint_contract import joint_auxiliary_losses
                hard, semantic = joint_auxiliary_losses(
                    output, batch, reference_rate=config.hard_negative_reference_rate
                )
                losses.total = (losses.total + config.hard_negative_support_weight * hard
                                + config.joint_contract_weight * semantic)
                if not torch.isfinite(losses.total):
                    raise RuntimeError("non-finite joint-contract objective")
                for key, value in (("hard_negative_support", hard), ("joint_contract", semantic)):
                    sums[key] = sums.get(key, 0.0) + float(value.detach().cpu()) * int(query.shape[0])
            if audit is not None:
                audit.observe(output, batch)
            if training:
                losses.total.backward()
                if config.gradient_clip_norm > 0:
                    torch.nn.utils.clip_grad_norm_(
                        model.parameters(), config.gradient_clip_norm
                    )
                if positive_guard is None:
                    optimizer.step()
                else:
                    guard_steps.append(positive_guard.step(model, optimizer))
            batch_size = int(query.shape[0])
            row_count += batch_size
            for name, value in losses.as_dict(detach=True).items():
                metric_name = (
                    "intervention_augmented_supervision"
                    if name == "intervention"
                    else name
                )
                sums[metric_name] += float(value.cpu().item()) * batch_size
    if row_count == 0:
        raise ContractError("an RP3 epoch cannot operate on an empty dataset")
    metrics = {name: value / row_count for name, value in sums.items()}
    if audit is not None:
        metrics["field_diagnostics"] = audit.summary()
    if positive_guard is not None:
        metrics["positive_guard_steps"] = guard_steps
    return metrics


def _cpu_state_dict(model: LightweightEvidenceController) -> dict[str, Any]:
    return {
        name: value.detach().cpu().contiguous()
        for name, value in model.state_dict().items()
    }


def _write_checkpoint(
    path: Path,
    *,
    model: LightweightEvidenceController,
    optimizer: "torch.optim.Optimizer",
    epoch: int,
    validation_loss: float,
    model_config: EvidenceControllerConfig,
    training_config: TrainingConfig,
    input_fingerprint: str,
) -> None:
    payload = {
        "schema": CHECKPOINT_SCHEMA,
        "model_state_dict": _cpu_state_dict(model),
        "optimizer_state_dict": optimizer.state_dict(),
        "epoch": int(epoch),
        "validation_loss": float(validation_loss),
        "model_config": asdict(model_config),
        "training_config": {
            **asdict(training_config),
            "loss_weights": asdict(training_config.loss_weights),
        },
        "input_fingerprint": input_fingerprint,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary, _use_new_zipfile_serialization=False)
    temporary.replace(path)


def load_controller_checkpoint(
    checkpoint_path: str | Path,
    *,
    expected_input_fingerprint: str | None = None,
    map_location: str = "cpu",
) -> tuple[LightweightEvidenceController, dict[str, Any]]:
    """Load a code-owned checkpoint and validate its declared schema/binding."""

    require_torch()
    try:
        payload = torch.load(
            checkpoint_path, map_location=map_location, weights_only=False
        )
    except TypeError:  # Compatibility with older PyTorch releases.
        payload = torch.load(checkpoint_path, map_location=map_location)
    if not isinstance(payload, Mapping) or payload.get("schema") != CHECKPOINT_SCHEMA:
        raise ContractError("checkpoint is not an RP3 LEC checkpoint")
    fingerprint = str(payload.get("input_fingerprint", ""))
    if expected_input_fingerprint is not None and fingerprint != expected_input_fingerprint:
        raise ContractError("checkpoint input fingerprint does not match frozen inputs")
    config = EvidenceControllerConfig(**dict(payload.get("model_config", {})))
    model = LightweightEvidenceController(config)
    model.load_state_dict(payload["model_state_dict"], strict=True)
    return model, dict(payload)


def train_evidence_controller(
    prepared: PreparedTrainingData,
    *,
    model_config: EvidenceControllerConfig,
    training_config: TrainingConfig,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Train on build-set rows and select the model on build-set validation.

    ``prepared.development_dataset`` is intentionally never passed to a
    ``DataLoader`` here.  MP008 is only registered in the manifest as an input to
    later threshold, routing, and post-quantization calibration procedures.
    """

    require_torch()
    if model_config.query_dim != prepared.feature_store.query_dimension:
        raise ContractError("model query_dim disagrees with the feature bundle")
    if model_config.evidence_dim != prepared.feature_store.evidence_dimension:
        raise ContractError("model evidence_dim disagrees with the feature bundle")
    if model_config.max_cardinality != prepared.train_dataset.config.max_cardinality:
        raise ContractError("model and tensorizer cardinality bounds disagree")
    if not prepared.train_dataset.config.require_validation_split:
        raise ContractError(
            "model training requires group-disjoint build-set validation; "
            "require_validation_split cannot be disabled"
        )
    if any(
        trace.split.value != "train" for trace in prepared.train_dataset.traces
    ):
        raise ContractError("gradient dataset contains a non-train trace")
    if any(
        trace.split.value != "validation"
        for trace in prepared.validation_dataset.traces
    ):
        raise ContractError(
            "early stopping/model selection requires build-set validation traces"
        )
    if prepared.development_dataset is not None:
        if prepared.development_fingerprint is None:
            raise ContractError("development dataset has no frozen fingerprint")
        if prepared.development_feature_store is None:
            raise ContractError("development dataset has no explicit feature store")
        if any(
            trace.split.value != "development"
            for trace in prepared.development_dataset.traces
        ):
            raise ContractError("non-development trace reached the MP008 calibration set")
    if training_config.hard_negative_support_weight or training_config.joint_contract_weight:
        from .joint_contract import hard_empty_rows
        hard_count = 0
        for i in range(len(prepared.train_dataset)):
            row = prepared.train_dataset[i]
            requested = row["requested_field_mask"]
            if int(requested.sum()) != 1:
                raise ContractError("joint training requires single-role supervision")
            eligible = row["requested_candidate_mask"] & row["availability_mask"]
            hard_count += int(hard_empty_rows(row["support_labels"][None], eligible[None],
                                            row["cardinality_labels"][requested])[0])
        actual_rate = hard_count / len(prepared.train_dataset)
        if abs(actual_rate - training_config.hard_negative_reference_rate) > 1e-12:
            raise ContractError("hard-negative reference rate differs from frozen training data")
    output = Path(output_dir)
    manifest_path = output / "training_manifest.json"
    checkpoint_path = output / "best_controller.pt"
    history_path = output / "training_history.jsonl"
    if not overwrite and any(path.exists() for path in (manifest_path, checkpoint_path, history_path)):
        raise RuntimeError("refusing to overwrite an existing RP3 training run")
    output.mkdir(parents=True, exist_ok=True)

    set_deterministic_seed(training_config.seed)
    device = resolve_device(training_config.device)
    model = LightweightEvidenceController(model_config).to(device)
    parameter_count = model.parameter_count()
    if parameter_count >= MAX_CONTROLLER_PARAMETERS:
        raise ContractError(
            "RP3 LEC must remain below 50M parameters; "
            f"constructed model has {parameter_count:,}"
        )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=training_config.learning_rate,
        weight_decay=training_config.weight_decay,
    )
    positive_guard = None
    if training_config.positive_step_guard:
        from .positive_guard import PositiveStepGuard
        reference = collate_teacher_batch([prepared.train_dataset[i] for i in range(len(prepared.train_dataset))])
        reference = {key: value.to(device) if isinstance(value, torch.Tensor) else value for key, value in reference.items()}
        positive_guard = PositiveStepGuard(reference, margin=training_config.positive_guard_margin,
            backtracks=training_config.positive_guard_backtracks, tolerance=training_config.positive_guard_tolerance)
    generator = torch.Generator()
    generator.manual_seed(training_config.seed)
    train_loader = DataLoader(
        prepared.train_dataset,
        batch_size=training_config.batch_size,
        shuffle=True,
        generator=generator,
        num_workers=0,
        collate_fn=collate_teacher_batch,
    )
    validation_loader = DataLoader(
        prepared.validation_dataset,
        batch_size=training_config.batch_size,
        shuffle=False,
        num_workers=0,
        collate_fn=collate_teacher_batch,
    )

    history: list[dict[str, Any]] = []
    best_loss = float("inf")
    best_epoch = 0
    stale_epochs = 0
    for epoch in range(1, training_config.epochs + 1):
        train_metrics = _run_epoch(
            model, train_loader, training_config, device, optimizer, positive_guard
        )
        validation_metrics = _run_epoch(
            model, validation_loader, training_config, device, None
        )
        row = {
            "epoch": epoch,
            "train": train_metrics,
            "validation": validation_metrics,
        }
        history.append(row)
        validation_loss = validation_metrics["total"]
        if validation_loss < best_loss:
            best_loss = validation_loss
            best_epoch = epoch
            stale_epochs = 0
            _write_checkpoint(
                checkpoint_path,
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                validation_loss=validation_loss,
                model_config=model_config,
                training_config=training_config,
                input_fingerprint=prepared.input_fingerprint,
            )
        else:
            stale_epochs += 1
        if (
            training_config.early_stopping_patience > 0
            and stale_epochs >= training_config.early_stopping_patience
        ):
            break

    history_payload = b"".join(canonical_json_bytes(row) for row in history)
    history_path.write_bytes(history_payload)
    checkpoint_hash = file_sha256(checkpoint_path)
    history_hash = file_sha256(history_path)
    manifest = {
        "schema": TRAINING_MANIFEST_SCHEMA,
        "status": "trained_unquantized",
        "input_fingerprint": prepared.input_fingerprint,
        "teacher_graph": prepared.trace_manifest.get("teacher_graph"),
        "teacher_replay_id": prepared.trace_manifest.get("teacher_replay_id"),
        "teacher_replay_sha256": prepared.trace_manifest.get("teacher_replay_sha256"),
        "trace_bundle_sha256": prepared.trace_manifest.get("logical_sha256"),
        "memory_bundle_sha256": prepared.memory_manifest.get("logical_sha256"),
        "feature_bundle_sha256": prepared.feature_store.logical_sha256,
        "feature_encoder_manifest": dict(prepared.feature_store.encoder_manifest),
        "model_config": asdict(model_config),
        "training_config": {
            **asdict(training_config),
            "loss_weights": asdict(training_config.loss_weights),
        },
        "parameter_report": {
            **model.parameter_report(),
            "required_strictly_below": MAX_CONTROLLER_PARAMETERS,
            "gate_passed": True,
        },
        "objective_semantics": {
            "intervention_augmented_supervision": (
                "additional teacher-target supervision on perturbation rows; this "
                "is not a parent-paired directional consistency loss"
            )
        },
        "determinism": {
            "seed": training_config.seed,
            "torch_deterministic_algorithms": True,
            "dataloader_workers": 0,
            "shuffle_generator_seed": training_config.seed,
        },
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "device_type": device.type,
        },
        "train_trace_count": len(prepared.train_dataset),
        "validation_trace_count": len(prepared.validation_dataset),
        "data_roles": {
            "gradient_training": {
                "corpus": "build_set_only",
                "split": "train",
                "trace_count": len(prepared.train_dataset),
            },
            "early_stopping_and_model_selection": {
                "corpus": "build_set_only",
                "split": "validation",
                "trace_count": len(prepared.validation_dataset),
            },
            "threshold_route_and_post_quantization_calibration": {
                "corpus": "MP008_only",
                "split": "development",
                "attached": prepared.development_dataset is not None,
                "trace_count": (
                    len(prepared.development_dataset)
                    if prepared.development_dataset is not None
                    else 0
                ),
                "included_in_gradient_training": False,
                "used_for_early_stopping_or_model_selection": False,
            },
        },
        "development_set": {
            "attached": prepared.development_dataset is not None,
            "purpose": (
                "threshold_route_and_post_quantization_calibration_only"
            ),
            "input_fingerprint": prepared.development_fingerprint,
            "trace_bundle_sha256": (
                prepared.development_trace_manifest.get("logical_sha256")
                if prepared.development_trace_manifest is not None
                else None
            ),
            "memory_bundle_sha256": (
                prepared.development_memory_manifest.get("logical_sha256")
                if prepared.development_memory_manifest is not None
                else None
            ),
            "feature_bundle_sha256": (
                prepared.development_feature_store.logical_sha256
                if prepared.development_feature_store is not None
                else None
            ),
            "feature_encoder_manifest": (
                dict(prepared.development_feature_store.encoder_manifest)
                if prepared.development_feature_store is not None
                else None
            ),
            "trace_count": (
                len(prepared.development_dataset)
                if prepared.development_dataset is not None
                else 0
            ),
            "metrics": None,
        },
        "calibration_interfaces": {
            "answer_abstain_thresholds": {
                "status": "pending_not_run",
                "required_split": "development",
                "artifact": None,
            },
            "cost_sensitive_route": {
                "status": "pending_not_run",
                "required_split": "development",
                "artifact": None,
            },
            "post_quantization_thresholds": {
                "status": "pending_requires_int8_artifact",
                "required_split": "development",
                "artifact": None,
            },
        },
        "best_epoch": best_epoch,
        "best_validation_loss": best_loss,
        "checkpoint_file": checkpoint_path.name,
        "checkpoint_sha256": checkpoint_hash,
        "history_file": history_path.name,
        "history_sha256": history_hash,
        "human_expert_reviewed": False,
        "supervision_boundary": "teacher_generated_not_expert_ground_truth",
        "quantized": False,
    }
    manifest["logical_sha256"] = stable_sha256(manifest)
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    return manifest


__all__ = [
    "CHECKPOINT_SCHEMA",
    "TRAINING_MANIFEST_SCHEMA",
    "TrainingConfig",
    "load_controller_checkpoint",
    "resolve_device",
    "set_deterministic_seed",
    "train_evidence_controller",
]
