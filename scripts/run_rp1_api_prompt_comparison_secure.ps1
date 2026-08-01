param(
    [string]$Python = "python",
    [int]$Limit = 0,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot
$Pool = "configs/rp1_api_comparison_pages_v1.jsonl"
$BaseConfig = Get-Content -Raw -Encoding UTF8 "configs/triple_extraction_qwen3_7_max_full_corpus_v1.json" | ConvertFrom-Json
$Methods = @(
    @{ Id = "B0"; Prompt = "marine_pump_api_ablation_b0" },
    @{ Id = "B1"; Prompt = "marine_pump_api_ablation_b1" },
    @{ Id = "B2"; Prompt = "marine_pump_api_ablation_b2" },
    @{ Id = "B3"; Prompt = "marine_pump_api_ablation_b3" },
    @{ Id = "Ours"; Prompt = "marine_pump_full_corpus_prompt_v4" }
)

$SecureKey = $null
$Pointer = [IntPtr]::Zero
try {
    if (-not $DryRun) {
        $SecureKey = Read-Host "Enter a NEW DASHSCOPE_API_KEY (input is hidden)" -AsSecureString
        $Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
        $env:DASHSCOPE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
        if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
            throw "DASHSCOPE_API_KEY must not be empty."
        }
    }
    foreach ($Method in $Methods) {
        $Output = "results/experiments/research_point_1/api_prompt_comparison_v1/$($Method.Id)"
        $TempConfig = Join-Path $env:TEMP "rp1_api_$($Method.Id)_$PID.json"
        $Config = $BaseConfig.PSObject.Copy()
        $Config.version = "rp1_api_prompt_comparison_$($Method.Id)_v1"
        $Config.status = "fixed_page_real_api_comparison"
        $Config.prompt_version = $Method.Prompt
        $Config.output_dir = $Output
        $ConfigJson = $Config | ConvertTo-Json -Depth 20
        [IO.File]::WriteAllText(
            $TempConfig,
            $ConfigJson,
            [Text.UTF8Encoding]::new($false)
        )
        Write-Host "`n========== $($Method.Id) extraction =========="
        $Args = @(
            "-u", "scripts/run_targeted_triple_extraction.py",
            "--config", $TempConfig,
            "--candidate-pool", $Pool,
            "--output-dir", $Output
        )
        if ($Limit -gt 0) { $Args += @("--limit", "$Limit") }
        if ($DryRun) { $Args += "--dry-run" }
        & $Python @Args
        if ($LASTEXITCODE -ne 0) { throw "$($Method.Id) extraction failed: $LASTEXITCODE" }
        if (-not $DryRun) {
            Write-Host "========== $($Method.Id) strict validation =========="
            & $Python -u scripts/run_targeted_strict_validation.py `
                --config $TempConfig `
                --candidate-dir $Output `
                --output-dir "$Output/strict" `
                --schema "data/kg/marine_pump/schema/provenance_schema_v3.json"
            if ($LASTEXITCODE -ne 0) { throw "$($Method.Id) validation failed: $LASTEXITCODE" }
        }
        Remove-Item -LiteralPath $TempConfig -Force -ErrorAction SilentlyContinue
    }
    if (-not $DryRun -and $Limit -eq 0) {
        & $Python -u scripts/summarize_rp1_api_prompt_comparison.py
        if ($LASTEXITCODE -ne 0) { throw "Comparison summary failed: $LASTEXITCODE" }
    }
}
finally {
    Remove-Item Env:DASHSCOPE_API_KEY -ErrorAction SilentlyContinue
    if ($Pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
    }
}
