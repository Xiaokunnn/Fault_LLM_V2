#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"
CONFIG="${RP2_CONFIG:-configs/rp2_graphrag_v3_budget_effectiveness.json}"

echo "[RP2 v3 server] root=$ROOT"
echo "[RP2 v3 server] python=$($PYTHON --version 2>&1)"
echo "[RP2 v3 server] config=$CONFIG"

if [[ ! -d data/model/BAAI-bge-m3 ]]; then
  echo "Missing model: data/model/BAAI-bge-m3" >&2
  exit 2
fi
if [[ ! -d data/model/Qwen2.5-7B-Instruct ]]; then
  echo "Missing model: data/model/Qwen2.5-7B-Instruct" >&2
  exit 2
fi

echo "========== 0/4 CUDA and model-format preflight =========="
"$PYTHON" -u scripts/check_rp2_cuda.py

echo "========== 1/4 Leakage-safe development benchmark =========="
"$PYTHON" -u scripts/build_rp2_full_graph_benchmark.py

echo "========== 2/4 BGE-M3 evidence index =========="
"$PYTHON" -u scripts/build_rp2_dense_index.py --config "$CONFIG" --require-cuda

echo "========== 3/4 Budget-matched retrieval and Qwen generation =========="
"$PYTHON" -u scripts/run_rp2_graphrag_v2.py \
  --config "$CONFIG" \
  --require-cuda \
  "$@"

echo "[RP2 v3 server] completed"
echo "[RP2 v3 server] results=results/experiments/research_point_2/graphrag_v3_budget_effectiveness"
