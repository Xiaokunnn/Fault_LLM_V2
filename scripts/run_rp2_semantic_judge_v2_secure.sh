#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"
CONFIG="${RP2_JUDGE_CONFIG:-configs/rp2_semantic_judge_qwen3_7_max_v2.json}"

read -r -s -p "Enter a NEW DASHSCOPE_API_KEY (input is hidden): " DASHSCOPE_API_KEY
echo
if [[ -z "$DASHSCOPE_API_KEY" ]]; then
  echo "DASHSCOPE_API_KEY must not be empty" >&2
  exit 2
fi
export DASHSCOPE_API_KEY
trap 'unset DASHSCOPE_API_KEY' EXIT

"$PYTHON" -u scripts/run_rp2_dual_prompt_semantic_judge.py --config "$CONFIG" "$@"
"$PYTHON" -u scripts/summarize_rp2_v4_targets.py
