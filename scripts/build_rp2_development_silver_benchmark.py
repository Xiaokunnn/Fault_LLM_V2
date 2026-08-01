#!/usr/bin/env python3
"""Build the RP2 development-only Silver evidence candidate pools."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_point_2.dataset import (  # noqa: E402
    build_candidate_pools,
    load_evidence_candidates,
    load_silver_queries,
    write_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graph-root",
        default="data/kg/marine_pump/triples/KG_v1_validated",
    )
    parser.add_argument(
        "--cq-evaluation",
        default="results/experiments/research_point_1/cq_v1/cq_v1_evaluation.json",
    )
    parser.add_argument(
        "--output-dir",
        default="data/kg/marine_pump/silver_evidencebench/rp2_development_v1",
    )
    parser.add_argument("--pool-size", type=int, default=64)
    args = parser.parse_args()

    candidates = load_evidence_candidates(ROOT / args.graph_root)
    queries = load_silver_queries(ROOT / args.cq_evaluation)
    pooled = build_candidate_pools(queries, candidates, pool_size=args.pool_size)
    write_benchmark(pooled, candidates, ROOT / args.output_dir)
    print(
        f"[RP2 benchmark] queries={len(pooled)}, "
        f"answerable={sum(bool(q.relevant_evidence_ids) for q in pooled)}, "
        f"candidates={len(candidates)}, pool_size={args.pool_size}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
