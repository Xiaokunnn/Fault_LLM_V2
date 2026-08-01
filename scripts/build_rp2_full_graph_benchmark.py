#!/usr/bin/env python3
"""Build the leakage-safe RP2 development benchmark over the complete release graph."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.dataset import (  # noqa: E402
    SilverQuery,
    load_evidence_candidates,
    load_silver_queries,
    write_benchmark,
)

HELD_OUT = {"MP009", "MP010", "MP011", "MP012", "MP013"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-root", default="data/kg/marine_pump/triples/KG_v1_validated")
    parser.add_argument("--cq-evaluation", default="results/experiments/research_point_1/cq_v1/cq_v1_evaluation.json")
    parser.add_argument("--output-dir", default="data/kg/marine_pump/silver_evidencebench/rp2_full_graph_development_v2")
    args = parser.parse_args()

    candidates = load_evidence_candidates(ROOT / args.graph_root)
    leaked = sorted({row.doc_id for row in candidates} & HELD_OUT)
    if leaked:
        raise RuntimeError(f"Held-out documents entered the release graph: {leaked}")
    queries = [
        SilverQuery(
            query_id=row.query_id,
            question_zh=row.question_zh,
            fault_id=row.fault_id,
            fault_name_zh=row.fault_name_zh,
            role=row.role,
            relevant_evidence_ids=row.relevant_evidence_ids,
            candidate_evidence_ids=(),
            label_status=row.label_status,
        )
        for row in load_silver_queries(ROOT / args.cq_evaluation)
    ]
    write_benchmark(
        queries,
        candidates,
        ROOT / args.output_dir,
        manifest_overrides={
            "benchmark_id": "marine_pump_rp2_full_graph_development_v2",
            "scope": "development_CQ_over_complete_frozen_release_graph",
            "full_graph_retrieval_required": True,
            "positive_seeded_candidate_pool": False,
            "held_out_documents_forbidden": sorted(HELD_OUT),
        },
    )
    print(
        f"[RP2 benchmark v2] queries={len(queries)}, "
        f"answerable={sum(bool(row.relevant_evidence_ids) for row in queries)}, "
        f"full_graph_candidates={len(candidates)}, heldout_leakage=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
