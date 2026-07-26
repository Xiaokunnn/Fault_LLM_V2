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

$Config = "configs/triple_extraction_qwen3_7_max_final_semantic_gap_v1.json"
$SourceV4Config = "configs/triple_extraction_qwen3_7_max_source_v4_gap_v1.json"
$PoolDir = "data/interim/candidate_pages/final_semantic_gap_v1"
$Pool = "$PoolDir/candidate_pages.jsonl"
$CandidateDir = "data/interim/candidate_triples/qwen3_7_max_final_semantic_gap_v1"
$SymptomStrictDir = "${CandidateDir}_strict_v3"
$MP022CandidateDir = "data/interim/candidate_triples/qwen3_7_max_source_v4_gap_v1"
$MP022RepairStrictDir = "${MP022CandidateDir}_strict_v4_type_repaired"
$Base521Dir = "data/interim/candidate_triples/qwen3_7_max_gap_repair_v1_combined_auto_adjudicated"
$Base521 = "$Base521Dir/candidate_triples.auto_adjudicated_silver.jsonl"
$CombinedMP022Dir = "data/interim/candidate_triples/final_semantic_gap_v1_combined_mp022"
$CombinedAllDir = "data/interim/candidate_triples/final_semantic_gap_v1_combined_all"
$MappedDir = "data/interim/candidate_triples/final_semantic_gap_v1_mapping_v1_4"
$FinalDir = "data/interim/candidate_triples/final_semantic_gap_v1_auto_adjudicated"
$Current535Dir = "data/interim/candidate_triples/qwen3_7_max_source_v4_gap_v1_combined_auto_adjudicated"

Invoke-PythonStep "1/9 Freeze three existing mechanical-seal symptom pages" @(
    "scripts\build_final_semantic_gap_page_plan.py"
)

Invoke-PythonStep "2/9 Revalidate MP022 with exact troubleshooting type repair" @(
    "scripts\run_targeted_strict_validation.py",
    "--config", $SourceV4Config,
    "--candidate-dir", $MP022CandidateDir,
    "--input-dir", "data/interim/parsed_pages/corpus_v2",
    "--output-dir", $MP022RepairStrictDir,
    "--schema", "data/kg/marine_pump/schema/provenance_schema_v3.json"
)

if ($LocalOnly) {
    Invoke-PythonStep "3/9 Validate symptom-repair prompt and inputs" @(
        "scripts\run_targeted_triple_extraction.py",
        "--config", $Config,
        "--candidate-pool", $Pool,
        "--input-dir", "data/interim/parsed_pages/corpus_v2",
        "--output-dir", $CandidateDir,
        "--dry-run"
    )
    Write-Host ""
    Write-Host "LocalOnly completed; no external model call was made."
    Write-Host "Expected external-model time: approximately 2-5 minutes."
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
    Invoke-PythonStep "3/9 Extract only three existing symptom pages with qwen3.7-max" $ExtractionArgs

    Invoke-PythonStep "4/9 Strictly validate new symptom assertions" @(
        "scripts\run_targeted_strict_validation.py",
        "--config", $Config,
        "--candidate-dir", $CandidateDir,
        "--input-dir", "data/interim/parsed_pages/corpus_v2",
        "--output-dir", $SymptomStrictDir,
        "--schema", "data/kg/marine_pump/schema/provenance_schema_v3.json"
    )

    Invoke-PythonStep "5/9 Rebuild MP022 layer on the frozen 521-Silver base" @(
        "scripts\merge_gap_repair_candidates.py",
        "--base", $Base521,
        "--gap-strict-dir", $MP022RepairStrictDir,
        "--output-dir", $CombinedMP022Dir
    )

    Invoke-PythonStep "6/9 Merge the three-page symptom repair" @(
        "scripts\merge_gap_repair_candidates.py",
        "--base", "$CombinedMP022Dir/candidate_triples.strict_v2.jsonl",
        "--gap-strict-dir", $SymptomStrictDir,
        "--output-dir", $CombinedAllDir
    )

    Invoke-PythonStep "7/9 Refresh all fault mappings with claim-scoped ontology v1.4" @(
        "scripts\refresh_fault_class_mappings.py",
        "--input-dir", $CombinedAllDir,
        "--output-dir", $MappedDir
    )

    Invoke-PythonStep "8/9 Dual-pass automatic Silver adjudication" @(
        "scripts\run_automatic_silver_adjudication.py",
        "--config", $Config,
        "--input-dir", $MappedDir,
        "--output-dir", $FinalDir,
        "--reuse-cache-dir", $Current535Dir,
        "--reuse-cache-dir", $Base521Dir
    )
} finally {
    Remove-Item Env:DASHSCOPE_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
}

Invoke-PythonStep "9/9 Recalculate all ten frozen coverage gates" @(
    "scripts\assess_gap_repair_result.py",
    "--coverage", "$FinalDir/auto_adjudicated_coverage_evidence_only.json",
    "--output", "$FinalDir/final_semantic_gap_decision.json"
)

$FinalSummary = Get-Content "$FinalDir/auto_adjudication_summary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$Decision = Get-Content "$FinalDir/final_semantic_gap_decision.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$Elapsed = (Get-Date) - $Started
Write-Host ""
Write-Host "========== Final semantic-gap result =========="
Write-Host "Final Silver: $($FinalSummary.decisions.silver_candidate)"
Write-Host "Final needs review: $($FinalSummary.decisions.candidate_needs_review)"
Write-Host "Final rejected: $($FinalSummary.decisions.rejected)"
Write-Host "Evidence-only classes passing: $($FinalSummary.evidence_only_classes_passing)/10"
Write-Host "Corpus decision: $($Decision.corpus_decision)"
Write-Host "Human expert reviewed: $($FinalSummary.human_expert_reviewed)"
Write-Host "Label policy: $($FinalSummary.label_policy)"
Write-Host "Total elapsed: $([math]::Round($Elapsed.TotalMinutes, 1)) minutes"
