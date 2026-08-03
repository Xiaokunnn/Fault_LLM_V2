#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"
CONFIG="${RP2_CONFIG:-configs/rp2_graphrag_v2_development_v2.json}"

echo "[RP2 server] root=$ROOT"
echo "[RP2 server] python=$($PYTHON --version 2>&1)"
echo "[RP2 server] config=$CONFIG"

if [[ ! -d data/model/BAAI-bge-m3 ]]; then
  echo "Missing model: data/model/BAAI-bge-m3" >&2
  exit 2
fi

echo "========== 0/4 CUDA preflight =========="
"$PYTHON" -u scripts/check_rp2_cuda.py
if [[ ! -d data/model/Qwen2.5-7B-Instruct ]]; then
  echo "Missing model: data/model/Qwen2.5-7B-Instruct" >&2
  exit 2
fi

echo "========== 1/4 Full-graph development benchmark =========="
"$PYTHON" -u scripts/build_rp2_full_graph_benchmark.py

echo "========== 2/4 BGE-M3 dense evidence index =========="
"$PYTHON" -u scripts/build_rp2_dense_index.py --config "$CONFIG" --require-cuda

echo "========== 3/4 Retrieval sensitivity =========="
"$PYTHON" -u scripts/run_rp2_graphrag_v2_sensitivity.py --config "$CONFIG" --require-cuda "$@"

echo "========== 4/4 GraphRAG v2 retrieval + Qwen generation =========="
"$PYTHON" -u scripts/run_rp2_graphrag_v2.py --config "$CONFIG" --require-cuda "$@"

echo "[RP2 server] completed. Results: results/experiments/research_point_2/graphrag_v2_development_v2"
