param(
    [string]$Python = "python",
    [int]$Limit = 0,
    [switch]$LocalOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot
$Config = "configs/triple_extraction_qwen3_7_max_heldout_external_v1.json"
$PageDir = "data/interim/parsed_pages/heldout_external_v1"
$PoolDir = "data/interim/candidate_pages/heldout_external_v1"
$CandidateDir = "data/interim/heldout_external/rp1_extraction_v1"
$StrictDir = "data/interim/heldout_external/rp1_strict_v1"
$FinalDir = "data/interim/heldout_external/shared_silver_v1"

function Invoke-Step([string]$Name, [string[]]$Arguments) {
    Write-Host ""
    Write-Host "========== $Name =========="
    & $Python -u @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

Invoke-Step "1/4 Build frozen held-out page plan" @("scripts/build_heldout_external_page_plan.py")
$Extraction = @(
    "scripts/run_targeted_triple_extraction.py", "--config", $Config,
    "--candidate-pool", "$PoolDir/candidate_pages.jsonl",
    "--input-dir", $PageDir, "--output-dir", $CandidateDir
)
if ($Limit -gt 0) { $Extraction += @("--limit", "$Limit") }
if ($LocalOnly) {
    $Extraction += "--dry-run"
    Invoke-Step "2/4 Validate held-out inputs without API" $Extraction
    Write-Host "Local-only check complete; no external model call was made."
    exit 0
}

$SecureKey = Read-Host "Enter DASHSCOPE_API_KEY (input is hidden)" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
try {
    $env:DASHSCOPE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) { throw "DASHSCOPE_API_KEY must not be empty." }
    Invoke-Step "2/4 Frozen extraction on MP010-MP013" $Extraction
    Invoke-Step "3/4 Frozen strict validation" @(
        "scripts/run_targeted_strict_validation.py", "--config", $Config,
        "--candidate-dir", $CandidateDir, "--input-dir", $PageDir,
        "--output-dir", $StrictDir,
        "--schema", "data/kg/marine_pump/schema/provenance_schema_v3.json"
    )
    Invoke-Step "4/4 Dual-pass external Silver adjudication" @(
        "scripts/run_automatic_silver_adjudication.py", "--config", $Config,
        "--input-dir", $StrictDir, "--output-dir", $FinalDir,
        "--allowed-splits", "held_out_test"
    )
} finally {
    Remove-Item Env:DASHSCOPE_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
}
Write-Host ""
Write-Host "External Silver is isolated under data/interim/heldout_external/."
Write-Host "It must not be merged into KG_v1_validated or used for tuning."
