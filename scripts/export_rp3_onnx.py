#!/usr/bin/env python3
"""Export an RP3 LEC checkpoint to verified, explicitly unquantized ONNX."""

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
from src.research_point_3.onnx_export import (  # noqa: E402
    build_int8_calibration_input_bundle,
    export_controller_onnx,
)


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export FP32 ONNX and optional representative INT8 inputs"
    )
    parser.add_argument("--training-manifest", required=True)
    parser.add_argument(
        "--memory-manifest",
        required=True,
        help="exact compact evidence-memory manifest used for deployment binding",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-candidates", type=int, default=32)
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--calibration-config",
        help=(
            "optional training-data JSON config used only to export representative "
            "INT8 inputs; it does not quantize the model"
        ),
    )
    parser.add_argument("--calibration-max-samples", type=int, default=128)
    parser.add_argument("--calibration-batch-size", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260813)
    args = parser.parse_args()

    output_dir = _path(args.output_dir)
    onnx_manifest = export_controller_onnx(
        training_manifest_path=_path(args.training_manifest),
        memory_manifest_path=_path(args.memory_manifest),
        output_dir=output_dir,
        max_candidates=args.max_candidates,
        opset_version=args.opset,
        overwrite=args.overwrite,
    )
    result = {
        "onnx_status": onnx_manifest["status"],
        "onnx_manifest": str(output_dir / "onnx_export_manifest.json"),
        "quantization_completed": False,
    }

    if args.calibration_config:
        values = json.loads(_path(args.calibration_config).read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise ValueError("calibration config must be a JSON object")
        tensorization = TensorizationConfig(**dict(values.get("tensorization", {})))
        if tensorization.max_candidates != args.max_candidates:
            raise ValueError(
                "calibration tensorization max_candidates must match ONNX fixed width"
            )
        prepared = prepare_training_data(
            trace_bundle_dir=_path(values["trace_bundle_dir"]),
            memory_bundle_dir=_path(values["memory_bundle_dir"]),
            teacher_freeze_path=_path(values["teacher_freeze_path"]),
            feature_bundle_path=_path(values["feature_bundle_path"]),
            config=tensorization,
            development_trace_bundle_dir=_path(values["development_trace_bundle_dir"]),
            development_memory_bundle_dir=_path(values["development_memory_bundle_dir"]),
            development_feature_bundle_path=_path(
                values["development_feature_bundle_path"]
            ),
        )
        if prepared.input_fingerprint != onnx_manifest["input_fingerprint"]:
            raise ValueError(
                "build-set identity does not match the trained model input fingerprint"
            )
        if prepared.development_dataset is None or prepared.development_fingerprint is None:
            raise ValueError("INT8 calibration requires the separate MP008 development bundle")
        calibration_manifest = build_int8_calibration_input_bundle(
            prepared.development_dataset,
            output_dir=output_dir,
            source_input_fingerprint=prepared.development_fingerprint,
            max_samples=args.calibration_max_samples,
            batch_size=args.calibration_batch_size,
            seed=args.seed,
            overwrite=args.overwrite,
        )
        result.update(
            {
                "calibration_status": calibration_manifest["status"],
                "calibration_manifest": str(
                    output_dir / "int8_calibration_manifest.json"
                ),
            }
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
