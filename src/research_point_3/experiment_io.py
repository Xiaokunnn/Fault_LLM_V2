"""Shared governed inputs for RP3 command-line experiments."""
import json
from pathlib import Path
from .dataset import TensorizationConfig, prepare_training_data
from .onnx_runtime import decode_numpy_output

ROOT = Path(__file__).resolve().parents[2]

def prepare(config_path, *, attach_development=True):
    values = json.loads(Path(config_path).read_text(encoding="utf-8"))
    names = ("trace_bundle_dir", "memory_bundle_dir", "teacher_freeze_path", "feature_bundle_path")
    paths = {k: ROOT / values[k] for k in names}
    if attach_development:
        for k in ("development_trace_bundle_dir", "development_memory_bundle_dir", "development_feature_bundle_path"):
            if values.get(k):
                paths[k] = ROOT / values[k]
    return prepare_training_data(**paths, config=TensorizationConfig(**values["tensorization"]))

def onnx_feed(dataset, index):
    return {k: dataset[index][k].unsqueeze(0).cpu().numpy() for k in (
        "query_features", "candidate_features", "availability_mask", "selection_budget")}

def decode_row(outputs, trace, records, *, support_threshold=0.5, minimum_route_confidence=0.0):
    return decode_numpy_output(rank_logits=outputs[0], support_logits=outputs[1],
        field_state_logits=outputs[2], cardinality_logits=outputs[3], route_logits=outputs[4],
        candidate_ids=trace.candidate_evidence_ids,
        candidate_roles=[records[eid].role for eid in trace.candidate_evidence_ids],
        availability_mask=trace.availability_mask, selection_budget=trace.selection_budget,
        support_threshold=support_threshold, minimum_route_confidence=minimum_route_confidence)

def exact_teacher_agreement(trace, selected):
    # Teacher agreement is NOT engineering/diagnostic accuracy.
    return set(selected) == set(trace.selected_evidence_ids)
