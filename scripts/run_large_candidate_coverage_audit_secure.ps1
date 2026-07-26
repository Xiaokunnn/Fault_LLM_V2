param(
    [string]$Python = "",
    [switch]$LocalOnly,
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot

function Resolve-Python {
    param([string]$Requested)
    $Candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($Requested)) { $Candidates += $Requested }
    $Bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $Bundled) { $Candidates += $Bundled }
    $Candidates += "python"
    foreach ($Candidate in $Candidates) {
        try {
            & $Candidate -c "import pdfplumber" 2>$null
            if ($LASTEXITCODE -eq 0) { return $Candidate }
        } catch {}
    }
    throw "No Python runtime with pdfplumber was found. Pass -Python <path>."
}

function Invoke-Step {
    param([string]$Name, [string[]]$Arguments)
    Write-Host ""
    Write-Host "========== $Name =========="
    & $script:PythonExe -u @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

$script:PythonExe = Resolve-Python -Requested $Python
$Started = Get-Date
Write-Host "Python: $script:PythonExe"
Write-Host "Mode: large candidate corpus sufficiency audit"

$Pool = "data/interim/candidate_pages/corpus_retrieval_v2_large_audit/candidate_pages.jsonl"
$CandidateDir = "data/interim/candidate_triples/qwen3_7_max_corpus_retrieval_v2_large_audit"
$StrictDir = "${CandidateDir}_strict_v2"

Invoke-Step "1/4 Build 300-500 page wide-recall pool" @(
    "scripts\build_candidate_page_pool.py",
    "--config", "configs/corpus_candidate_retrieval_marine_pump_v2_large_audit.json",
    "--output-dir", "data/interim/candidate_pages/corpus_retrieval_v2_large_audit"
)

$Summary = Get-Content "data/interim/candidate_pages/corpus_retrieval_v2_large_audit/retrieval_summary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$PageCount = [int]$Summary.candidate_pages
$RunPages = if ($Limit -gt 0) { [math]::Min($Limit, $PageCount) } else { $PageCount }
$EstimatedMinutes = [math]::Ceiling($RunPages * 20.2 / 60)
Write-Host "Candidate pages: $PageCount"
Write-Host "Pages in this run: $RunPages"
Write-Host "Estimated Qwen time: approximately $EstimatedMinutes minutes; cached pages resume instantly."

if ($LocalOnly) {
    Write-Host "LocalOnly selected; candidate pool is ready. No API call was made."
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
        "--reuse-cache-dir", "data/interim/candidate_triples/qwen3_7_max_corpus_retrieval_v1"
    )
    if ($Limit -gt 0) { $ExtractionArgs += @("--limit", "$Limit") }
    Invoke-Step "2/4 Qwen large-pool extraction (resume enabled)" $ExtractionArgs
} finally {
    Remove-Item Env:DASHSCOPE_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
}

Invoke-Step "3/4 Strict Silver validation" @(
    "scripts\run_targeted_strict_validation.py",
    "--candidate-dir", $CandidateDir,
    "--input-dir", "data/interim/parsed_pages/corpus_v2",
    "--output-dir", $StrictDir
)

Invoke-Step "4/4 Corpus sufficiency decision" @(
    "scripts\assess_large_candidate_coverage.py",
    "--candidate-pool", $Pool,
    "--strict-dir", $StrictDir,
    "--output-dir", $StrictDir
)

$Validation = Get-Content (Join-Path $StrictDir "strict_v2_validation_summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$Decision = Get-Content (Join-Path $StrictDir "corpus_sufficiency_decision.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$Elapsed = (Get-Date) - $Started
Write-Host ""
Write-Host "========== Final result =========="
Write-Host "Candidate pages: $PageCount"
Write-Host "Strict Silver: $($Validation.decisions.silver_candidate)"
Write-Host "Needs review: $($Validation.decisions.candidate_needs_review)"
Write-Host "Rejected: $($Validation.decisions.rejected)"
Write-Host "Evidence-only classes passing: $($Validation.fault_classes_passing_evidence_only_audit)/10"
Write-Host "Corpus decision: $($Decision.global_decision)"
Write-Host "Total elapsed: $([math]::Round($Elapsed.TotalMinutes, 1)) minutes"
