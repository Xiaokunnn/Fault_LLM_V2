param(
    [string]$OutputPath = "papers/D2AI_ICDM_2026/figures/rp2_budgeted_retrieval_bilingual.vsdx",
    [string]$ExportDirectory = "papers/D2AI_ICDM_2026/figures"
)

$ErrorActionPreference = "Stop"

function Set-CellFormula {
    param($Shape, [string]$Cell, [string]$Formula)
    $Shape.CellsU($Cell).FormulaU = $Formula
}

function Add-Box {
    param(
        $Page,
        [double]$X1, [double]$Y1, [double]$X2, [double]$Y2,
        [string]$Text,
        [string]$Fill,
        [string]$Line,
        [double]$FontSize = 11,
        [double]$Radius = 0.10
    )
    $shape = $Page.DrawRectangle($X1, $Y1, $X2, $Y2)
    $shape.Text = $Text
    Set-CellFormula $shape "FillForegnd" $Fill
    Set-CellFormula $shape "FillPattern" "1"
    Set-CellFormula $shape "LineColor" $Line
    Set-CellFormula $shape "LineWeight" "1.4 pt"
    Set-CellFormula $shape "Rounding" ("{0} in" -f $Radius)
    Set-CellFormula $shape "Char.Size" ("{0} pt" -f $FontSize)
    Set-CellFormula $shape "Para.HorzAlign" "1"
    Set-CellFormula $shape "VerticalAlign" "1"
    return $shape
}

function Add-Text {
    param(
        $Page,
        [double]$X1, [double]$Y1, [double]$X2, [double]$Y2,
        [string]$Text,
        [double]$FontSize = 11,
        [string]$Color = "RGB(31,41,55)",
        [bool]$Bold = $false
    )
    $shape = $Page.DrawRectangle($X1, $Y1, $X2, $Y2)
    $shape.Text = $Text
    Set-CellFormula $shape "LinePattern" "0"
    Set-CellFormula $shape "FillPattern" "0"
    Set-CellFormula $shape "Char.Size" ("{0} pt" -f $FontSize)
    Set-CellFormula $shape "Char.Color" $Color
    Set-CellFormula $shape "Char.Style" ($(if ($Bold) { "1" } else { "0" }))
    Set-CellFormula $shape "Para.HorzAlign" "1"
    Set-CellFormula $shape "VerticalAlign" "1"
    return $shape
}

function Add-Arrow {
    param(
        $Page,
        [double]$X1, [double]$Y1, [double]$X2, [double]$Y2,
        [string]$Color = "RGB(75,85,99)",
        [double]$Weight = 1.4
    )
    $line = $Page.DrawLine($X1, $Y1, $X2, $Y2)
    Set-CellFormula $line "LineColor" $Color
    Set-CellFormula $line "LineWeight" ("{0} pt" -f $Weight)
    Set-CellFormula $line "EndArrow" "4"
    return $line
}

