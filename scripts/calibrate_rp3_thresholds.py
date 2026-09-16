#!/usr/bin/env python3
"""Fit support and route thresholds jointly on post-INT8 MP008 outputs only."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.research_point_3.artifacts import file_sha256
from src.research_point_3.calibration import write_calibration_manifest_from_export
from src.research_point_3.experiment_io import prepare, onnx_feed, decode_row, exact_teacher_agreement

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
    grid=[]
    for support in (0.3,0.4,0.5,0.6,0.7,0.8,0.9,0.95):
        for confidence in (0.0,0.5,0.6,0.7,0.8,0.9,0.95):
            answered=errors=0
            for trace,logits in zip(dataset.traces,outputs):
                result=decode_row(logits,trace,dataset.records,support_threshold=support,minimum_route_confidence=confidence)
                if result.route_action.value == "answer":
                    answered+=1
                    errors+=not exact_teacher_agreement(trace,result.selected_evidence_ids)
            grid.append({"support":support,"confidence":confidence,"answered":answered,
                "errors":errors,"risk":errors/answered if answered else None})
    feasible=[x for x in grid if x["answered"]>=args.minimum_answers and x["risk"]<=args.maximum_teacher_disagreement]
    if not feasible:
        # Never manufacture a successful calibration from zero accepted answers.
        raise RuntimeError("no feasible MP008 risk/coverage operating point; do not deploy. Inspect model and development coverage.")
    best=min(feasible,key=lambda x:(-x["answered"],x["risk"],-x["support"],-x["confidence"]))
    metrics={"objective":"max_coverage_subject_to_empirical_teacher_disagreement", "grid":grid,
        "chosen":best,"development_queries":len(dataset),
        "maximum_teacher_disagreement":args.maximum_teacher_disagreement,"minimum_answers":args.minimum_answers,
        "statistical_safety_guarantee":False,"human_expert_reviewed":False,
        "warning":"MP008 empirical calibration only; no external or hardware performance claim"}
    write_calibration_manifest_from_export(root/"calibration_manifest.json",
        support_threshold=best["support"],minimum_route_confidence=best["confidence"],
        quantized_model_path=model,onnx_export_manifest_path=root/"onnx_export_manifest.json",metrics=metrics)
    print(json.dumps(best))

if __name__ == "__main__":
    main()
