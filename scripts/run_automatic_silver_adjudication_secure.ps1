param(
    [string]$Python = "",
    [int]$Limit = 0,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot
$Bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$PythonExe = if (-not [string]::IsNullOrWhiteSpace($Python)) { $Python } elseif (Test-Path $Bundled) { $Bundled } else { "python" }

$Arguments = @(
    "-u", "scripts\run_automatic_silver_adjudication.py",
    "--input-dir", "data/interim/candidate_triples/qwen3_7_max_corpus_retrieval_v2_large_audit_strict_v3_auto_normalized",
    "--output-dir", "data/interim/candidate_triples/qwen3_7_max_corpus_retrieval_v2_large_audit_strict_v4_auto_adjudicated"
)
if ($Limit -gt 0) { $Arguments += @("--limit", "$Limit") }
if ($DryRun) {
    $Arguments += "--dry-run"
    & $PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Dry-run failed with exit code $LASTEXITCODE" }
    exit 0
}

$SecureKey = Read-Host "Enter a NEW DASHSCOPE_API_KEY (input is hidden)" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
try {
    $env:DASHSCOPE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
        throw "DASHSCOPE_API_KEY must not be empty."
    }
    & $PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Automatic Silver adjudication failed with exit code $LASTEXITCODE"
    }
} finally {
    Remove-Item Env:DASHSCOPE_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
}
