#!/usr/bin/env python3
"""Build or validate the BGE-M3 evidence index used by RP2 GraphRAG v2."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.dataset import load_benchmark_candidates, load_evidence_candidates  # noqa: E402
from research_point_2.dense_index import DenseEvidenceIndex  # noqa: E402
from research_point_2.local_models import BgeM3Encoder, model_file_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/rp2_graphrag_v2_development.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    graph_root = ROOT / config["graph_root"]
    model_path = ROOT / config["embedding"]["model_path"]
    output = ROOT / config["embedding"]["index_dir"]
    index_source = config["embedding"].get("index_source", "primary_graph")
    candidates = (
        load_benchmark_candidates(ROOT / config["benchmark_dir"])
        if index_source == "benchmark_candidates"
        else load_evidence_candidates(graph_root)
    )
    print(f"[RP2 index] graph={graph_root}, candidates={len(candidates)}", flush=True)
    if not candidates:
        raise RuntimeError(
            "RP2 evidence candidate corpus is empty; stop before building a dense index"
        )
    if args.dry_run:
        print(f"[RP2 index] dry-run: model_exists={model_path.is_dir()}, output={output}", flush=True)
        return 0
    if not model_path.is_dir():
        raise FileNotFoundError(f"BGE-M3 model directory not found: {model_path}")
    if (output / "manifest.json").exists() and not args.force:
        print("[RP2 index] existing index reused; pass --force to rebuild", flush=True)
        return 0
    started = time.perf_counter()
    encoder = BgeM3Encoder(
        model_path,
        batch_size=int(config["embedding"]["batch_size"]),
        max_length=int(config["embedding"]["max_length"]),
        device=config["embedding"].get("device"),
        require_cuda=bool(
            args.require_cuda or config.get("runtime", {}).get("require_cuda")
        ),
    )
    print("[RP2 index] loading BGE-M3 and encoding evidence ...", flush=True)
    index = DenseEvidenceIndex.build(candidates, encoder)
    index.save(
        output,
        metadata={
            "protocol_id": config["protocol_id"],
            "graph_root": config["graph_root"],
            "index_source": index_source,
            "benchmark_dir": config.get("benchmark_dir") if index_source == "benchmark_candidates" else None,
            "model_manifest": model_file_manifest(model_path),
            "runtime_manifest": encoder.runtime_manifest,
            "embedding_device": encoder.device,
            "label_policy": "Silver only; never Gold",
        },
    )
    print(f"[RP2 index] completed: rows={len(candidates)}, elapsed={time.perf_counter()-started:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
