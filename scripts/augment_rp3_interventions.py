#!/usr/bin/env python3
"""Replay evidence-removal interventions AFTER freezing base fault groups.

This is bounded candidate-set reselection, not a new graph build or a new
independent case dataset. Every changed selected set is verified by the real 7B.
"""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.research_point_3.artifacts import read_teacher_trace_bundle,read_compact_evidence_memory_bundle,write_teacher_trace_bundle,_write_immutable,canonical_json_bytes,canonical_jsonl_bytes,stable_sha256,file_sha256
from src.research_point_3.trace_export import export_candidate_decisions,assemble_single_role_teacher_trace
from src.research_point_3.teacher_runner import verify_selection

def reselect(pool, unavailable, candidates, values):
    """Exact frozen RP2 greedy gain over an already scored bounded pool."""
    from src.research_point_2.retrieval import _candidate_overlap
    remaining=sorted([(candidates[x["evidence_id"]],x["raw_base_score"]) for x in pool
        if x["evidence_id"] not in unavailable],key=lambda x:(x[1],x[0].evidence_id),reverse=True)
    selected=[]
    families={}
    while remaining and len(selected)<3:
        eligible=[]
        for position,(item,score) in enumerate(remaining):
            family=item.source_family_id or "UNKNOWN"
            if families.get(family,0)>=values["max_per_source_family"]:
                continue
            gain=score+values["source_family_bonus"]*(family not in families)-values["redundancy_penalty"]*max(
                (_candidate_overlap(item,old) for old,_ in selected),default=0.0)
            eligible.append((gain,-position,position))
        if not eligible:
            break
        gain,_,position=max(eligible)
        item,_=remaining.pop(position)
        selected.append((item,gain))
        family=item.source_family_id or "UNKNOWN"
        families[family]=families.get(family,0)+1
    return selected

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",default="data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/traces/augmented_training")
    args=p.parse_args()
    import os
    os.chdir(ROOT)
    from src.research_point_3.dataset import _validate_teacher_freeze_manifest
    from src.research_point_2.local_models import QwenLocalGenerator
    from src.research_point_2.dataset import EvidenceCandidate,SilverQuery
    from src.research_point_2.retrieval import RetrievalResult,RankedEvidence
    from scripts.export_rp3_teacher_traces import _validation_report
    frozen=json.loads(Path("configs/frozen/teacher_graph_rp3_v1.freeze.json").read_text(encoding="utf-8"))
    _validate_teacher_freeze_manifest(frozen)
    config=json.loads(Path("configs/rp2_graphrag_v6_equal_budget.json").read_text(encoding="utf-8"))
    bundle=Path("data/kg/marine_pump/rp3/TeacherGraph_RP3_v1")
    originals,manifest=read_teacher_trace_bundle(bundle/"traces/training",purpose="training")
    records,memory=read_compact_evidence_memory_bundle(bundle/"evidence_memory/training",purpose="training")
    by_record={r.evidence_id:r for r in records}
    raw_path=Path("results/experiments/research_point_3/teacher_traces/strict208_base_top32/teacher_candidate_traces.jsonl")
    raw={r["query_id"]:r for r in map(json.loads,raw_path.read_text(encoding="utf-8").splitlines())}
    candidates={x["evidence_id"]:EvidenceCandidate(**{**x,"fault_class_ids":tuple(x["fault_class_ids"])})
        for x in map(json.loads,Path(config["benchmark_dir"],"evidence_candidates.jsonl").read_text(encoding="utf-8").splitlines())}
    generator=QwenLocalGenerator(config["generator"]["model_path"],require_cuda=True)
    output=Path(args.output)
    derived=[]
    audits=[]
    for trace in originals:
        base=raw[trace.query.query_id]
        pool=base["candidates"]
        full_selection=reselect(pool,set(),candidates,config["retrieval"])
        if [x.evidence_id for x,_ in full_selection]!=base["rp2_selected_before_verifier"]:
            raise RuntimeError("bounded reselection does not match frozen teacher; stop")
        # Prespecified removals, no MP008 or external examples influence curriculum.
        sets=[set(trace.candidate_evidence_ids)] + [{eid} for eid in trace.selected_evidence_ids]
        negatives=[eid for eid in trace.candidate_evidence_ids if eid not in trace.selected_evidence_ids]
        if negatives:
            sets.append({negatives[0]})
        seen=set()
        for removed in sets:
            identity=stable_sha256(sorted(removed))[:16]
            if not removed or identity in seen:
                continue
            seen.add(identity)
            intervention_id=trace.trace_id+"-remove-"+identity
            selected=reselect(pool,removed,candidates,config["retrieval"])
            q=SilverQuery(intervention_id,trace.query.question_zh,trace.query.fault_id,trace.query.fault_name_zh,trace.query.requested_role.value,())
            ranked=tuple(RankedEvidence(x.evidence_id,score,x.source_family_id,x.claim_id,x.role,q.fault_id in x.fault_class_ids,q.role==x.role) for x,score in selected)
            ret=RetrievalResult(q.query_id,"Ours_v6_k3_equal",ranked,0.0,len(pool)-len(removed),len(ranked),len(pool),0,0,"bounded_availability_intervention",False,True)
            checkpoint=output/"checkpoints"/(intervention_id+".json")
            checkpoint_identity=stable_sha256({"teacher":frozen["teacher_system_identity_sha256"],
                "parent":trace.to_dict(),"removed":sorted(removed),"script":file_sha256(Path(__file__))})
            if checkpoint.exists():
                cached=json.loads(checkpoint.read_text(encoding="utf-8"))
                if cached["identity"]!=checkpoint_identity:
                    raise ValueError("intervention checkpoint identity mismatch")
                run=cached["run"]
            else:
                run=verify_selection(q,ret,[x for x,_ in selected],generator,config,output/"verifier_cache",
                    frozen["teacher_system_identity_sha256"],intervention_id)
                _write_immutable(checkpoint,canonical_json_bytes({"identity":checkpoint_identity,"run":run}))
            if not run["cascade_contract_valid"]:
                raise RuntimeError("intervention verifier contract failed; raw cache retained")
            selected_ids=[eid for point in run["answer"]["answer_points"] for eid in point["evidence_ids"]]
            support=dict(base["final_support_by_evidence_id"])
            support.update(dict(zip([x.evidence_id for x,_ in selected],run["final_mask"])))
            prefix=[x.evidence_id for x,_ in selected]
            order=prefix+[x["evidence_id"] for x in pool if x["evidence_id"] not in prefix]
            row={**base,"candidates":[{**x,"available":x["evidence_id"] not in removed,
                    "score":float(len(order)-order.index(x["evidence_id"]))} for x in pool],
                "final_support_by_evidence_id":support,"selected_evidence_ids":selected_ids,
                "underfill_reason_codes":["teacher_replayed_availability_underfill"] if len(selected_ids)<3 else []}
            row["route"]={**base["route"],"action":"answer" if selected_ids else "abstain"}
            compiled=assemble_single_role_teacher_trace(trace_id=intervention_id,query=trace.query,
                candidate_trace=export_candidate_decisions(row,candidate_count_policy="at_most"),records_by_id=by_record,
                route=row["route"],route_action_costs=row["route_action_costs"],split=trace.split,
                teacher_graph_id=trace.teacher_graph_id,teacher_replay_id=trace.teacher_replay_id,perturbation_id="remove-"+identity,
                metadata={"route_supervision_status":"pending_student_rollout","parent_trace_id":trace.trace_id,
                    "teacher_replay_required":False,"intervention_verifier_replayed":True,
                    "tail_support_boundary":"unchanged query-evidence pair auxiliary labels; reselected K3 uses fresh batch verifier"})
            derived.append(compiled)
            audits.append({"trace_id":intervention_id,"parent":trace.trace_id,"removed":sorted(removed),"verifier":run})
        print(f"interventions {trace.trace_id}: cumulative {len(derived)}",flush=True)
    _write_immutable(output/"intervention_audit.jsonl",canonical_jsonl_bytes(audits))
    all_traces=(*originals,*derived)
    write_teacher_trace_bundle(output,all_traces,dataset_id="RP3_BasePlusRemoval_v1",
        teacher_graph_id=manifest["teacher_graph"]["id"],teacher_graph_sha256=manifest["teacher_graph"]["sha256"],
        teacher_replay_id=manifest["teacher_replay_id"],teacher_replay_sha256=manifest["teacher_replay_sha256"],
        candidate_trace_sha256=manifest["candidate_trace"]["data_sha256"],candidate_trace_manifest_sha256=manifest["candidate_trace"]["manifest_sha256"],
        teacher_system_identity_sha256=manifest["teacher_system_identity_sha256"],split_protocol=manifest["split_protocol"],
        validation_report=_validation_report(all_traces,expected_count=40),purpose="training")
    _write_immutable(output/"lineage.json",canonical_json_bytes({"base_manifest_sha256":file_sha256(bundle/"traces/training/manifest.json"),
        "intervention_audit_sha256":file_sha256(output/"intervention_audit.jsonl"),"original_queries":40,
        "derived_rows":len(derived),"independent_case_count_not_increased":True}))

if __name__=="__main__":
    main()
