from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _training_cli_module():
    path = ROOT / "scripts" / "train_rp3_lec.py"
    spec = importlib.util.spec_from_file_location("train_rp3_lec", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_training_config_matches_cli_constructor_contracts() -> None:
    module = _training_cli_module()
    config = json.loads(
        (ROOT / "configs" / "research_point_3" / "lec_train_v1.json").read_text(
            encoding="utf-8"
        )
    )
    module.validate_config_schema(config)
    module.TensorizationConfig(**config["tensorization"])
    module.EvidenceControllerConfig(**config["model"])
    training = dict(config["training"])
    training["loss_weights"] = module.LossWeights(**training["loss_weights"])
    training["temperatures"] = tuple(training["temperatures"])
    module.TrainingConfig(**training)


def test_augmented_config_changes_only_prespecified_build_inputs() -> None:
    module = _training_cli_module()
    directory = ROOT / "configs" / "research_point_3"
    base = json.loads((directory / "lec_train_v1.json").read_text(encoding="utf-8"))
    augmented = json.loads(
        (directory / "lec_train_augmented_v1.json").read_text(encoding="utf-8")
    )
    module.validate_config_schema(augmented)
    assert augmented["training"] == base["training"]
    assert augmented["model"] == base["model"]
    assert augmented["tensorization"] == base["tensorization"]
    assert augmented["development_trace_bundle_dir"] == base["development_trace_bundle_dir"]
    assert augmented["development_memory_bundle_dir"] == base["development_memory_bundle_dir"]
    assert augmented["development_feature_bundle_path"] == base["development_feature_bundle_path"]
    assert augmented["corpus_policy"] == base["corpus_policy"]
    assert augmented["trace_bundle_dir"].endswith("traces/augmented_training")
    assert augmented["feature_bundle_path"].endswith("augmented_training_features.json")
