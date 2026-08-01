#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"

echo "[RP2 server] root=$ROOT"
echo "[RP2 server] python=$($PYTHON --version 2>&1)"

if [[ ! -d data/mode/BAAI-bge-m3 ]]; then
  echo "Missing model: data/mode/BAAI-bge-m3" >&2
  exit 2
fi
if [[ ! -d data/mode/Qwen2.5-7B-Instruct ]]; then
  echo "Missing model: data/mode/Qwen2.5-7B-Instruct" >&2
  exit 2
fi

echo "========== 1/4 Full-graph development benchmark =========="
"$PYTHON" -u scripts/build_rp2_full_graph_benchmark.py

echo "========== 2/4 BGE-M3 dense evidence index =========="
"$PYTHON" -u scripts/build_rp2_dense_index.py

echo "========== 3/4 Retrieval sensitivity =========="
"$PYTHON" -u scripts/run_rp2_graphrag_v2_sensitivity.py "$@"

echo "========== 4/4 GraphRAG v2 retrieval + Qwen generation =========="
"$PYTHON" -u scripts/run_rp2_graphrag_v2.py "$@"

echo "[RP2 server] completed. Results: results/experiments/research_point_2/graphrag_v2_development"
