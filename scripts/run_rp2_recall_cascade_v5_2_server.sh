#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"
CONFIG="${RP2_CONFIG:-configs/rp2_graphrag_v5_2_recall_cascade.json}"
FROZEN="results/experiments/research_point_2/graphrag_v4_faithfulness/retrieval_results.jsonl"

echo "[RP2 v5.2] two-stage recall cascade with rotating interleaved timing"
echo "[RP2 v5.2] frozen retrieval=$FROZEN"
echo "[RP2 v5.2] graph and BGE-M3 will not be loaded"

if [[ ! -f "$FROZEN" ]]; then
  echo "Missing frozen retrieval results: $FROZEN" >&2
  exit 2
fi
if [[ ! -d data/model/Qwen2.5-7B-Instruct ]]; then
  echo "Missing model: data/model/Qwen2.5-7B-Instruct" >&2
  exit 2
fi

echo "========== 0/2 CUDA preflight =========="
"$PYTHON" -u scripts/check_rp2_cuda.py

echo "========== 1/2 Interleaved repeated precision-mask + recall review =========="
"$PYTHON" -u scripts/run_rp2_recall_cascade_v5_2.py \
  --config "$CONFIG" \
  --require-cuda \
  "$@"

echo "========== 2/2 Local paper-readiness summary =========="
"$PYTHON" -u scripts/summarize_rp2_v4_targets.py --config "$CONFIG"

echo "[RP2 v5.2] local stage completed"
echo "Next: RP2_JUDGE_CONFIG=configs/rp2_semantic_judge_qwen3_7_max_v5_cascade.json RP2_TARGET_CONFIG=$CONFIG bash scripts/run_rp2_semantic_judge_v2_secure.sh"
