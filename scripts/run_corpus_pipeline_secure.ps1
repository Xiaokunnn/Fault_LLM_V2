param(
    [string]$Python = "",
    [switch]$LocalOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot

function Resolve-Python {
    param([string]$Requested)
    $Candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $Candidates += $Requested
    }
    $Bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $Bundled) {
        $Candidates += $Bundled
    }
    $Candidates += "python"
    foreach ($Candidate in $Candidates) {
        try {
            & $Candidate -c "import pdfplumber" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return $Candidate
            }
        }
        catch {
        }
    }
    throw "No Python runtime with pdfplumber was found. Pass -Python <path>."
}

function Invoke-Step {
    param(
        [string]$Name,
        [string[]]$Arguments
    )
    Write-Host ""
    Write-Host "========== $Name =========="
    & $script:PythonExe -u @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

$script:PythonExe = Resolve-Python -Requested $Python
Write-Host "Python: $script:PythonExe"
$PipelineStarted = Get-Date

Invoke-Step "1/6 Full corpus parsing" @(
    "scripts\run_corpus_ingest.py"
)
Invoke-Step "2/6 SQLite page index" @(
    "scripts\build_page_index.py"
)
Invoke-Step "3/6 Candidate page pool" @(
    "scripts\build_candidate_page_pool.py"
)

$SummaryPath = Join-Path $ProjectRoot "data\interim\candidate_pages\corpus_retrieval_v1\retrieval_summary.json"
$Summary = Get-Content -LiteralPath $SummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$CandidatePages = [int]$Summary.candidate_pages
$EstimatedMinutes = [math]::Ceiling($CandidatePages * 20.2 / 60)
Write-Host ""
Write-Host "Candidate pages: $CandidatePages"
Write-Host "Estimated Qwen time: approximately $EstimatedMinutes minutes (resume/cache enabled)."

if ($LocalOnly) {
    Write-Host "LocalOnly selected; stopping before the external model call."
    exit 0
}

$SecureKey = Read-Host "Enter a NEW DASHSCOPE_API_KEY (input is hidden)" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
try {
    $env:DASHSCOPE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
        throw "DASHSCOPE_API_KEY must not be empty."
    }
    Invoke-Step "4/6 Qwen candidate extraction" @(
        "scripts\run_targeted_triple_extraction.py",
        "--candidate-pool",
        "data/interim/candidate_pages/corpus_retrieval_v1/candidate_pages.jsonl",
        "--input-dir",
        "data/interim/parsed_pages/corpus_v2",
        "--output-dir",
        "data/interim/candidate_triples/qwen3_7_max_corpus_retrieval_v1"
    )
}
finally {
    Remove-Item Env:DASHSCOPE_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
}

Invoke-Step "5/6 Strict validation" @(
    "scripts\run_targeted_strict_validation.py",
    "--candidate-dir",
    "data/interim/candidate_triples/qwen3_7_max_corpus_retrieval_v1",
    "--input-dir",
    "data/interim/parsed_pages/corpus_v2",
    "--output-dir",
    "data/interim/candidate_triples/qwen3_7_max_corpus_retrieval_v1_strict_v2"
)

Write-Host ""
Write-Host "========== 6/6 Coverage result =========="
$ValidationSummaryPath = Join-Path $ProjectRoot "data\interim\candidate_triples\qwen3_7_max_corpus_retrieval_v1_strict_v2\strict_v2_validation_summary.json"
$ValidationSummary = Get-Content -LiteralPath $ValidationSummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$Elapsed = (Get-Date) - $PipelineStarted
Write-Host "Strict Silver: $($ValidationSummary.decisions.silver_candidate)"
Write-Host "Needs review: $($ValidationSummary.decisions.candidate_needs_review)"
Write-Host "Rejected: $($ValidationSummary.decisions.rejected)"
Write-Host "Evidence-only classes passing: $($ValidationSummary.fault_classes_passing_evidence_only_audit)/10"
Write-Host "Chinese-release classes passing: $($ValidationSummary.fault_classes_passing_gate)/10"
Write-Host "Total elapsed: $([math]::Round($Elapsed.TotalMinutes, 1)) minutes"
