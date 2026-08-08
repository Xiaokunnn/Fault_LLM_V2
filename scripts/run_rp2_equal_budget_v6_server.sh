#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python}"
BASE_CONFIG="${RP2_V6_CONFIG:-configs/rp2_graphrag_v6_equal_budget.json}"
LIMIT=0
FORCE_GENERATION=0
FORCE_RETRIEVAL=0

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_rp2_equal_budget_v6_server.sh [options]

Options:
  --limit N             Run the first N queries as an isolated smoke test under .tmp/.
  --force-generation    Ignore generation checkpoints/cache and regenerate outputs.
  --force-retrieval     Replace the fresh retrieval-latency artifact.
  -h, --help            Show this help.

Environment:
  PYTHON                 Python executable (default: python).
  RP2_V6_CONFIG          Main v6 config (default: configs/rp2_graphrag_v6_equal_budget.json).

The default full run is non-destructive: completed fresh-retrieval timing is
reused and generation resumes from its measurement checkpoint. Use a force
flag only when an intentional rerun is required.
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
    --force-generation)
      FORCE_GENERATION=1
      shift
      ;;
    --force-retrieval)
      FORCE_RETRIEVAL=1
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

if [[ ! -f "$BASE_CONFIG" ]]; then
  echo "Missing v6 config: $BASE_CONFIG" >&2
  exit 2
fi
if ! command -v "$PYTHON" >/dev/null 2>&1 && [[ ! -x "$PYTHON" ]]; then
  echo "Python executable is unavailable: $PYTHON" >&2
  exit 2
fi

read_config_value() {
  "$PYTHON" - "$BASE_CONFIG" "$1" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = payload
for key in sys.argv[2].split("."):
    value = value[key]
print(value)
PY
}

BENCHMARK_DIR="$(read_config_value benchmark_dir)"
PROTOCOL_ID="$(read_config_value protocol_id)"
REPLAY_PATH="$(read_config_value frozen_retrieval_results)"
FORMAL_GENERATION_DIR="$(read_config_value output_dir)"
FORMAL_RETRIEVAL_DIR="$(read_config_value retrieval_latency_output_dir)"
PREPARE_SCRIPT="$($PYTHON - "$BASE_CONFIG" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(payload.get("replay_preparation_script", "scripts/prepare_rp2_v6_equal_budget_replay.py"))
PY
)"

if [[ ! -f "$PREPARE_SCRIPT" ]]; then
  echo "Missing replay preparation script: $PREPARE_SCRIPT" >&2
  exit 2
