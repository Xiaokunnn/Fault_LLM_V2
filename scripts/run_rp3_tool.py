#!/usr/bin/env python3
"""JSON-lines edge tool runner, without an LLM or online BGE by default.

Reads one public select_pump_evidence argument object per stdin line. Candidate
buckets come only from the governed training trace bundle, never caller hashes.
Fallback without a connected teacher becomes abstention; no dummy answer.
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--memory",required=True)
    p.add_argument("--traces",required=True)
    p.add_argument("--export-dir",required=True)
    args=p.parse_args()
    from src.research_point_3.artifacts import read_teacher_trace_bundle,read_compact_evidence_memory_bundle,stable_sha256
    from src.research_point_3.contracts import CONTRACT_VERSION
    from src.research_point_3.features import HashingFeatureProvider
    from src.research_point_3.onnx_runtime import OnnxEvidenceController
    from src.research_point_3.tool_api import EvidenceMemoryResolver,FrozenCandidateBucket,FrozenCandidateBucketRegistry,SelectPumpEvidenceTool,SelectPumpEvidenceFacade,BUCKET_REGISTRY_ARTIFACT_TYPE
    records,memory=read_compact_evidence_memory_bundle(args.memory,purpose="training")
    traces,manifest=read_teacher_trace_bundle(args.traces,purpose="training")
    if memory["teacher_graph"]!=manifest["teacher_graph"] or memory["teacher_system_identity_sha256"]!=manifest["teacher_system_identity_sha256"]:
        raise ValueError("runtime trace/memory teacher identity mismatch")
    resolver=EvidenceMemoryResolver(records=records,manifest=memory)
    buckets=[FrozenCandidateBucket(t.query.fault_id,t.query.requested_role,t.candidate_evidence_ids)
        for t in traces if t.perturbation_id=="original"]
    rows=[{"fault_id":x.fault_id,"role":x.role.value,"evidence_ids":list(x.evidence_ids)}
        for x in sorted(buckets,key=lambda x:(x.fault_id,x.role.value))]
    registry_manifest={"artifact_type":BUCKET_REGISTRY_ARTIFACT_TYPE,"contract_version":CONTRACT_VERSION,
        "memory":{"id":memory["memory_id"],"logical_sha256":memory["logical_sha256"]},
        "teacher_graph":memory["teacher_graph"],"bucket_count":len(rows),"logical_sha256":stable_sha256(rows)}
    registry=FrozenCandidateBucketRegistry(buckets=buckets,manifest=registry_manifest,resolver=resolver)
    scope_authorizations={}
    for trace in traces:
        if trace.perturbation_id!="original":
            continue
        key=(trace.query.fault_id,trace.query.requested_role)
        authorized=set(scope_authorizations.get(key,()))
        declared=trace.metadata.get("automatic_fault_label_mismatch_selected_evidence_ids",())
        if not set(declared).issubset(trace.selected_evidence_ids):
            raise ValueError("trace scope authorization is not teacher-selected")
        authorized.update(declared)
        if authorized:
            scope_authorizations[key]=tuple(sorted(authorized))
    root=Path(args.export_dir)
    controller=OnnxEvidenceController(onnx_manifest_path=root/"onnx_export_manifest.json",
        quantized_model_path=root/"controller.int8.onnx",calibration_manifest_path=root/"calibration_manifest.json",
        memory_manifest=memory,feature_provider=HashingFeatureProvider(),providers=["CPUExecutionProvider"])
    facade=SelectPumpEvidenceFacade(tool=SelectPumpEvidenceTool(controller=controller,
        resolver=resolver,teacher_available=False,
        teacher_scope_authorizations=scope_authorizations),registry=registry)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request=json.loads(line)
            if not isinstance(request,dict):
                raise ValueError("request must be an object")
            response=facade.select_pump_evidence(**request)
            print(json.dumps(response.to_dict(),ensure_ascii=False),flush=True)
        except (ValueError,TypeError,KeyError) as exc:
            print(json.dumps({"ok":False,"action":"abstain","error":str(exc)},ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
