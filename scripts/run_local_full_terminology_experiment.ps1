param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if ([string]::IsNullOrWhiteSpace($Python)) {
    $VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $VenvPython) {
        $Python = $VenvPython
    }
    else {
        $Python = (Get-Command python -ErrorAction Stop).Source
    }
}

$Root = "data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full"

function Invoke-Step {
    param([string]$Name, [string[]]$Arguments)
    Write-Host ""
    Write-Host "========== $Name =========="
    & $Python -u @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Invoke-Step "1/7 Local full terminology governance" @(
    "scripts/run_local_full_terminology_experiment.py"
)
Invoke-Step "2/7 Build standard graph" @(
    "scripts/build_versioned_knowledge_graph.py",
    "--input", "$Root/candidate_triples.zh_local_full.jsonl",
    "--output-root", "$Root/standard_graph"
)
Invoke-Step "3/7 Build conservative graph" @(
    "scripts/build_versioned_knowledge_graph.py",
    "--input", "$Root/candidate_triples.zh_local_conservative.jsonl",
    "--output-root", "$Root/conservative_graph"
)
Invoke-Step "4/7 Validate standard graph" @(
    "scripts/generate_graph_constraint_report_v1.py",
    "--graph-root", "$Root/standard_graph",
    "--terminology", "$Root/entity_terminology_zh_marine_pump_v5_local_full.json",
    "--output-dir", "$Root/standard_constraint_report",
    "--fail-on-blocked"
)
Invoke-Step "5/7 Validate conservative graph" @(
    "scripts/generate_graph_constraint_report_v1.py",
    "--graph-root", "$Root/conservative_graph",
    "--terminology", "$Root/terminology_conservative.json",
    "--output-dir", "$Root/conservative_constraint_report",
    "--fail-on-blocked"
)
Invoke-Step "6/7 Evaluate standard graph CQ" @(
    "scripts/evaluate_cq_v1.py",
    "--layered-jsonl-root", "$Root/standard_graph/triples/KG_v1_validated",
    "--graphml", "$Root/standard_graph/graph_versions/KG_v1_validated/marine_pump_graph.graphml",
    "--output-dir", "$Root/standard_cq_v1"
)
Invoke-Step "7/7 Evaluate conservative graph CQ" @(
    "scripts/evaluate_cq_v1.py",
    "--layered-jsonl-root", "$Root/conservative_graph/triples/KG_v1_validated",
    "--graphml", "$Root/conservative_graph/graph_versions/KG_v1_validated/marine_pump_graph.graphml",
    "--output-dir", "$Root/conservative_cq_v1"
)

Write-Host ""
Write-Host "Local full terminology experiment complete: $Root"
