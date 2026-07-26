param(
    [string]$Python = "",
    [switch]$LocalOnly,
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot
$Bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$PythonExe = if (-not [string]::IsNullOrWhiteSpace($Python)) { $Python } elseif (Test-Path $Bundled) { $Bundled } else { "python" }
$Started = Get-Date

function Invoke-PythonStep {
    param([string]$Name, [string[]]$Arguments)
    Write-Host ""
    Write-Host "========== $Name =========="
    & $PythonExe -u @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

$PoolDir = "data/interim/candidate_pages/corpus_retrieval_v3_source_supplement"
$Pool = "$PoolDir/candidate_pages.jsonl"
$CandidateDir = "data/interim/candidate_triples/qwen3_7_max_corpus_retrieval_v3_source_supplement"
$StrictDir = "${CandidateDir}_strict_v3_auto_normalized"
$FinalDir = "${CandidateDir}_strict_v4_auto_adjudicated"

Invoke-PythonStep "1/6 Verify 16 documents and 1941 parsed pages" @(
    "scripts\run_corpus_ingest.py"
)
Invoke-PythonStep "2/6 Rebuild full-text index" @(
    "scripts\build_page_index.py"
)
Invoke-PythonStep "3/6 Build v3 wide-recall candidate pool" @(
    "scripts\build_candidate_page_pool.py",
    "--config", "configs/corpus_candidate_retrieval_marine_pump_v2_large_audit.json",
    "--output-dir", $PoolDir
)

$PoolSummary = Get-Content "$PoolDir/retrieval_summary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$Pages = [int]$PoolSummary.candidate_pages
$ApiPages = 103
Write-Host "Candidate pages: $Pages"
Write-Host "Compatible old-page cache: 326 pages"
Write-Host "Expected new API pages: approximately $ApiPages"
Write-Host "Estimated total external-model time: approximately 25-35 minutes."
if ($LocalOnly) {
    Write-Host "LocalOnly selected; no external model call was made."
    exit 0
}

$SecureKey = Read-Host "Enter a NEW DASHSCOPE_API_KEY (input is hidden)" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
try {
    $env:DASHSCOPE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
        throw "DASHSCOPE_API_KEY must not be empty."
    }
    $ExtractionArgs = @(
        "scripts\run_targeted_triple_extraction.py",
        "--candidate-pool", $Pool,
        "--input-dir", "data/interim/parsed_pages/corpus_v2",
        "--output-dir", $CandidateDir,
        "--reuse-cache-dir", "data/interim/candidate_triples/qwen3_7_max_corpus_retrieval_v2_large_audit",
        "--reuse-cache-dir", "data/interim/candidate_triples/qwen3_7_max_corpus_retrieval_v1"
    )
    if ($Limit -gt 0) { $ExtractionArgs += @("--limit", "$Limit") }
    Invoke-PythonStep "4/6 Extract source-v3 candidates (resume/cache enabled)" $ExtractionArgs
    Invoke-PythonStep "5/6 Deterministic relation repair and strict validation" @(
        "scripts\run_targeted_strict_validation.py",
        "--candidate-dir", $CandidateDir,
        "--input-dir", "data/interim/parsed_pages/corpus_v2",
        "--output-dir", $StrictDir
    )
    Invoke-PythonStep "6/6 Dual-pass automatic Silver adjudication" @(
        "scripts\run_automatic_silver_adjudication.py",
        "--input-dir", $StrictDir,
        "--output-dir", $FinalDir
    )
} finally {
    Remove-Item Env:DASHSCOPE_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
}

$StrictSummary = Get-Content "$StrictDir/strict_v2_validation_summary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$FinalSummary = Get-Content "$FinalDir/auto_adjudication_summary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$Elapsed = (Get-Date) - $Started
Write-Host ""
Write-Host "========== Final source-v3 Silver result =========="
Write-Host "Strict Silver before semantic adjudication: $($StrictSummary.decisions.silver_candidate)"
Write-Host "Automatically promoted Silver: $($FinalSummary.promoted_to_silver)"
Write-Host "Final Silver: $($FinalSummary.decisions.silver_candidate)"
Write-Host "Final needs review: $($FinalSummary.decisions.candidate_needs_review)"
Write-Host "Final rejected: $($FinalSummary.decisions.rejected)"
Write-Host "Evidence-only classes passing: $($FinalSummary.evidence_only_classes_passing)/10"
Write-Host "Human expert reviewed: $($FinalSummary.human_expert_reviewed)"
Write-Host "Label policy: $($FinalSummary.label_policy)"
Write-Host "Total elapsed: $([math]::Round($Elapsed.TotalMinutes, 1)) minutes"
