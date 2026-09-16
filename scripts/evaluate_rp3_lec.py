#!/usr/bin/env python3
"""Evaluate frozen ONNX decisions; records teacher-relative, not clinical metrics."""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.research_point_3.artifacts import canonical_json_bytes, canonical_jsonl_bytes, file_sha256, _write_immutable
from src.research_point_3.experiment_io import prepare, onnx_feed, decode_row, exact_teacher_agreement
from src.research_point_3.evaluation import pointer_metrics
from src.research_point_3.calibration import ControllerCalibration

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",required=True)
    p.add_argument("--export-dir",required=True)
    p.add_argument("--output-dir",required=True)
    p.add_argument("--repeats",type=int,default=30)
    args=p.parse_args()
    if args.repeats<1:
        p.error("repeats must be positive")
    import numpy as np
    import onnxruntime as ort
    root=Path(args.export_dir)
    prepared=prepare(args.config,attach_development=False)
    dataset=prepared.validation_dataset
    calibration=ControllerCalibration.read(root/"calibration_manifest.json")
    model=root/"controller.int8.onnx"
    if calibration.quantized_model_sha256!=file_sha256(model):
        raise ValueError("INT8/calibration identity mismatch")
    if calibration.teacher_graph_sha256!=prepared.memory_manifest["teacher_graph"]["sha256"] or calibration.memory_logical_sha256!=prepared.memory_manifest["logical_sha256"]:
        raise ValueError("evaluation memory identity mismatch")
    options=ort.SessionOptions()
    options.intra_op_num_threads=1
    session=ort.InferenceSession(str(model),sess_options=options,providers=["CPUExecutionProvider"])
    rows=[]
    for i,trace in enumerate(dataset.traces):
        feed=onnx_feed(dataset,i)
        for _ in range(5):
            session.run(None,feed)
        timings=[]
        for _ in range(args.repeats):
            start=time.perf_counter_ns()
            outputs=session.run(None,feed)
            timings.append((time.perf_counter_ns()-start)/1e6)
        decoded=decode_row(outputs,trace,dataset.records,support_threshold=calibration.support_threshold,
            minimum_route_confidence=calibration.minimum_route_confidence)
        rows.append({"trace_id":trace.trace_id,"scenario_id":trace.query.scenario_id,
            "split":trace.split.value,"action":decoded.route_action.value,
            "selected_ids":list(decoded.selected_evidence_ids),
            "teacher_selected_ids":list(trace.selected_evidence_ids),
            "teacher_exact_agreement":exact_teacher_agreement(trace,decoded.selected_evidence_ids),
            "pointer_metrics":pointer_metrics(decoded.selected_evidence_ids,trace.selected_evidence_ids),
            "controller_only_median_ms":float(np.median(timings)),
            "controller_only_p95_ms":float(np.percentile(timings,95)),"timings_ms":timings})
    answered=[x for x in rows if x["action"]=="answer"]
    summary={"status":"measured_build_validation_not_independent_test", "queries":len(rows),
        "independent_scenario_groups":len({x["scenario_id"] for x in rows}),
        "answer_coverage":len(answered)/len(rows),
        "teacher_disagreement_on_answered":sum(not x["teacher_exact_agreement"] for x in answered)/len(answered) if answered else None,
        "macro_pointer_f1":sum(x["pointer_metrics"]["f1"] for x in rows)/len(rows),
        "int8_sha256":file_sha256(model),"hardware":__import__("platform").platform(),
        "latency_scope":"ORT controller only; excludes features, memory, rendering, shell, teacher fallback",
        "target_edge_deployment_claim":False,"external_evaluation_completed":False,
        "warning":"validation was used for model selection; do not report as held-out external accuracy"}
    _write_immutable(Path(args.output_dir)/"predictions.jsonl",canonical_jsonl_bytes(rows))
    _write_immutable(Path(args.output_dir)/"summary.json",canonical_json_bytes(summary))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
