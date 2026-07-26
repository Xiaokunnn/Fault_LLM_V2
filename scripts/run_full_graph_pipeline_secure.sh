#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON=""
LIMIT=0
LOCAL_ONLY=0
SKIP_ADJUDICATION=0

usage() {
  echo "Usage: $0 [--python PATH] [--limit N] [--local-only] [--skip-adjudication]"
}

while (($#)); do
  case "$1" in
    --python) PYTHON="${2:?--python requires a path}"; shift 2 ;;
    --limit) LIMIT="${2:?--limit requires an integer}"; shift 2 ;;
    --local-only) LOCAL_ONLY=1; shift ;;
    --skip-adjudication) SKIP_ADJUDICATION=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$PYTHON" ]]; then
  if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
  else
    PYTHON="$(command -v python3 || true)"
  fi
fi
[[ -n "$PYTHON" && -x "$PYTHON" ]] || { echo "Python executable not found. Use --python PATH." >&2; exit 2; }
[[ "$LIMIT" =~ ^[0-9]+$ ]] || { echo "--limit must be a non-negative integer." >&2; exit 2; }

CONFIG="configs/triple_extraction_qwen3_7_max_full_corpus_v1.json"
POOL="data/interim/candidate_pages/full_extraction_v1/candidate_pages.jsonl"
CANDIDATE_DIR="data/interim/candidate_triples/qwen3_7_max_full_corpus_v1"
STRICT_DIR="${CANDIDATE_DIR}_strict_v3"
FINAL_DIR="${CANDIDATE_DIR}_auto_adjudicated"
STARTED=$SECONDS

run_step() {
  local name="$1"
  shift
  echo
  echo "========== $name =========="
  "$PYTHON" -u "$@"
}

run_step "1/5 Build deterministic all-page plan" \
  scripts/build_full_extraction_page_plan.py

EXTRACTION_ARGS=(
  scripts/run_targeted_triple_extraction.py
  --config "$CONFIG"
  --candidate-pool "$POOL"
  --input-dir data/interim/parsed_pages/corpus_v2
  --output-dir "$CANDIDATE_DIR"
)
((LIMIT > 0)) && EXTRACTION_ARGS+=(--limit "$LIMIT")

if ((LOCAL_ONLY)); then
  EXTRACTION_ARGS+=(--dry-run)
  run_step "2/5 Validate prompts and local inputs without API" "${EXTRACTION_ARGS[@]}"
  echo
  echo "Local-only validation completed. No external model call was made."
  exit 0
fi

cleanup_secret() {
  unset DASHSCOPE_API_KEY || true
}
trap cleanup_secret EXIT

if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
  read -r -s -p "Enter DASHSCOPE_API_KEY (input is hidden): " DASHSCOPE_API_KEY
  echo
  export DASHSCOPE_API_KEY
fi
[[ -n "${DASHSCOPE_API_KEY:-}" ]] || { echo "DASHSCOPE_API_KEY must not be empty." >&2; exit 2; }

run_step "2/5 Extract build-train pages with qwen3.7-max" "${EXTRACTION_ARGS[@]}"
run_step "3/5 Strict evidence, schema, scope and Chinese validation" \
  scripts/run_targeted_strict_validation.py \
  --config "$CONFIG" \
  --candidate-dir "$CANDIDATE_DIR" \
  --input-dir data/interim/parsed_pages/corpus_v2 \
  --output-dir "$STRICT_DIR" \
  --schema data/kg/marine_pump/schema/provenance_schema_v3.json

GRAPH_INPUT="$STRICT_DIR/candidate_triples.strict_v2.jsonl"
if ((SKIP_ADJUDICATION == 0)); then
  run_step "4/5 Dual-pass automatic Silver adjudication" \
    scripts/run_automatic_silver_adjudication.py \
    --config "$CONFIG" \
    --input-dir "$STRICT_DIR" \
    --output-dir "$FINAL_DIR"
  GRAPH_INPUT="$FINAL_DIR/candidate_triples.auto_adjudicated_silver.jsonl"
else
  echo
  echo "========== 4/5 Automatic semantic adjudication skipped =========="
fi

run_step "5/5 Build KG_v1_raw and Chinese-ready KG_v1_validated" \
  scripts/build_versioned_knowledge_graph.py \
  --input "$GRAPH_INPUT" \
  --output-root data/kg/marine_pump

echo
echo "========== Full graph pipeline result =========="
echo "Raw graph: data/kg/marine_pump/graph_versions/KG_v1_raw"
echo "Validated graph: data/kg/marine_pump/graph_versions/KG_v1_validated"
echo "Resume policy: rerun the same command; completed page and adjudication responses are reused from cache."
printf 'Total elapsed: %d minutes %d seconds\n' "$(((SECONDS-STARTED)/60))" "$(((SECONDS-STARTED)%60))"
