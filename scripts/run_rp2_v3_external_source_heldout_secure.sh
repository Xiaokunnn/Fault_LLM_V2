#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"
EXTRACTION_CONFIG="configs/triple_extraction_qwen3_7_max_heldout_external_v3.json"
RP2_CONFIG="configs/rp2_graphrag_v3_external_source_heldout.json"
PAGE_DIR="data/interim/parsed_pages/heldout_external_v1"
POOL_DIR="data/interim/candidate_pages/heldout_external_v1"
CANDIDATE_DIR="data/interim/heldout_external/rp1_extraction_v3"
STRICT_DIR="data/interim/heldout_external/rp1_strict_v3"
FINAL_DIR="data/interim/heldout_external/shared_silver_v3"

echo "[RP2 external] verifying committed freeze before any external model call"
"$PYTHON" -u scripts/verify_rp2_v3_external_freeze.py --external-config "$RP2_CONFIG"
"$PYTHON" -u scripts/check_rp2_cuda.py
"$PYTHON" -u scripts/build_heldout_external_page_plan.py

read -r -s -p "Enter a NEW DASHSCOPE_API_KEY (input is hidden): " DASHSCOPE_API_KEY
echo
if [[ -z "$DASHSCOPE_API_KEY" ]]; then
  echo "DASHSCOPE_API_KEY must not be empty" >&2
  exit 2
fi
export DASHSCOPE_API_KEY
trap 'unset DASHSCOPE_API_KEY' EXIT

echo "========== 1/7 Frozen extraction: MP010-MP013 =========="
"$PYTHON" -u scripts/run_targeted_triple_extraction.py \
  --config "$EXTRACTION_CONFIG" \
  --candidate-pool "$POOL_DIR/candidate_pages.jsonl" \
  --input-dir "$PAGE_DIR" \
  --output-dir "$CANDIDATE_DIR"

echo "========== 2/7 Frozen strict validation =========="
"$PYTHON" -u scripts/run_targeted_strict_validation.py \
  --config "$EXTRACTION_CONFIG" \
  --candidate-dir "$CANDIDATE_DIR" \
  --input-dir "$PAGE_DIR" \
  --output-dir "$STRICT_DIR" \
  --schema data/kg/marine_pump/schema/provenance_schema_v3.json

echo "========== 3/7 Dual-pass external Silver adjudication =========="
"$PYTHON" -u scripts/run_automatic_silver_adjudication.py \
  --config "$EXTRACTION_CONFIG" \
  --input-dir "$STRICT_DIR" \
  --output-dir "$FINAL_DIR" \
  --allowed-splits held_out_test \
  --external-silver-mode

unset DASHSCOPE_API_KEY

echo "========== 4/7 Isolated external Silver benchmark =========="
"$PYTHON" -u scripts/prepare_shared_heldout_evaluation.py \
  --input "$FINAL_DIR/candidate_triples.auto_adjudicated_silver.jsonl" \
  --output-root results/experiments/heldout_external_v3

echo "========== 5/7 Isolated external BGE-M3 index =========="
"$PYTHON" -u scripts/build_rp2_dense_index.py \
  --config "$RP2_CONFIG" \
  --require-cuda \
  --force

echo "========== 6/7 Frozen external retrieval + Qwen generation =========="
"$PYTHON" -u scripts/run_rp2_graphrag_v2.py \
  --config "$RP2_CONFIG" \
  --require-cuda

echo "========== 7/7 External evaluation complete =========="
echo "Results: results/experiments/heldout_external_v3"
echo "Results: results/experiments/research_point_2/graphrag_v3_external_source_heldout"
echo "Do not alter frozen parameters or rerun external results for model selection."
