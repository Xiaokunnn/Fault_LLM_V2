#!/usr/bin/env python3
"""Fit support and route thresholds jointly on post-INT8 MP008 outputs only."""
import argparse
from collections import Counter
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.research_point_3.artifacts import canonical_json_bytes, file_sha256, _write_immutable
from src.research_point_3.calibration import write_calibration_manifest_from_export
from src.research_point_3.experiment_io import prepare, onnx_feed, decode_row, exact_teacher_agreement

SEARCH_REPORT_SCHEMA = "rp3_mp008_calibration_search_v1"

def select_operating_point(grid, *, maximum_teacher_disagreement, minimum_answers):
    feasible=[x for x in grid if x["answered"]>=minimum_answers and x["risk"] is not None
        and x["risk"]<=maximum_teacher_disagreement]
    if feasible:
        return min(feasible,key=lambda x:(-x["answered"],x["risk"],-x["support"],-x["confidence"])), None
    answered=[x for x in grid if x["answered"]]
    maximum_coverage=max((x["answered"] for x in grid),default=0)
    if maximum_coverage < minimum_answers:
        reason="insufficient_answer_coverage"
    else:
        reason="teacher_disagreement_above_limit"
    closest=min(answered,key=lambda x:(x["risk"],-x["answered"],-x["support"],-x["confidence"])) if answered else None
    return None, {"reason":reason,"maximum_answered":maximum_coverage,
        "lowest_observed_risk":closest["risk"] if closest else None,
        "closest_observed_point":closest}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",required=True)
    p.add_argument("--export-dir",required=True)
    p.add_argument("--maximum-teacher-disagreement",type=float,default=0.1)
    p.add_argument("--minimum-answers",type=int,default=5)
    args=p.parse_args()
    if not 0 <= args.maximum_teacher_disagreement <= 1 or args.minimum_answers < 1:
        p.error("invalid risk/coverage constraint")
    import onnxruntime as ort
    root=Path(args.export_dir)
    model=root/"controller.int8.onnx"
    quant=json.loads((root/"quantization_manifest.json").read_text(encoding="utf-8"))
    if quant["int8_sha256"] != file_sha256(model):
        raise ValueError("quantized model identity mismatch")
    prepared=prepare(args.config)
    dataset=prepared.development_dataset
    if dataset is None:
        raise ValueError("separate MP008-only development bundles are required")
    export=json.loads((root/"onnx_export_manifest.json").read_text(encoding="utf-8"))
    if export["runtime_binding"]["development_calibration_source"]["input_fingerprint"] != prepared.development_fingerprint:
        raise ValueError("MP008 binding mismatch")
    session=ort.InferenceSession(str(model),providers=["CPUExecutionProvider"])
    outputs=[session.run(None,onnx_feed(dataset,i)) for i in range(len(dataset))]
    raw_route_counts=Counter(("answer","fallback","abstain")[int(logits[4][0].argmax())] for logits in outputs)
    grid=[]
    for support in (0.3,0.4,0.5,0.6,0.7,0.8,0.9,0.95):
        for confidence in (0.0,0.5,0.6,0.7,0.8,0.9,0.95):
            answered=errors=exact=nonempty=0
            actions=Counter()
            for trace,logits in zip(dataset.traces,outputs):
                result=decode_row(logits,trace,dataset.records,support_threshold=support,minimum_route_confidence=confidence)
                actions[result.route_action.value]+=1
                agrees=exact_teacher_agreement(trace,result.selected_evidence_ids)
                exact+=agrees
                nonempty+=bool(result.selected_evidence_ids)
                if result.route_action.value == "answer":
                    answered+=1
                    errors+=not agrees
            grid.append({"support":support,"confidence":confidence,"answered":answered,
                "errors":errors,"risk":errors/answered if answered else None,
                "actions":dict(sorted(actions.items())),"selection_exact_all":exact,
                "selection_nonempty_all":nonempty})
    best,blocked=select_operating_point(grid,
        maximum_teacher_disagreement=args.maximum_teacher_disagreement,
        minimum_answers=args.minimum_answers)
    report={"schema":SEARCH_REPORT_SCHEMA,
        "status":"calibrated" if best is not None else "blocked_no_feasible_operating_point",
        "development_corpus":"MP008","development_queries":len(dataset),
        "quantized_model_sha256":file_sha256(model),
        "development_input_fingerprint":prepared.development_fingerprint,
        "constraints":{"maximum_teacher_disagreement":args.maximum_teacher_disagreement,
            "minimum_answers":args.minimum_answers},
        "raw_route_argmax_counts":dict(sorted(raw_route_counts.items())),
        "chosen":best,"blocked":blocked,"grid":grid,
        "teacher_agreement_is_not_diagnostic_accuracy":True,
        "human_expert_reviewed":False}
    report_path=root/"calibration_search_report.json"
    _write_immutable(report_path,canonical_json_bytes(report))
    if best is None:
        raise RuntimeError(
            "no feasible MP008 risk/coverage operating point; do not deploy. "
            f"Reason={blocked['reason']}; diagnostic report: {report_path}"
        )
    metrics={"objective":"max_coverage_subject_to_empirical_teacher_disagreement", "grid":grid,
        "chosen":best,"development_queries":len(dataset),
        "maximum_teacher_disagreement":args.maximum_teacher_disagreement,"minimum_answers":args.minimum_answers,
        "statistical_safety_guarantee":False,"human_expert_reviewed":False,
        "warning":"MP008 empirical calibration only; no external or hardware performance claim",
        "search_report_sha256":file_sha256(report_path)}
    write_calibration_manifest_from_export(root/"calibration_manifest.json",
        support_threshold=best["support"],minimum_route_confidence=best["confidence"],
        quantized_model_path=model,onnx_export_manifest_path=root/"onnx_export_manifest.json",metrics=metrics)
    print(json.dumps(best))

if __name__ == "__main__":
    main()
