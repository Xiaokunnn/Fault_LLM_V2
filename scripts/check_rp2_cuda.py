#!/usr/bin/env python3
"""Fail-closed CUDA preflight for formal research-point-2 server runs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.local_models import cuda_runtime_manifest  # noqa: E402


def main() -> int:
    manifest = cuda_runtime_manifest(require_cuda=True)
    import torch

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
