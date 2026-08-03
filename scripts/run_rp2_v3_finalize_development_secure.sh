#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"

echo "========== 1/4 CUDA and model preflight =========="
"$PYTHON" -u scripts/check_rp2_cuda.py

echo "========== 2/4 Counterbalanced repeated latency replay =========="
"$PYTHON" -u scripts/run_rp2_interleaved_latency_replay.py --repeats 5 --warmups 2

echo "========== 3/4 Dual-prompt qwen3.7-max Silver semantic audit =========="
read -r -s -p "Enter a NEW DASHSCOPE_API_KEY (input is hidden): " DASHSCOPE_API_KEY
echo
if [[ -z "$DASHSCOPE_API_KEY" ]]; then
  echo "DASHSCOPE_API_KEY must not be empty" >&2
  exit 2
fi
export DASHSCOPE_API_KEY
trap 'unset DASHSCOPE_API_KEY' EXIT
"$PYTHON" -u scripts/run_rp2_dual_prompt_semantic_judge.py
unset DASHSCOPE_API_KEY

echo "========== 4/4 Create pre-external freeze manifest =========="
"$PYTHON" -u scripts/freeze_rp2_v3_protocol.py

echo "[RP2 finalize] development finalization complete."
echo "Commit latency, Judge, and configs/frozen/rp2_v3_frozen_protocol.json before external evaluation."
