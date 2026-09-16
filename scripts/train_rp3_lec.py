#!/usr/bin/env python3
"""Train the RP3 lightweight evidence controller from frozen explicit features."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research_point_3.dataset import (  # noqa: E402
    TensorizationConfig,
    prepare_training_data,
)
from src.research_point_3.losses import LossWeights  # noqa: E402
from src.research_point_3.model import EvidenceControllerConfig  # noqa: E402
from src.research_point_3.training import (  # noqa: E402
    TrainingConfig,
    train_evidence_controller,
)


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _config(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("RP3 training config must be a JSON object")
    return value


def validate_config_schema(values: dict) -> None:
    """Reject a planning-only or misspelled config before loading artifacts."""

    required = {
        "trace_bundle_dir",
        "memory_bundle_dir",
        "teacher_freeze_path",
        "feature_bundle_path",
        "tensorization",
        "model",
        "training",
    }
    missing = sorted(required - set(values))
    if missing:
        raise ValueError("RP3 training config is missing: " + ", ".join(missing))
    allowed_model = {
        "query_dim",
        "evidence_dim",
        "hidden_dim",
        "max_cardinality",
        "dropout",
        "num_card_fields",
        "num_field_states",
        "num_route_actions",
    }
    allowed_training = set(TrainingConfig.__dataclass_fields__)
    allowed_tensorization = set(TensorizationConfig.__dataclass_fields__)
    for section, allowed in (
        ("model", allowed_model),
        ("training", allowed_training),
        ("tensorization", allowed_tensorization),
    ):
        value = values.get(section)
        if not isinstance(value, dict):
            raise ValueError(f"{section} config must be a JSON object")
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(
                f"unknown RP3 {section} config keys: " + ", ".join(unknown)
            )


def _development_paths(values: dict) -> dict[str, Path | None]:
    """Accept a nested development block while preserving flat-key compatibility."""

    nested = values.get("development", {})
    if nested is None:
        nested = {}
    if not isinstance(nested, dict):
        raise ValueError("development config must be a JSON object")
    aliases = {
        "development_trace_bundle_dir": "trace_bundle_dir",
        "development_memory_bundle_dir": "memory_bundle_dir",
        "development_feature_bundle_path": "feature_bundle_path",
    }
    result: dict[str, Path | None] = {}
    for output_name, nested_name in aliases.items():
        raw = values.get(output_name, nested.get(nested_name))
        result[output_name] = _path(raw) if raw is not None else None
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train RP3 LEC from frozen teacher traces and externally precomputed "
            "features. This command never creates embeddings or calls an LLM."
        )
    )
    parser.add_argument("--config", required=True, help="training JSON config")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--bootstrap-without-development", action="store_true",
        help="Train preliminary heads without MP008; not deployable until MP008 is attached and calibrated")
    args = parser.parse_args()

    config_path = _path(args.config)
    values = _config(config_path)
    validate_config_schema(values)
    tensorization_values = dict(values.get("tensorization", {}))
    model_values = dict(values.get("model", {}))
    training_values = dict(values.get("training", {}))
    if "loss_weights" in training_values:
        training_values["loss_weights"] = LossWeights(
            **dict(training_values["loss_weights"])
        )
    if "temperatures" in training_values:
        training_values["temperatures"] = tuple(training_values["temperatures"])
    if training_values.get("route_class_weights") is not None:
        training_values["route_class_weights"] = tuple(
            training_values["route_class_weights"]
        )

    tensorization = TensorizationConfig(**tensorization_values)
    prepared = prepare_training_data(
        trace_bundle_dir=_path(values["trace_bundle_dir"]),
        memory_bundle_dir=_path(values["memory_bundle_dir"]),
        teacher_freeze_path=_path(values["teacher_freeze_path"]),
        feature_bundle_path=_path(values["feature_bundle_path"]),
        config=tensorization,
        **({} if args.bootstrap_without_development else _development_paths(values)),
    )
    model_values.setdefault("query_dim", prepared.feature_store.query_dimension)
    model_values.setdefault("evidence_dim", prepared.feature_store.evidence_dimension)
    model_values.setdefault("max_cardinality", tensorization.max_cardinality)
    manifest = train_evidence_controller(
        prepared,
        model_config=EvidenceControllerConfig(**model_values),
        training_config=TrainingConfig(**training_values),
        output_dir=_path(args.output_dir),
        overwrite=args.overwrite,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "best_epoch": manifest["best_epoch"],
                "best_validation_loss": manifest["best_validation_loss"],
                "development_attached": manifest["development_set"]["attached"],
                "calibration_status": manifest["calibration_interfaces"],
                "manifest": str(_path(args.output_dir) / "training_manifest.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