function Build-Page {
    param($Page, [bool]$English)

    Set-CellFormula $Page.PageSheet "PageWidth" "13.333 in"
    Set-CellFormula $Page.PageSheet "PageHeight" "7.5 in"
    Set-CellFormula $Page.PageSheet "ShdwOffsetX" "0 in"
    Set-CellFormula $Page.PageSheet "ShdwOffsetY" "0 in"

    if ($English) {
        $Page.Name = "English Figure"
        $title = "Budget-Constrained Vector-Graph Evidence Retrieval for Compute-Efficient Fault Diagnosis"
        $offline = "TRUSTED EVIDENCE BASE (OFFLINE)   Traceable triples + source anchors   |   BGE-M3 vector index"
        $boxes = @(
            "Mechanical fault query`nFault scope + diagnostic task",
            "BGE-M3 broad recall`nTop 32 candidates",
            "Task and fault gating`nOne-hop graph propagation",
            "Evidence budget controller`nK <= 3 + active underfilling`nSource de-duplication",
            "Local 7B evidence verifier`n0/1 mask + recall review",
            "Verifiable diagnostic advice`nEvidence IDs or abstention"
        )
        $metric1 = "ANSWER QUALITY`nCitation F1: 0.259 -> 0.426`nAnswerable coverage: 23/34 -> 34/34"
        $metric2 = "INFERENCE LOAD`nPrompt tokens: 1066.7 -> 634.7`nModel calls: 2.95 -> 1.80"
        $metric3 = "END-TO-END LATENCY`nMean: 839.4 -> 531.2 ms`n36.7% reduction"
        $footer = "Same local 7B model and maximum evidence budget K=3; RTX 5880 used for controlled relative measurement"
    }
    else {
        $Page.Name = "中文流程图"
        $title = "面向低算力机械故障辅助诊断的预算约束型向量与图协同证据检索"
        $offline = "高可信证据底座（离线）   可追溯三元组 + 原文来源锚点   |   BGE-M3向量索引"
        $boxes = @(
            "机械故障问题`n故障范围 + 诊断任务",
            "BGE-M3宽召回`n前32项候选",
            "任务与故障约束`n一跳图传播",
            "证据预算控制器`nK <= 3 + 主动欠填`n来源去冗余",
            "本地7B证据核验`n0/1筛选 + 补充复核",
            "可核验辅助诊断建议`n证据编号或明确拒答"
        )
        $metric1 = "回答质量`n引用F1：0.259 -> 0.426`n可回答覆盖：23/34 -> 34/34"
        $metric2 = "推理负担`n提示长度：1066.7 -> 634.7 Token`n模型调用：2.95 -> 1.80"
        $metric3 = "端到端时延`n平均：839.4 -> 531.2 ms`n降低36.7%"
        $footer = "本地7B模型和最大证据预算K=3保持一致；RTX 5880仅用于控制变量下的相对性能测量"
    }

    Add-Text $Page 0.35 6.95 12.98 7.42 $title 18 "RGB(30,64,111)" $true | Out-Null
    Add-Box $Page 0.55 6.12 12.78 6.78 $offline "RGB(236,244,252)" "RGB(57,106,160)" 11 0.08 | Out-Null

    $starts = @(0.40, 2.55, 4.70, 6.85, 9.00, 11.15)
    $fills = @("RGB(255,247,237)", "RGB(239,246,255)", "RGB(236,253,245)", "RGB(254,252,232)", "RGB(254,242,242)", "RGB(240,253,250)")
    $lines = @("RGB(234,88,12)", "RGB(37,99,235)", "RGB(5,150,105)", "RGB(202,138,4)", "RGB(220,38,38)", "RGB(13,148,136)")
    for ($i = 0; $i -lt 6; $i++) {
        Add-Box $Page $starts[$i] 3.82 ($starts[$i] + 1.78) 5.42 $boxes[$i] $fills[$i] $lines[$i] 9.6 0.10 | Out-Null
        if ($i -lt 5) {
            Add-Arrow $Page ($starts[$i] + 1.78) 4.62 $starts[$i + 1] 4.62 | Out-Null
        }
    }

    Add-Arrow $Page 3.45 6.12 3.45 5.42 "RGB(57,106,160)" 1.2 | Out-Null
    Add-Arrow $Page 5.60 6.12 5.60 5.42 "RGB(57,106,160)" 1.2 | Out-Null

    Add-Box $Page 0.75 1.35 4.20 2.85 $metric1 "RGB(239,246,255)" "RGB(37,99,235)" 10.2 0.08 | Out-Null
    Add-Box $Page 4.95 1.35 8.40 2.85 $metric2 "RGB(255,247,237)" "RGB(234,88,12)" 10.2 0.08 | Out-Null
    Add-Box $Page 9.15 1.35 12.60 2.85 $metric3 "RGB(236,253,245)" "RGB(5,150,105)" 10.2 0.08 | Out-Null
    Add-Arrow $Page 12.04 3.82 10.88 2.85 "RGB(13,148,136)" 1.2 | Out-Null

    Add-Text $Page 0.45 0.55 12.88 1.05 $footer 8.5 "RGB(75,85,99)" $false | Out-Null
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$output = [System.IO.Path]::GetFullPath((Join-Path $root $OutputPath))
$exports = [System.IO.Path]::GetFullPath((Join-Path $root $ExportDirectory))
[System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($output)) | Out-Null
[System.IO.Directory]::CreateDirectory($exports) | Out-Null

$visio = $null
$document = $null
try {
    $visio = New-Object -ComObject Visio.Application
    $visio.Visible = $false
    $visio.AlertResponse = 7
    $document = $visio.Documents.Add("")
    $zhPage = $document.Pages.Item(1)
    Build-Page $zhPage $false
    $enPage = $document.Pages.Add()
    Build-Page $enPage $true
    $document.SaveAs($output)

    $zhPage.Export((Join-Path $exports "rp2_budgeted_retrieval_zh.svg"))
    $zhPage.Export((Join-Path $exports "rp2_budgeted_retrieval_zh.png"))
    $enPage.Export((Join-Path $exports "rp2_budgeted_retrieval_en.svg"))
    $enPage.Export((Join-Path $exports "rp2_budgeted_retrieval_en.png"))
    Write-Output "Created: $output"
    Write-Output "Exported bilingual SVG and PNG figures to: $exports"
}
finally {
    if ($null -ne $document) { $document.Close() }
    if ($null -ne $visio) { $visio.Quit() }
    if ($null -ne $document) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    if ($null -ne $visio) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($visio) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

