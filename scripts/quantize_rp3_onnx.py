#!/usr/bin/env python3
"""Actual static INT8 QDQ export; thresholds are intentionally NOT inherited."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.research_point_3.artifacts import canonical_json_bytes, file_sha256, stable_sha256, _write_immutable

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--export-dir", required=True)
    args = p.parse_args()
    import numpy as np
    import onnx
    import onnxruntime as ort
    from onnxruntime.quantization import QuantFormat, QuantType, quantize_static
    from src.research_point_3.onnx_export import NumpyInt8CalibrationDataReader
    root = Path(args.export_dir)
    export = json.loads((root/"onnx_export_manifest.json").read_text(encoding="utf-8"))
    if stable_sha256({k:v for k,v in export.items() if k != "logical_sha256"}) != export["logical_sha256"]:
        raise ValueError("ONNX export manifest hash mismatch")
    source = root/export["onnx_file"]
    if file_sha256(source) != export["onnx_sha256"]:
        raise ValueError("FP32 ONNX hash mismatch")
    calibration_path = root/"int8_calibration_manifest.json"
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    development = export["runtime_binding"]["development_calibration_source"]
    if development["corpus"] != "MP008" or calibration["source_input_fingerprint"] != development["input_fingerprint"]:
        raise ValueError("INT8 representative inputs must bind the exact MP008 development set")
    destination = root/"controller.int8.onnx"
    if destination.exists() or (root/"quantization_manifest.json").exists():
        raise RuntimeError("INT8 output exists; do not silently replace a calibrated model")
    reader = NumpyInt8CalibrationDataReader(calibration_path)
    temporary = root/"controller.int8.pending.onnx"
    # Quantize affine layers only. Masked finfo.min logits and normalization stay FP32.
    quantize_static(str(source),str(temporary),reader,quant_format=QuantFormat.QDQ,
        activation_type=QuantType.QInt8,weight_type=QuantType.QInt8,per_channel=True,
        op_types_to_quantize=["MatMul", "Gemm"])
    model = onnx.load(str(temporary))
    onnx.checker.check_model(model)
    qdq_count = sum(node.op_type in {"QuantizeLinear","DequantizeLinear"} for node in model.graph.node)
    if not qdq_count or not any(x.data_type == onnx.TensorProto.INT8 for x in model.graph.initializer):
        raise RuntimeError("quantization produced no INT8 weights/QDQ nodes")
    fp = ort.InferenceSession(str(source),providers=["CPUExecutionProvider"])
    quant = ort.InferenceSession(str(temporary),providers=["CPUExecutionProvider"])
    reader.rewind()
    maximum_error = [0.0]*5
    count = 0
    while (feed := reader.get_next()) is not None:
        for i,(a,b) in enumerate(zip(fp.run(None,feed),quant.run(None,feed))):
            if not np.isfinite(b).all():
                raise RuntimeError("non-finite INT8 output")
            active = np.abs(a) < 1e30
            if active.any():
                maximum_error[i]=max(maximum_error[i],float(np.max(np.abs(a[active]-b[active]))))
        count += len(feed["query_features"])
    temporary.replace(destination)
    result = {"schema":"rp3_int8_quantization_v1","status":"quantized_thresholds_pending",
        "fp32_sha256":file_sha256(source),"int8_sha256":file_sha256(destination),
        "calibration_manifest_sha256":file_sha256(calibration_path),
        "qdq_nodes":qdq_count,"checked_samples":count,"maximum_absolute_error_per_head":maximum_error,
        "fp32_bytes":source.stat().st_size,"int8_bytes":destination.stat().st_size,
        "accuracy_passed":False,"target_edge_hardware_measured":False,
        "onnxruntime_version":ort.__version__,"post_quantization_calibration_required":True}
    result["logical_sha256"]=stable_sha256(result)
    _write_immutable(root/"quantization_manifest.json",canonical_json_bytes(result))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
