#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
  else
    PYTHON="$(command -v python3 || true)"
  fi
fi
[[ -n "$PYTHON" && -x "$PYTHON" ]] || {
  echo "Python executable not found. Set PYTHON=/absolute/path/to/python." >&2
  exit 2
}

cleanup_secret() {
  unset DASHSCOPE_API_KEY || true
}
trap cleanup_secret EXIT

run_step() {
  local name="$1"
  shift
  echo
  echo "========== $name =========="
  "$PYTHON" -u "$@"
}

STARTED=$SECONDS

run_step "1/3 Repair evidence coverage gaps locally" \
  scripts/repair_full_graph_evidence_gaps.py

if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
  read -r -s -p "Enter DASHSCOPE_API_KEY (input is hidden): " DASHSCOPE_API_KEY
  echo
  export DASHSCOPE_API_KEY
fi
[[ -n "${DASHSCOPE_API_KEY:-}" ]] || {
  echo "DASHSCOPE_API_KEY must not be empty." >&2
  exit 2
}

run_step "2/3 Govern fault-core Chinese Silver terminology" \
  scripts/run_silver_terminology_governance.py

cleanup_secret

run_step "3/3 Rebuild raw and Chinese-validated graph" \
  scripts/build_versioned_knowledge_graph.py \
  --input \
  data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_governed/candidate_triples.zh_governed.jsonl \
  --output-root data/kg/marine_pump

echo
echo "========== Full graph release repair result =========="
echo "Evidence coverage: data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/coverage_evidence_only.json"
echo "Terminology governance: data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_governed/terminology_governance_summary.json"
echo "Validated graph: data/kg/marine_pump/graph_versions/KG_v1_validated"
echo "Rerun the same command after interruption; terminology calls reuse cache."
printf 'Total elapsed: %d minutes %d seconds\n' "$(((SECONDS-STARTED)/60))" "$(((SECONDS-STARTED)%60))"
