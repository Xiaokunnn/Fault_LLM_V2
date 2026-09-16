#!/usr/bin/env python3
"""Rebuild/verify strict208 BGE index and replay RP2 on a model-capable server."""
from __future__ import annotations
import argparse
import gc
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research_point_3.artifacts import _write_immutable, canonical_json_bytes, canonical_jsonl_bytes, normalized_text_sha256, stable_sha256
from src.research_point_3.teacher_runner import replay_candidates, verify_selection, compile_candidate_row

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=0, help="isolated smoke; never freezes formal artifacts")
    p.add_argument("--retrieval-only", action="store_true")
    args = p.parse_args()
    if args.limit < 0:
        p.error("limit must be non-negative")
    import os
    os.chdir(ROOT)
    from dataclasses import replace
    from src.research_point_2.dataset import EvidenceCandidate, SilverQuery, load_evidence_candidates
    from src.research_point_2.dense_index import DenseEvidenceIndex
    from src.research_point_2.local_models import BgeM3Encoder, QwenLocalGenerator
    from src.research_point_2.retrieval import RetrievalIndex
    from src.research_point_3.teacher_freeze import audit_teacher_freeze
    config = json.loads((ROOT / "configs/rp2_graphrag_v6_equal_budget.json").read_text(encoding="utf-8"))
    freeze_config = json.loads((ROOT / "configs/research_point_3/teacher_graph_rp3_v1.json").read_text(encoding="utf-8"))
    def rows(path):
        return [json.loads(x) for x in (ROOT/path).read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    candidates = load_evidence_candidates(ROOT/config["graph_root"])
    if len(candidates) != 208:
        raise RuntimeError("strict208 evidence count mismatch")
    benchmark_candidates = rows(config["benchmark_dir"] + "/evidence_candidates.jsonl")
    # The RP2 runner uses these frozen benchmark surfaces, not freshly relabelled records.
    candidates = [EvidenceCandidate(**{**x, "fault_class_ids": tuple(x["fault_class_ids"])}) for x in benchmark_candidates]
    if {x.evidence_id for x in candidates} != {x["evidence_id"] for x in rows(config["graph_root"]+"/evidence_assertions.jsonl")}:
        raise RuntimeError("benchmark does not close on strict208")
    queries = [SilverQuery(**{**x, "relevant_evidence_ids": (), "candidate_evidence_ids": ()})
               for x in rows(config["benchmark_dir"] + "/queries.jsonl")]
    expected = {x["query_id"]: [e["evidence_id"] for e in x["ranked"]]
                for x in rows(config["frozen_retrieval_results"]) if x["method"] == "Ours_v6_k3_equal"}
    if len(queries) != 40 or set(expected) != {q.query_id for q in queries}:
        raise RuntimeError("frozen 40 query identity mismatch")
    if args.limit:
        queries = queries[:args.limit]
    output = ROOT / (f".tmp/rp3_smoke/limit_{args.limit}" if args.limit else
        "results/experiments/research_point_3/teacher_traces/strict208_base_top32")
    embedding = config["embedding"]
    encoder = BgeM3Encoder(ROOT/embedding["model_path"], device="cuda", require_cuda=True,
        batch_size=embedding["batch_size"], max_length=embedding["max_length"])
    index_path = ROOT/embedding["index_dir"]
    if not index_path.exists():
        # No overwrite of an existing upstream index, even when incomplete.
        DenseEvidenceIndex.build(candidates, encoder).save(index_path, metadata={
            "graph_root": config["graph_root"], "built_for": "RP3_RP2_replay",
            "source_sha256": normalized_text_sha256(ROOT/config["graph_root"]/"source_records.jsonl"),
        })
    dense = DenseEvidenceIndex.load(index_path)
    if set(dense.evidence_ids) != {x.evidence_id for x in candidates}:
        raise RuntimeError("BGE index evidence ID closure mismatch")
    audit = audit_teacher_freeze(ROOT, freeze_config)
    if not audit.teacher_system_ready:
        raise RuntimeError("teacher system blocked: " + "; ".join(audit.teacher_system_blockers))
    # Bind the entire ready system inventory, including binary model/index hashes.
    identity = stable_sha256({k:audit.manifest[k] for k in
        ("graph_artifacts", "model_inventories", "vector_index")}|{
        "config":config,"runner_sha256":__import__("hashlib").sha256(Path(__file__).read_bytes()).hexdigest(),
        "adapter_sha256":__import__("hashlib").sha256((ROOT/"src/research_point_3/teacher_runner.py").read_bytes()).hexdigest(),
        "upstream_verifier_sha256":__import__("hashlib").sha256((ROOT/"scripts/run_rp2_equal_budget_v6.py").read_bytes()).hexdigest()})
    graph_index = RetrievalIndex(candidates)
    captured = []
    for q in queries:
        result, pool = replay_candidates(q, candidates, graph_index, dense, encoder, config)
        if [x.evidence_id for x in result.ranked] != expected[q.query_id]:
            raise RuntimeError(f"fresh RP2 ranking differs from frozen replay: {q.query_id}; stop, do not refreeze upstream")
        captured.append((q,result,pool))
        print(f"retrieval {q.query_id}: {len(pool)} candidates, exact K3 replay matched", flush=True)
    replay_report = {"schema": "rp3_fresh_retrieval_audit_v1", "smoke_only": bool(args.limit),
        "query_count": len(captured), "all_rankings_match": True,
        "queries": [{"query_id":q.query_id,"selected_ids":[x.evidence_id for x in ret.ranked],
            "scored_count":len(pool)} for q,ret,pool in captured], "teacher_identity": identity}
    _write_immutable(output/"fresh_retrieval_audit.json",canonical_json_bytes(replay_report))
    del encoder, dense
    gc.collect()
    import torch
    torch.cuda.empty_cache()
    if args.retrieval_only:
        return
    generator = QwenLocalGenerator(ROOT/config["generator"]["model_path"], require_cuda=True)
    exported = []
    for q,ret,pool in captured:
        checkpoint = output/"checkpoints"/(q.query_id+".json")
        if checkpoint.exists():
            cached = json.loads(checkpoint.read_text(encoding="utf-8"))
            if cached["teacher_identity"] != identity:
                raise RuntimeError("stale RP3 checkpoint; use a new run, do not overwrite frozen inputs")
            row = cached["row"]
        else:
            by_id = {x.evidence_id:x for x,_ in pool}
            base = verify_selection(q,ret,[by_id[x.evidence_id] for x in ret.ranked],generator,config,output/"model_cache",identity)
            tails = {eid:verify_selection(q,ret,[item],generator,config,output/"model_cache",identity,"tail:"+eid)
                for eid,item in by_id.items() if eid not in {x.evidence_id for x in ret.ranked}}
            row = compile_candidate_row(q,ret,pool,base,tails)
            _write_immutable(checkpoint,canonical_json_bytes({"teacher_identity":identity,"row":row}))
        exported.append(row)
        print(f"verifier {len(exported)}/{len(captured)} {q.query_id}", flush=True)
    data_path = output/"teacher_candidate_traces.jsonl"
    _write_immutable(data_path,canonical_jsonl_bytes(exported))
    manifest = {"schema":"rp3_teacher_candidate_trace_manifest_v1", "trace_schema":"rp3_teacher_candidate_trace_v1",
        "data_artifact":{"path":data_path.relative_to(ROOT).as_posix(),"sha256":normalized_text_sha256(data_path)},
        "teacher_graph":{"id":"TeacherGraph_RP3_v1","terminology_tier":"strict_208","evidence_count":208,
            "evidence_assertions_sha256":normalized_text_sha256(ROOT/config["graph_root"]/"evidence_assertions.jsonl")},
        "rp2_replay_sha256":normalized_text_sha256(ROOT/config["frozen_retrieval_results"]),
        "teacher_method":"Ours_v6_k3_equal","base_query_count":len(exported),"candidates_per_query":32,
        "candidate_count_policy":"at_most","maximum_selected":3,"smoke_only":bool(args.limit),
        "fresh_retrieval_audit_sha256":normalized_text_sha256(output/"fresh_retrieval_audit.json"),
        "validation":{k:True for k in freeze_config["required_teacher_trace"]["required_validation_flags"]},
        "supervision_boundary":"teacher_generated_not_expert_ground_truth",
        "route_supervision_status":"pending_student_rollout",
    }
    manifest["logical_sha256"]=stable_sha256(manifest)
    _write_immutable(output/"manifest.json",canonical_json_bytes(manifest))
    print(f"Teacher export complete: {output}; route labels still require student rollout.")

if __name__ == "__main__":
    main()
