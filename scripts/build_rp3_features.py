#!/usr/bin/env python3
"""Export deterministic CPU features from governed trace/memory bundles."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.research_point_3.artifacts import read_teacher_trace_bundle, read_compact_evidence_memory_bundle, _write_immutable, canonical_json_bytes
from src.research_point_3.dataset import ExplicitFeatureStore
from src.research_point_3.features import ENCODER_MANIFEST, query_vector, evidence_vector

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--traces", required=True)
    p.add_argument("--memory", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    traces, tm = read_teacher_trace_bundle(args.traces)
    records, mm = read_compact_evidence_memory_bundle(args.memory)
    if tm["teacher_graph"] != mm["teacher_graph"] or tm["purpose"] != mm["purpose"]:
        raise ValueError("trace/memory graph or purpose mismatch")
    result = ExplicitFeatureStore.build_payload(
        query_features={t.trace_id: query_vector(t.query) for t in traces},
        evidence_features={r.evidence_id: evidence_vector(r) for r in records},
        query_dimension=256, evidence_dimension=288, encoder_manifest=ENCODER_MANIFEST,
    )
    ExplicitFeatureStore.from_dict(result)
    print(_write_immutable(Path(args.output), canonical_json_bytes(result)))

if __name__ == "__main__":
    main()
