#!/usr/bin/env python3
"""Fail-closed CUDA preflight for formal research-point-2 server runs."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.local_models import cuda_runtime_manifest  # noqa: E402


def main() -> int:
    manifest = cuda_runtime_manifest(require_cuda=True)
    import torch

    version_match = re.match(r"(\d+)\.(\d+)", str(torch.__version__))
    torch_version = (
        tuple(int(value) for value in version_match.groups())
        if version_match else (0, 0)
    )
    bge_root = ROOT / "data/model/BAAI-bge-m3"
    has_bin_weights = any(bge_root.rglob("pytorch_model*.bin"))
    has_safe_weights = any(bge_root.rglob("*.safetensors"))
    manifest["bge_weight_format"] = (
        "safetensors" if has_safe_weights else "pytorch_bin" if has_bin_weights else "unknown"
    )
    if has_bin_weights and not has_safe_weights and torch_version < (2, 6):
        raise RuntimeError(
            f"BGE-M3 uses pytorch_model.bin but torch={torch.__version__}. "
            "Current Transformers requires torch>=2.6 for this weight format. "
            "Install the repository's documented torch 2.6 CUDA wheel before running RP2."
        )

    device = torch.device("cuda:0")
    left = torch.randn((1024, 1024), device=device)
    right = left @ left
    torch.cuda.synchronize()
    manifest["probe_tensor_device"] = str(right.device)
    manifest["probe_peak_memory_bytes"] = int(torch.cuda.max_memory_allocated(0))
    print("[RP2 CUDA] preflight passed")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
