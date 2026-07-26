param(
    [string]$Python = "",
    [int]$Limit = 0,
    [switch]$LocalOnly,
    [switch]$SkipAdjudication
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot
$UserHome = if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    $env:USERPROFILE
} elseif (-not [string]::IsNullOrWhiteSpace($env:HOME)) {
    $env:HOME
} else {
    [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
}
$Bundled = Join-Path $UserHome ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
$PythonExe = if (-not [string]::IsNullOrWhiteSpace($Python)) { $Python } elseif (Test-Path $Bundled) { $Bundled } else { "python" }
$Started = Get-Date

$Config = "configs/triple_extraction_qwen3_7_max_full_corpus_v1.json"
$PoolDir = "data/interim/candidate_pages/full_extraction_v1"
$Pool = "$PoolDir/candidate_pages.jsonl"
$CandidateDir = "data/interim/candidate_triples/qwen3_7_max_full_corpus_v1"
$StrictDir = "${CandidateDir}_strict_v3"
$FinalDir = "${CandidateDir}_auto_adjudicated"

function Invoke-PythonStep {
    param([string]$Name, [string[]]$Arguments)
    Write-Host ""
    Write-Host "========== $Name =========="
    & $PythonExe -u @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

Invoke-PythonStep "1/5 Build deterministic all-page plan" @(
    "scripts/build_full_extraction_page_plan.py"
)

$ExtractionArgs = @(
    "scripts/run_targeted_triple_extraction.py",
    "--config", $Config,
    "--candidate-pool", $Pool,
    "--input-dir", "data/interim/parsed_pages/corpus_v2",
    "--output-dir", $CandidateDir
)
if ($Limit -gt 0) { $ExtractionArgs += @("--limit", "$Limit") }

if ($LocalOnly) {
    $ExtractionArgs += "--dry-run"
    Invoke-PythonStep "2/5 Validate prompts and local inputs without API" $ExtractionArgs
    Write-Host ""
    Write-Host "LocalOnly completed. No external model call was made."
    Write-Host "Run a two-page smoke test with: powershell -ExecutionPolicy Bypass -File scripts\run_full_graph_pipeline_secure.ps1 -Limit 2"
    exit 0
}

$SecureKey = Read-Host "Enter a NEW DASHSCOPE_API_KEY (input is hidden)" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
try {
    $env:DASHSCOPE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
        throw "DASHSCOPE_API_KEY must not be empty."
    }

    Invoke-PythonStep "2/5 Extract build-train pages with qwen3.7-max" $ExtractionArgs

    Invoke-PythonStep "3/5 Strict evidence, schema, scope and Chinese validation" @(
        "scripts/run_targeted_strict_validation.py",
        "--config", $Config,
        "--candidate-dir", $CandidateDir,
        "--input-dir", "data/interim/parsed_pages/corpus_v2",
        "--output-dir", $StrictDir,
        "--schema", "data/kg/marine_pump/schema/provenance_schema_v3.json"
    )

    if (-not $SkipAdjudication) {
        Invoke-PythonStep "4/5 Dual-pass automatic Silver adjudication" @(
            "scripts/run_automatic_silver_adjudication.py",
            "--config", $Config,
            "--input-dir", $StrictDir,
            "--output-dir", $FinalDir
        )
        $GraphInput = "$FinalDir/candidate_triples.auto_adjudicated_silver.jsonl"
    } else {
        Write-Host ""
        Write-Host "========== 4/5 Adjudication skipped by request =========="
        $GraphInput = "$StrictDir/candidate_triples.strict_v2.jsonl"
    }
} finally {
    Remove-Item Env:DASHSCOPE_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
}

Invoke-PythonStep "5/5 Build KG_v1_raw and Chinese-ready KG_v1_validated" @(
    "scripts/build_versioned_knowledge_graph.py",
    "--input", $GraphInput,
    "--output-root", "data/kg/marine_pump"
)

$Elapsed = (Get-Date) - $Started
Write-Host ""
Write-Host "========== Full graph pipeline result =========="
Write-Host "Elapsed: $([math]::Round($Elapsed.TotalHours, 2)) hours"
Write-Host "Raw graph: data/kg/marine_pump/graph_versions/KG_v1_raw"
Write-Host "Validated graph: data/kg/marine_pump/graph_versions/KG_v1_validated"
Write-Host "Resume policy: rerun the same command; completed page and adjudication responses are reused from cache."