fi
if [[ ! "$PROTOCOL_ID" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Unsafe protocol_id for isolated output path: $PROTOCOL_ID" >&2
  exit 2
fi

RUN_CONFIG="$BASE_CONFIG"
GENERATION_DIR="$FORMAL_GENERATION_DIR"
RETRIEVAL_DIR="$FORMAL_RETRIEVAL_DIR"
LIMIT_ARGS=()

if [[ "$LIMIT" -gt 0 ]]; then
  # Keep smoke artifacts isolated by protocol so a frozen v6 run cannot be
  # mistaken for a compatible v6.1 result (or vice versa).
  SMOKE_ROOT=".tmp/${PROTOCOL_ID}_smoke/limit_${LIMIT}"
  RUN_CONFIG="$SMOKE_ROOT/config.json"
  GENERATION_DIR="$SMOKE_ROOT/generation"
  RETRIEVAL_DIR="$SMOKE_ROOT/retrieval_latency"
  LIMIT_ARGS=(--limit "$LIMIT")
  mkdir -p "$SMOKE_ROOT"
  "$PYTHON" - "$BASE_CONFIG" "$RUN_CONFIG" "$SMOKE_ROOT" <<'PY'
import json
import sys
from pathlib import Path

source, destination, smoke_root = map(Path, sys.argv[1:])
payload = json.loads(source.read_text(encoding="utf-8"))
payload["status"] = "isolated_limit_smoke_not_formal_result"
payload["output_dir"] = (smoke_root / "generation").as_posix()
payload["retrieval_latency_output_dir"] = (smoke_root / "retrieval_latency").as_posix()
payload["generator"]["cache_dir"] = (smoke_root / "model_cache").as_posix()
destination.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
fi

echo "[RP2 v6] config=$BASE_CONFIG"
if [[ "$LIMIT" -gt 0 ]]; then
  echo "[RP2 v6] mode=SMOKE, queries=$LIMIT, isolated_root=$(dirname "$RUN_CONFIG")"
else
  echo "[RP2 v6] mode=FORMAL_FULL, resume=true, force_generation=$FORCE_GENERATION, force_retrieval=$FORCE_RETRIEVAL"
fi
echo "[RP2 v6] quality=repeat0 only; timing=3 independent interleaved repeats; quality fusion=NONE"

echo "========== 1/6 Prepare and verify immutable retrieval replay =========="
"$PYTHON" -u "$PREPARE_SCRIPT" --config "$BASE_CONFIG"
"$PYTHON" -u "$PREPARE_SCRIPT" \
  --config "$BASE_CONFIG" \
  --verify-only

echo "========== 2/6 CUDA preflight =========="
"$PYTHON" -u scripts/check_rp2_cuda.py

retrieval_complete() {
  "$PYTHON" - "$BASE_CONFIG" "$RETRIEVAL_DIR" "$LIMIT" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
output = Path(sys.argv[2])
limit = int(sys.argv[3])
rows_path = output / "retrieval_latency_runs.jsonl"
summary_path = output / "retrieval_latency_summary.json"
if not rows_path.is_file() or not summary_path.is_file():
    raise SystemExit(1)

config = json.loads(config_path.read_text(encoding="utf-8"))
summary = json.loads(summary_path.read_text(encoding="utf-8"))
query_total = sum(
    1
    for line in (Path(config["benchmark_dir"]) / "queries.jsonl").open(encoding="utf-8-sig")
    if line.strip()
)
expected_queries = min(limit, query_total) if limit else query_total
expected_methods = len(config["scenarios"])
expected_repeats = int(config["latency_protocol"]["interleaved_repeats"])
expected_rows = expected_queries * expected_methods * expected_repeats
actual_rows = sum(1 for line in rows_path.open(encoding="utf-8-sig") if line.strip())
config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()

valid = (
    summary.get("protocol_id") == config.get("protocol_id")
    and int(summary.get("queries", -1)) == expected_queries
    and int(summary.get("measurement_repeats", -1)) == expected_repeats
    and bool(summary.get("all_rankings_match_immutable_replay"))
    and summary.get("inputs", {}).get("config", {}).get("sha256") == config_sha
    and len(summary.get("methods", {})) == expected_methods
    and actual_rows == expected_rows
)
raise SystemExit(0 if valid else 1)
PY
}

echo "========== 3/6 Fresh CUDA-synchronized retrieval latency =========="
if [[ "$FORCE_RETRIEVAL" -eq 0 ]] && retrieval_complete; then
  echo "[RP2 v6 retrieval] verified completed artifact; reuse=$RETRIEVAL_DIR"
else
  if [[ "$FORCE_RETRIEVAL" -eq 0 && -d "$RETRIEVAL_DIR" ]] && \
     [[ -n "$(find "$RETRIEVAL_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    echo "Incomplete or incompatible retrieval output: $RETRIEVAL_DIR" >&2
    echo "Inspect it, then rerun with --force-retrieval to replace it intentionally." >&2
    exit 2
  fi
  RETRIEVAL_ARGS=(
    --config "$BASE_CONFIG"
    --output-dir "$RETRIEVAL_DIR"
    "${LIMIT_ARGS[@]}"
  )
  if [[ "$FORCE_RETRIEVAL" -eq 1 ]]; then
    RETRIEVAL_ARGS+=(--force)
  fi
  "$PYTHON" -u scripts/run_rp2_v6_retrieval_latency.py "${RETRIEVAL_ARGS[@]}"
fi

echo "========== 4/6 Equal-budget generation and verifier =========="
GENERATION_ARGS=(
  --config "$RUN_CONFIG"
  --require-cuda
  --resume
  "${LIMIT_ARGS[@]}"
)
if [[ "$FORCE_GENERATION" -eq 1 ]]; then
  GENERATION_ARGS+=(--force-generation)
fi
"$PYTHON" -u scripts/run_rp2_equal_budget_v6.py "${GENERATION_ARGS[@]}"

echo "========== 5/6 Paper-ready Silver summary =========="
"$PYTHON" -u scripts/summarize_rp2_equal_budget_v6.py \
  --config "$RUN_CONFIG" \
  --experiment-dir "$GENERATION_DIR" \
  --retrieval-results "$REPLAY_PATH" \
  --retrieval-latency-results "$RETRIEVAL_DIR/retrieval_latency_runs.jsonl" \
  --queries "$BENCHMARK_DIR/queries.jsonl" \
  --output-dir "$GENERATION_DIR/paper_summary"

echo "========== 6/6 Data-system and provenance footprint =========="
"$PYTHON" -u scripts/report_rp2_v6_data_system_footprint.py \
  --config "$BASE_CONFIG" \
  --output-dir "$GENERATION_DIR/paper_summary"

echo "========== RP2 v6 completed =========="
echo "Generation: $GENERATION_DIR"
echo "Fresh retrieval latency: $RETRIEVAL_DIR"
echo "Paper summary: $GENERATION_DIR/paper_summary"
if [[ "$LIMIT" -gt 0 ]]; then
  echo "NOTE: This is an isolated smoke result under .tmp and must not be cited as the formal full result."
fi
