#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python}"
CONFIG="${RP2_V6_JUDGE_CONFIG:-configs/rp2_semantic_judge_qwen3_7_max_v6_equal_budget.json}"
LIMIT=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_rp2_v6_semantic_judge_secure.sh [--limit N] [--dry-run]

The DashScope key is requested with hidden input, exported only for this
process, and removed on every exit. The key is never written to a file or
placed in shell history.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit)
      if [[ $# -lt 2 || ! "$2" =~ ^[1-9][0-9]*$ ]]; then
        echo "--limit requires a positive integer" >&2
        exit 2
      fi
      LIMIT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$CONFIG" ]]; then
  echo "Missing v6 semantic-judge config: $CONFIG" >&2
  exit 2
fi

ARGS=(--config "$CONFIG")
if [[ "$LIMIT" -gt 0 ]]; then
  ARGS+=(--limit "$LIMIT")
fi
if [[ "$DRY_RUN" -eq 1 ]]; then
  ARGS+=(--dry-run)
else
  read -r -s -p "Enter a NEW DASHSCOPE_API_KEY (input is hidden): " DASHSCOPE_API_KEY
  echo
  if [[ -z "$DASHSCOPE_API_KEY" ]]; then
    echo "DASHSCOPE_API_KEY cannot be empty" >&2
    exit 2
  fi
  export DASHSCOPE_API_KEY
  trap 'unset DASHSCOPE_API_KEY' EXIT INT TERM
fi

"$PYTHON" -u scripts/run_rp2_dual_prompt_semantic_judge.py "${ARGS[@]}"

if [[ "$DRY_RUN" -eq 0 ]]; then
  unset DASHSCOPE_API_KEY
  trap - EXIT INT TERM
fi

echo "[RP2 v6 judge] same-model, dual-prompt consistency audit completed"
echo "[RP2 v6 judge] labels remain Silver; this is not expert review"
