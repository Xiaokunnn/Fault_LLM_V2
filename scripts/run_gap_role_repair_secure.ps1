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

$Config = "configs/triple_extraction_qwen3_7_max_gap_repair_v2.json"
$PoolDir = "data/interim/candidate_pages/gap_repair_v1"
$Pool = "$PoolDir/candidate_pages.jsonl"
$CandidateDir = "data/interim/candidate_triples/qwen3_7_max_gap_repair_v1"
$StrictDir = "${CandidateDir}_strict_v3"
$CombinedDir = "${CandidateDir}_combined_strict_v3"
$FinalDir = "${CandidateDir}_combined_auto_adjudicated"
$BaseFinalDir = "data/interim/candidate_triples/qwen3_7_max_corpus_retrieval_v3_source_supplement_strict_v4_auto_adjudicated"

Invoke-PythonStep "1/7 Freeze six-class gap page plan" @(
    "scripts\build_gap_repair_page_plan.py"
)

$Plan = Get-Content "$PoolDir/gap_repair_plan_summary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host "Frozen pages: $($Plan.candidate_pages)"
Write-Host "Verified table pages: $($Plan.table_reparse_page_count)"

$TableArgs = @("scripts\reparse_gap_table_pages.py")
if ($LocalOnly) { $TableArgs += "--dry-run" }
Invoke-PythonStep "2/7 Reparse verified same-row/row-group tables" $TableArgs

if ($LocalOnly) {
    Invoke-PythonStep "3/7 Validate gap-role prompt and inputs" @(
        "scripts\run_targeted_triple_extraction.py",
        "--config", $Config,
        "--candidate-pool", $Pool,
        "--input-dir", "data/interim/parsed_pages/corpus_v2",
        "--output-dir", $CandidateDir,
        "--dry-run"
    )
    Write-Host ""
    Write-Host "LocalOnly selected; no external model call was made."
    Write-Host "Expected external-model time: approximately 30-45 minutes."
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
        "--config", $Config,
        "--candidate-pool", $Pool,
        "--input-dir", "data/interim/parsed_pages/corpus_v2",
        "--output-dir", $CandidateDir
    )
    if ($Limit -gt 0) { $ExtractionArgs += @("--limit", "$Limit") }
    Invoke-PythonStep "3/7 Extract missing roles with qwen3.7-max" $ExtractionArgs

    Invoke-PythonStep "4/7 Strict validation with prevention relation v3" @(
        "scripts\run_targeted_strict_validation.py",
        "--config", $Config,
        "--candidate-dir", $CandidateDir,
        "--input-dir", "data/interim/parsed_pages/corpus_v2",
        "--output-dir", $StrictDir,
        "--schema", "data/kg/marine_pump/schema/provenance_schema_v3.json"
    )

    Invoke-PythonStep "5/7 Merge source-v3 and gap-repair assertions" @(
        "scripts\merge_gap_repair_candidates.py",
        "--gap-strict-dir", $StrictDir,
        "--output-dir", $CombinedDir
    )

    Invoke-PythonStep "6/7 Dual-pass automatic Silver adjudication" @(
        "scripts\run_automatic_silver_adjudication.py",
        "--config", $Config,
        "--input-dir", $CombinedDir,
        "--output-dir", $FinalDir,
        "--reuse-cache-dir", $BaseFinalDir
    )
} finally {
    Remove-Item Env:DASHSCOPE_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
}

Invoke-PythonStep "7/7 Recalculate coverage and decide next action" @(
    "scripts\assess_gap_repair_result.py",
    "--coverage", "$FinalDir/auto_adjudicated_coverage_evidence_only.json",
    "--output", "$FinalDir/gap_repair_decision.json"
)

$FinalSummary = Get-Content "$FinalDir/auto_adjudication_summary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$Decision = Get-Content "$FinalDir/gap_repair_decision.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$Elapsed = (Get-Date) - $Started
Write-Host ""
Write-Host "========== Final gap-repair Silver result =========="
Write-Host "Final Silver: $($FinalSummary.decisions.silver_candidate)"
Write-Host "Final needs review: $($FinalSummary.decisions.candidate_needs_review)"
Write-Host "Final rejected: $($FinalSummary.decisions.rejected)"
Write-Host "Evidence-only classes passing: $($FinalSummary.evidence_only_classes_passing)/10"
Write-Host "Corpus decision: $($Decision.corpus_decision)"
Write-Host "Human expert reviewed: $($FinalSummary.human_expert_reviewed)"
Write-Host "Label policy: $($FinalSummary.label_policy)"
Write-Host "Total elapsed: $([math]::Round($Elapsed.TotalMinutes, 1)) minutes"
