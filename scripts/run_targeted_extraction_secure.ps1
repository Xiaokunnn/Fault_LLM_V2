param(
    [switch]$Full,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Runner = Join-Path $ProjectRoot "scripts\run_targeted_triple_extraction.py"
$SecureKey = Read-Host "Enter a NEW DASHSCOPE_API_KEY (input is hidden)" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)

try {
    $env:DASHSCOPE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
        throw "DASHSCOPE_API_KEY must not be empty."
    }
    Set-Location -LiteralPath $ProjectRoot
    if ($Full) {
        & $Python -u $Runner
    }
    else {
        & $Python -u $Runner --pages "MP005:60,MP016:4"
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Extraction process exit code: $LASTEXITCODE"
    }
}
finally {
    Remove-Item Env:DASHSCOPE_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
}
