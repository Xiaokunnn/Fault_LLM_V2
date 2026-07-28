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
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

function Invoke-PipelineStep {
    param(
        [string]$Name,
        [string[]]$Arguments
    )
    Write-Host ""
    Write-Host "========== $Name =========="
    & $Python -u @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

$Started = Get-Date
$SecureKey = $null
$KeyPointer = [IntPtr]::Zero

try {
    Invoke-PipelineStep `
        -Name "1/4 Repair evidence coverage gaps locally" `
        -Arguments @("scripts/repair_full_graph_evidence_gaps.py")

    if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
        $SecureKey = Read-Host `
            "Enter DASHSCOPE_API_KEY (input is hidden)" `
            -AsSecureString
        $KeyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR(
            $SecureKey
        )
        $env:DASHSCOPE_API_KEY = `
            [Runtime.InteropServices.Marshal]::PtrToStringBSTR($KeyPointer)
    }
    if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
        throw "DASHSCOPE_API_KEY must not be empty."
    }

    Invoke-PipelineStep `
        -Name "2/4 Govern fault-core Chinese Silver terminology" `
        -Arguments @(
            "scripts/run_silver_terminology_governance.py",
            "--allow-incomplete"
        )

    Invoke-PipelineStep `
        -Name "3/4 Reconcile only Chinese release-gap terminology" `
        -Arguments @(
            "scripts/reconcile_chinese_terminology_release_gaps.py"
        )
}
finally {
    Remove-Item Env:DASHSCOPE_API_KEY -ErrorAction SilentlyContinue
    if ($KeyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($KeyPointer)
    }
    $SecureKey = $null
}

Invoke-PipelineStep `
    -Name "4/4 Rebuild raw and Chinese-validated graph" `
    -Arguments @(
        "scripts/build_versioned_knowledge_graph.py",
        "--input",
        "data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_reconciled/candidate_triples.zh_reconciled.jsonl",
        "--output-root",
        "data/kg/marine_pump"
    )

$Elapsed = (Get-Date) - $Started
Write-Host ""
Write-Host "========== Full graph release repair result =========="
Write-Host "Evidence coverage: data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/coverage_evidence_only.json"
Write-Host "Terminology reconciliation: data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_reconciled/reconciliation_summary.json"
Write-Host "Validated graph: data/kg/marine_pump/graph_versions/KG_v1_validated"
Write-Host (
    "Total elapsed: {0} minutes {1} seconds" -f
    [Math]::Floor($Elapsed.TotalMinutes),
    $Elapsed.Seconds
)
