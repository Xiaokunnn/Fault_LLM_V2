#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"
CONFIG="${RP3_CONFIG:-configs/research_point_3/lec_train_v1.json}"
BUNDLE="data/kg/marine_pump/rp3/TeacherGraph_RP3_v1"
RUN="${RP3_RUN_DIR:-results/experiments/research_point_3/lec_v1}"
stage="${1:-help}"
case "$stage" in
  help|-h|--help)
    echo 'Stages: preflight teacher-smoke teacher mp008 features augment train route export quantize calibrate diagnose evaluate all'
    echo 'Use a model-capable Linux server. Teacher requires the frozen Qwen2.5-7B and BGE-M3.'
    echo 'all is a sequential first run, not an overwrite/resume switch for training.'
    ;;
  preflight) "$PYTHON" -u scripts/check_rp3_server.py ;;
  teacher-smoke) "$PYTHON" -u scripts/run_rp3_teacher.py --limit 2 ;;
  teacher)
    "$PYTHON" -u scripts/run_rp3_teacher.py
    "$PYTHON" -u scripts/export_rp3_teacher_traces.py
    "$PYTHON" -u scripts/freeze_rp3_teacher_graph.py
    ;;
  mp008) "$PYTHON" -u scripts/prepare_rp3_mp008.py ;;
  features)
    "$PYTHON" scripts/build_rp3_features.py --purpose training --traces "$BUNDLE/traces/training" --memory "$BUNDLE/evidence_memory/training" --output "$BUNDLE/features/training_features.json"
    "$PYTHON" scripts/build_rp3_features.py --purpose development --traces "$BUNDLE/traces/development_mp008" --memory "$BUNDLE/evidence_memory/development_mp008" --output "$BUNDLE/features/development_mp008_features.json"
    ;;
  augment)
    "$PYTHON" -u scripts/augment_rp3_interventions.py
    "$PYTHON" scripts/build_rp3_features.py --purpose training --traces "$BUNDLE/traces/augmented_training" --memory "$BUNDLE/evidence_memory/training" --output "$BUNDLE/features/augmented_training_features.json"
    ;;
  train) "$PYTHON" -u scripts/train_rp3_lec.py --config "$CONFIG" --output-dir "$RUN/bootstrap" ;;
  route) "$PYTHON" -u scripts/fit_rp3_route_head.py --config "$CONFIG" --training-dir "$RUN/bootstrap" --output-dir "$RUN/routed" ;;
  export) "$PYTHON" -u scripts/export_rp3_onnx.py --training-manifest "$RUN/routed/training_manifest.json" --memory-manifest "$BUNDLE/evidence_memory/training/manifest.json" --output-dir "$RUN/onnx" --calibration-config "$CONFIG" ;;
  quantize) "$PYTHON" -u scripts/quantize_rp3_onnx.py --export-dir "$RUN/onnx" ;;
  calibrate) "$PYTHON" -u scripts/calibrate_rp3_thresholds.py --config "$CONFIG" --export-dir "$RUN/onnx" ;;
  diagnose) "$PYTHON" -u scripts/diagnose_rp3_lec.py --config "$CONFIG" --export-dir "$RUN/onnx" --output-dir "${RP3_DIAGNOSTIC_DIR:-$RUN/diagnostics_v1}" ;;
  evaluate) "$PYTHON" -u scripts/evaluate_rp3_lec.py --config "$CONFIG" --export-dir "$RUN/onnx" --output-dir "$RUN/evaluation" ;;
  all)
    for next in preflight teacher mp008 features train route export quantize calibrate evaluate; do
      echo "[RP3 stage] $next"
      bash "$0" "$next"
    done
    ;;
  *) echo "Unknown RP3 stage: $stage" >&2; exit 2 ;;
esac
