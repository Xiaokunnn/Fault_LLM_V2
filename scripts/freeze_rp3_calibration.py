#!/usr/bin/env python3
"""Freeze already-fitted MP008 post-quantization LEC thresholds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research_point_3.calibration import (  # noqa: E402
    write_calibration_manifest_from_export,
)


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze thresholds fitted offline on MP008 after INT8 quantization; "
            "this command does not fit thresholds or run a model"
        )
    )
    parser.add_argument("--onnx-export-manifest", required=True)
    parser.add_argument("--quantized-model", required=True)
    parser.add_argument("--support-threshold", required=True, type=float)
    parser.add_argument("--minimum-route-confidence", required=True, type=float)
    parser.add_argument("--metrics-json", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    metrics = json.loads(_path(args.metrics_json).read_text(encoding="utf-8"))
    if not isinstance(metrics, dict):
        raise ValueError("metrics JSON must be an object")
    manifest = write_calibration_manifest_from_export(
        _path(args.output),
        support_threshold=args.support_threshold,
        minimum_route_confidence=args.minimum_route_confidence,
        quantized_model_path=_path(args.quantized_model),
        onnx_export_manifest_path=_path(args.onnx_export_manifest),
        metrics=metrics,
        overwrite=args.overwrite,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
