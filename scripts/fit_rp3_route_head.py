#!/usr/bin/env python3
"""Fit ONLY the route head from observed frozen-student/teacher disagreement.

Costs are declared dimensionless utilities, not fabricated latency or energy.
The ranking/support/card representation is frozen, so labels stay on-policy.
MP008 is never used for gradients or early stopping.
"""
import argparse
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.research_point_3.artifacts import canonical_json_bytes, canonical_jsonl_bytes, file_sha256, stable_sha256, _write_immutable
from src.research_point_3.experiment_io import prepare, decode_row, onnx_feed, exact_teacher_agreement

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",required=True)
    p.add_argument("--training-dir",required=True)
    p.add_argument("--output-dir",required=True)
    p.add_argument("--epochs",type=int,default=100)
    p.add_argument("--error-cost",type=float,default=50.0)
    p.add_argument("--teacher-cost",type=float,default=8.0)
    p.add_argument("--review-cost",type=float,default=12.0)
    args=p.parse_args()
    import math
    if args.epochs<1 or any(not math.isfinite(x) or x<0 for x in (args.error_cost,args.teacher_cost,args.review_cost)):
        p.error("invalid epochs/cost profile")
    import torch
    from src.research_point_3.training import load_controller_checkpoint, set_deterministic_seed
    from src.research_point_3.losses import cost_sensitive_route_loss
    source=Path(args.training_dir)
    output=Path(args.output_dir)
    if output.exists():
        raise RuntimeError("route output must be a new directory")
    manifest=json.loads((source/"training_manifest.json").read_text(encoding="utf-8"))
    if stable_sha256({k:v for k,v in manifest.items() if k!="logical_sha256"}) != manifest["logical_sha256"]:
        raise ValueError("training manifest hash mismatch")
    checkpoint=source/manifest["checkpoint_file"]
    if file_sha256(checkpoint)!=manifest["checkpoint_sha256"]:
        raise ValueError("checkpoint hash mismatch")
    prepared=prepare(args.config,attach_development=False)
    model,payload=load_controller_checkpoint(checkpoint,expected_input_fingerprint=prepared.input_fingerprint)
    if manifest["input_fingerprint"]!=prepared.input_fingerprint:
        raise ValueError("training inputs mismatch")
    set_deterministic_seed(7042026)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    for parameter in model.route_head.parameters():
        parameter.requires_grad_(True)
    model.eval() # freeze dropout too
    rollout=[]
    captured=[]
    hook=model.route_head.register_forward_pre_hook(lambda module, args: captured.append(args[0].detach()))
    datasets=(prepared.train_dataset,prepared.validation_dataset)
    tensors=[]
    for dataset in datasets:
        costs=[]
        labels=[]
        start=len(captured)
        for i,trace in enumerate(dataset.traces):
            feed={k:torch.from_numpy(v) for k,v in onnx_feed(dataset,i).items()}
            with torch.no_grad():
                logits=model(**feed)
            outputs=[getattr(logits,k).detach().numpy() for k in ("rank_logits","support_logits","field_state_logits","cardinality_logits","route_logits")]
            decoded=decode_row(outputs,trace,dataset.records)
            success=bool(decoded.selected_evidence_ids) and exact_teacher_agreement(trace,decoded.selected_evidence_ids)
            teacher_success=bool(trace.selected_evidence_ids)
            action_costs=[1.0 + args.error_cost*(not success),
                1.0 + args.teacher_cost + args.error_cost*(not teacher_success),args.review_cost]
            label=min(range(3),key=lambda a:action_costs[a])
            costs.append(action_costs)
            labels.append(label)
            rollout.append({"trace_id":trace.trace_id,"split":trace.split.value,
                "student_selected_ids":list(decoded.selected_evidence_ids),
                "teacher_selected_ids":list(trace.selected_evidence_ids),
                "teacher_relative_exact_agreement":success,
                "action_costs":dict(zip(("answer","fallback","abstain"),action_costs)),
                "route_target":("answer","fallback","abstain")[label],
                "teacher_source":"frozen_same_query_candidate_replay",
                "cost_unit":"declared_utility_not_measured_milliseconds_or_joules"})
        tensors.append((torch.cat(captured[start:]),torch.tensor(labels),torch.tensor(costs)))
    hook.remove()
    optimizer=torch.optim.AdamW(model.route_head.parameters(),lr=3e-4)
    best=float("inf")
    best_state=None
    history=[]
    patience=0
    for epoch in range(args.epochs):
        x,y,cost=tensors[0]
        optimizer.zero_grad()
        loss=cost_sensitive_route_loss(model.route_head(x),y,route_action_costs=cost)
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            x,y,cost=tensors[1]
            validation=float(cost_sensitive_route_loss(model.route_head(x),y,route_action_costs=cost))
        history.append({"epoch":epoch+1,"train_route_loss":float(loss.detach()),"validation_route_loss":validation})
        if validation<best:
            best=validation
            best_state=copy.deepcopy(model.state_dict())
            patience=0
        else:
            patience+=1
        if patience>=10:
            break
    model.load_state_dict(best_state)
    output.mkdir(parents=True)
    payload["model_state_dict"]=model.state_dict()
    payload["route_training"]={"source_checkpoint_sha256":manifest["checkpoint_sha256"],
        "frozen_nonroute_heads":True,"split":"build_train_only","model_selection":"build_validation_only",
        "utility_profile":{"error":args.error_cost,"teacher":args.teacher_cost,"review":args.review_cost},
        "support_threshold_for_rollout":0.5,"mp008_used_for_training":False}
    torch.save(payload,output/"best_controller.pt",_use_new_zipfile_serialization=False)
    _write_immutable(output/"route_rollouts.jsonl",canonical_jsonl_bytes(rollout))
    _write_immutable(output/"training_history.jsonl",canonical_jsonl_bytes(history))
    result={k:v for k,v in manifest.items() if k!="logical_sha256"}
    result.update({"source_bootstrap_manifest_sha256":manifest["logical_sha256"],
        "route_training":payload["route_training"],"route_rollouts_sha256":file_sha256(output/"route_rollouts.jsonl"),
        "checkpoint_sha256":file_sha256(output/"best_controller.pt"),
        "history_sha256":file_sha256(output/"training_history.jsonl"),
        "best_epoch":min(history,key=lambda x:x["validation_route_loss"])["epoch"],
        "best_validation_loss":best,"route_supervision_status":"frozen_student_teacher_relative_utility_fit"})
    result["logical_sha256"]=stable_sha256(result)
    _write_immutable(output/"training_manifest.json",canonical_json_bytes(result))
    print(f"Route fitted on {len(tensors[0][1])} build rows; no MP008 gradients. {output}")

if __name__ == "__main__":
    main()
