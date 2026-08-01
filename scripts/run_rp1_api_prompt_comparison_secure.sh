#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"

if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
  read -r -s -p "Enter DASHSCOPE_API_KEY: " DASHSCOPE_API_KEY
  echo
  export DASHSCOPE_API_KEY
  cleanup_key=1
else
  cleanup_key=0
fi
trap '[[ ${cleanup_key:-0} -eq 1 ]] && unset DASHSCOPE_API_KEY' EXIT

"$PYTHON" -u scripts/run_rp1_api_prompt_comparison.py "$@"
