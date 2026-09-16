[CmdletBinding()]
param(
    [string]$OutputDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $repoRoot 'papers\ICSMD_2026'
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$baseName = 'RP1_ICSMD2026_method_flowchart'
$vsdxPath = Join-Path $OutputDirectory ($baseName + '_bilingual.vsdx')
$svgZhPath = Join-Path $OutputDirectory ($baseName + '_zh.svg')
$svgEnPath = Join-Path $OutputDirectory ($baseName + '_en.svg')
$pngZhPath = Join-Path $OutputDirectory ($baseName + '_zh.png')
$pngEnPath = Join-Path $OutputDirectory ($baseName + '_en.png')
$pdfBilingualPath = Join-Path $OutputDirectory ($baseName + '_bilingual.pdf')
$pdfZhPath = Join-Path $OutputDirectory ($baseName + '_zh.pdf')
$pdfEnPath = Join-Path $OutputDirectory ($baseName + '_en.pdf')
$splitPattern = Join-Path $OutputDirectory ($baseName + '_split_%d.pdf')

$ownedOutputs = @(
    $vsdxPath, $svgZhPath, $svgEnPath, $pngZhPath, $pngEnPath,
    $pdfBilingualPath, $pdfZhPath, $pdfEnPath,
    ($splitPattern -replace '%d', '1'), ($splitPattern -replace '%d', '2')
)
foreach ($path in $ownedOutputs) {
    if ([System.IO.File]::Exists($path)) {
        [System.IO.File]::Delete($path)
    }
}

$app = $null
$doc = $null

function Set-TextStyle {
    param(
        [Parameter(Mandatory)]$Shape,
        [Parameter(Mandatory)][string]$FontName,
        [Parameter(Mandatory)][int]$LanguageId,
        [double]$FontSizePt = 15.0,
        [bool]$Bold = $false
    )

    # Visio keeps Western and East-Asian fonts in different Character cells.
    # Setting both avoids a silent Chinese-font fallback during PDF export.
    $Shape.CellsSRC(3, 0, 0).FormulaU = 'FONT("' + $FontName + '")'
    $Shape.CellsSRC(3, 0, 51).FormulaU = 'FONT("' + $FontName + '")'
    $Shape.CellsSRC(3, 0, 57).FormulaU = [string]$LanguageId
    $Shape.CellsU('Char.Size').FormulaU = ([string]$FontSizePt + ' pt')
    $Shape.CellsU('Char.Style').FormulaU = if ($Bold) { '1' } else { '0' }
    $Shape.CellsU('Para.HorzAlign').FormulaU = '1'
    $Shape.CellsU('VerticalAlign').FormulaU = '1'
    $Shape.CellsU('LeftMargin').FormulaU = '0.05 in'
    $Shape.CellsU('RightMargin').FormulaU = '0.05 in'
    $Shape.CellsU('TopMargin').FormulaU = '0.03 in'
    $Shape.CellsU('BottomMargin').FormulaU = '0.03 in'
}

function New-Node {
    param(
        [Parameter(Mandatory)]$Page,
        [Parameter(Mandatory)][double]$X1,
        [Parameter(Mandatory)][double]$Y1,
        [Parameter(Mandatory)][double]$X2,
        [Parameter(Mandatory)][double]$Y2,
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$FontName,
        [Parameter(Mandatory)][int]$LanguageId,
        [Parameter(Mandatory)][string]$FillColor,
        [Parameter(Mandatory)][string]$LineColor,
        [string]$StepNumber = '',
        [double]$FontSizePt = 15.0
    )

    $shape = $Page.DrawRectangle($X1, $Y1, $X2, $Y2)
    $shape.Text = $Text
    $shape.CellsU('FillForegnd').FormulaU = $FillColor
    $shape.CellsU('FillPattern').FormulaU = '1'
    $shape.CellsU('FillForegndTrans').FormulaU = '0%'
    $shape.CellsU('LineColor').FormulaU = $LineColor
    $shape.CellsU('LinePattern').FormulaU = '1'
    $shape.CellsU('LineWeight').FormulaU = '1.15 pt'
    $shape.CellsU('Rounding').FormulaU = '0.10 in'
    Set-TextStyle -Shape $shape -FontName $FontName -LanguageId $LanguageId -FontSizePt $FontSizePt

    if (-not [string]::IsNullOrWhiteSpace($StepNumber)) {
        # Place the step badge on the upper border so it never covers a long
        # English title while remaining visually attached to its process node.
        $badge = $Page.DrawOval($X1 + 0.06, $Y2 - 0.05, $X1 + 0.44, $Y2 + 0.33)
        $badge.Text = $StepNumber
        $badge.CellsU('FillForegnd').FormulaU = $LineColor
        $badge.CellsU('FillPattern').FormulaU = '1'
        $badge.CellsU('LineColor').FormulaU = $LineColor
        $badge.CellsU('LineWeight').FormulaU = '0.9 pt'
        Set-TextStyle -Shape $badge -FontName $FontName -LanguageId $LanguageId -FontSizePt 16.0 -Bold $true
        $badge.CellsU('Char.Color').FormulaU = 'RGB(255,255,255)'
    }

    return $shape
}

function New-Label {
    param(
        [Parameter(Mandatory)]$Page,
        [Parameter(Mandatory)][double]$X1,
        [Parameter(Mandatory)][double]$Y1,
        [Parameter(Mandatory)][double]$X2,
        [Parameter(Mandatory)][double]$Y2,
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$FontName,
        [Parameter(Mandatory)][int]$LanguageId,
        [bool]$WhiteBackground = $false,
        [bool]$Bold = $false
    )

    $label = $Page.DrawRectangle($X1, $Y1, $X2, $Y2)
    $label.Text = $Text
    $label.CellsU('LinePattern').FormulaU = '0'
    if ($WhiteBackground) {
        $label.CellsU('FillPattern').FormulaU = '1'
        $label.CellsU('FillForegnd').FormulaU = 'RGB(255,255,255)'
    }
    else {
        $label.CellsU('FillPattern').FormulaU = '0'
    }
    Set-TextStyle -Shape $label -FontName $FontName -LanguageId $LanguageId -FontSizePt 15.0 -Bold $Bold
    return $label
}

function New-Connector {
    param(
        [Parameter(Mandatory)]$Page,
        [Parameter(Mandatory)]$FromShape,
        [Parameter(Mandatory)]$ToShape,
        [double]$FromX = 1.0,
        [double]$FromY = 0.5,
        [double]$ToX = 0.0,
        [double]$ToY = 0.5,
        [bool]$Dashed = $false,
        [bool]$Arrow = $true
    )

    $connector = $Page.Drop($app.ConnectorToolDataObject, 0, 0)
    $connector.CellsU('BeginX').GlueToPos($FromShape, $FromX, $FromY)
    $connector.CellsU('EndX').GlueToPos($ToShape, $ToX, $ToY)
    $connector.CellsU('LineColor').FormulaU = 'RGB(70,78,86)'
    $connector.CellsU('LineWeight').FormulaU = '1.05 pt'
    $connector.CellsU('LinePattern').FormulaU = if ($Dashed) { '2' } else { '1' }
    $connector.CellsU('EndArrow').FormulaU = if ($Arrow) { '13' } else { '0' }
    return $connector
}

function New-TraceSegment {
    param(
        [Parameter(Mandatory)]$Page,
        [Parameter(Mandatory)][double]$X1,
        [Parameter(Mandatory)][double]$Y1,
        [Parameter(Mandatory)][double]$X2,
        [Parameter(Mandatory)][double]$Y2,
        [bool]$Arrow = $false
    )

    $line = $Page.DrawLine($X1, $Y1, $X2, $Y2)
    $line.CellsU('LineColor').FormulaU = 'RGB(82,89,96)'
    $line.CellsU('LineWeight').FormulaU = '1.05 pt'
    $line.CellsU('LinePattern').FormulaU = '2'
    $line.CellsU('EndArrow').FormulaU = if ($Arrow) { '13' } else { '0' }
    return $line
}

function Build-FlowchartPage {
    param(
        [Parameter(Mandatory)]$Page,
        [Parameter(Mandatory)][hashtable]$Labels,
        [Parameter(Mandatory)][string]$FontName,
        [Parameter(Mandatory)][int]$LanguageId
    )

    $blueFill = 'RGB(232,242,250)'
    $blueLine = 'RGB(47,91,133)'
    $gateFill = 'RGB(255,245,213)'
    $gateLine = 'RGB(153,112,26)'
    $tealFill = 'RGB(228,244,240)'
    $tealLine = 'RGB(35,111,102)'
    $grayFill = 'RGB(241,243,245)'
    $grayLine = 'RGB(88,96,105)'
    $noteFill = 'RGB(249,245,225)'
    $noteLine = 'RGB(132,111,45)'

    # A native white background fixes the SVG/PNG crop boundary and leaves
    # clear space around the trace-back path. It is drawn first, so every
    # process node and connector remains independently selectable above it.
    $background = $Page.DrawRectangle(0.10, 0.05, 12.55, 6.80)
    $background.CellsU('FillForegnd').FormulaU = 'RGB(255,255,255)'
    $background.CellsU('FillPattern').FormulaU = '1'
    $background.CellsU('LinePattern').FormulaU = '0'

    # The node height is deliberately generous. At full two-column width the
    # 14.5 pt source text scales to at least 8 pt, including the English page.
    $mainY1 = 3.45
    $mainY2 = 6.35

    $n1 = New-Node -Page $Page -X1 0.30 -Y1 $mainY1 -X2 1.70 -Y2 $mainY2 `
        -Text $Labels.N1 -FontName $FontName -LanguageId $LanguageId `
        -FillColor $blueFill -LineColor $blueLine -StepNumber '1'
    $n2 = New-Node -Page $Page -X1 1.88 -Y1 $mainY1 -X2 3.35 -Y2 $mainY2 `
        -Text $Labels.N2 -FontName $FontName -LanguageId $LanguageId `
        -FillColor $blueFill -LineColor $blueLine -StepNumber '2'
    $n3 = New-Node -Page $Page -X1 3.53 -Y1 $mainY1 -X2 5.10 -Y2 $mainY2 `
        -Text $Labels.N3 -FontName $FontName -LanguageId $LanguageId `
        -FillColor $blueFill -LineColor $blueLine -StepNumber '3'
    $n4 = New-Node -Page $Page -X1 5.28 -Y1 $mainY1 -X2 6.95 -Y2 $mainY2 `
        -Text $Labels.N4 -FontName $FontName -LanguageId $LanguageId `
        -FillColor $gateFill -LineColor $gateLine -StepNumber '4'
    $qualified = New-Node -Page $Page -X1 7.27 -Y1 $mainY1 -X2 8.70 -Y2 $mainY2 `
        -Text $Labels.Qualified -FontName $FontName -LanguageId $LanguageId `
        -FillColor $tealFill -LineColor $tealLine
    $n5 = New-Node -Page $Page -X1 8.90 -Y1 $mainY1 -X2 10.65 -Y2 $mainY2 `
        -Text $Labels.N5 -FontName $FontName -LanguageId $LanguageId `
        -FillColor $tealFill -LineColor $tealLine -StepNumber '5'
    $n6 = New-Node -Page $Page -X1 10.85 -Y1 $mainY1 -X2 12.40 -Y2 $mainY2 `
        -Text $Labels.N6 -FontName $FontName -LanguageId $LanguageId `
        -FillColor $tealFill -LineColor $tealLine -StepNumber '6'

    $audit = New-Node -Page $Page -X1 5.08 -Y1 0.85 -X2 6.88 -Y2 2.72 `
        -Text $Labels.Audit -FontName $FontName -LanguageId $LanguageId `
        -FillColor $grayFill -LineColor $grayLine -FontSizePt 15.0
    $family = New-Node -Page $Page -X1 7.28 -Y1 1.05 -X2 9.90 -Y2 2.55 `
        -Text $Labels.Family -FontName $FontName -LanguageId $LanguageId `
        -FillColor $noteFill -LineColor $noteLine -FontSizePt 15.0
    $family.CellsU('LinePattern').FormulaU = '2'

    $null = New-Connector -Page $Page -FromShape $n1 -ToShape $n2
    $null = New-Connector -Page $Page -FromShape $n2 -ToShape $n3
    $null = New-Connector -Page $Page -FromShape $n3 -ToShape $n4
    $null = New-Connector -Page $Page -FromShape $n4 -ToShape $qualified
    $null = New-Connector -Page $Page -FromShape $qualified -ToShape $n5
    $null = New-Connector -Page $Page -FromShape $n5 -ToShape $n6

    $null = New-Connector -Page $Page -FromShape $n4 -ToShape $audit `
        -FromX 0.5 -FromY 0.0 -ToX 0.5 -ToY 1.0
    $null = New-Connector -Page $Page -FromShape $qualified -ToShape $family `
        -FromX 0.5 -FromY 0.0 -ToX 0.18 -ToY 1.0 -Dashed $true -Arrow $false

    $null = New-Label -Page $Page -X1 6.35 -Y1 2.93 -X2 7.55 -Y2 3.28 `
        -Text $Labels.PassOnly -FontName $FontName -LanguageId $LanguageId
    $null = New-Label -Page $Page -X1 4.48 -Y1 2.90 -X2 5.82 -Y2 3.27 `
        -Text $Labels.AllDecisions -FontName $FontName -LanguageId $LanguageId

    # A controlled three-segment dashed path prevents crossings and keeps the
    # trace-back visually separate from the forward publication path.
    $null = New-TraceSegment -Page $Page -X1 11.625 -Y1 3.45 -X2 11.625 -Y2 0.25
    $null = New-TraceSegment -Page $Page -X1 11.625 -Y1 0.25 -X2 5.98 -Y2 0.25
    $null = New-TraceSegment -Page $Page -X1 5.98 -Y1 0.25 -X2 5.98 -Y2 0.85 -Arrow $true
    $null = New-Label -Page $Page -X1 8.75 -Y1 0.35 -X2 11.45 -Y2 0.75 `
        -Text $Labels.TraceBack -FontName $FontName -LanguageId $LanguageId -WhiteBackground $true

    $Page.ResizeToFitContents()
}

$labelsZh = @{
    N1 = "冻结语料`n与规则`n15份构建文档`n1889个`n抽取页"
    N2 = "页面级候选`n生成`n保留原文`n物理页`n表格位置"
    N3 = "规范化三元组与`n页面证据记录`n语义去重`n逐次支持`n独立保存"
    N4 = "自动证据质量`n门控`n结构·方向`nE1/E2定位`n关系支持·来源`n非推断"
    Qualified = "证据合格集合`n1698条记录`n1650个去重三元组"
    N5 = "分级中文术语`n规范化`n标准：0.90`n保守：重复0.90`n单次0.95`n严格：`n原冻结状态"
    N6 = "中文应用图`n标准1326条`n保守620条`n严格208条"
    Audit = "全量审计图`n（完整处理台账）`n8003条：合格、`n隔离、拒绝"
    Family = "来源族封顶`n同族重复只计最高支持"
    PassOnly = "仅合格"
    AllDecisions = "全部判定"
    TraceBack = "稳定标识回溯"
}

$labelsEn = @{
    N1 = "Frozen corpus`nand rules`n15 build documents`n1,889 extraction pages"
    N2 = "Page-level candidate`ngeneration`nPreserve source text,`nphysical page and`ntable location"
    N3 = "Normalized triples and`npage evidence records`nSemantic deduplication;`neach support occurrence`nstored independently"
    N4 = "Automated evidence-`nquality gating`nStructure, direction,`nE1/E2 localization,`nrelation support, source`nand non-inference"
    Qualified = "Evidence-qualified set`n1,698 records`n1,650 unique triples"
    N5 = "Tiered Chinese`nterminology normalization`nStandard: 0.90`nConservative:`nrepeated 0.90`nsingleton 0.95`nStrict: frozen state"
    N6 = "Chinese application graph`nStandard: 1,326`nConservative: 620`nStrict: 208"
    Audit = "Full audit graph`n(complete processing ledger)`n8,003: evidence-qualified,`nquarantined,`nrejected"
    Family = "Source-family cap`nRetain the strongest`nsupport per family"
    PassOnly = "Pass only"
    AllDecisions = "All decisions"
    TraceBack = "Stable-ID trace-back"
}

try {
    $app = New-Object -ComObject Visio.Application
    $app.Visible = $false
    # visRasterUseCustomResolution = 3; visRasterPixelsPerInch = 0.
    $app.Settings.SetRasterExportResolution(3, 300, 300, 0)

    $doc = $app.Documents.Add('')
    $pageZh = $doc.Pages.Item(1)
    $pageZh.NameU = 'CN_Method_Flowchart'
    $pageZh.Name = '中文流程图'
    $pageEn = $doc.Pages.Add()
    $pageEn.NameU = 'EN_Method_Flowchart'
    $pageEn.Name = 'English Flowchart'

    Build-FlowchartPage -Page $pageZh -Labels $labelsZh -FontName 'Microsoft YaHei UI' -LanguageId 2052
    Build-FlowchartPage -Page $pageEn -Labels $labelsEn -FontName 'Arial' -LanguageId 1033

    [void]$doc.SaveAs($vsdxPath)
    $pageZh.Export($svgZhPath)
    $pageEn.Export($svgEnPath)
    $pageZh.Export($pngZhPath)
    $pageEn.Export($pngEnPath)

    # visFixedFormatPDF = 1; visDocExIntentPrint = 1; visPrintAll = 0.
    $doc.ExportAsFixedFormat(
        1, $pdfBilingualPath, 1, 0, 1, 2,
        $false, $true, $true, $false, $false, [System.Type]::Missing
    )
    $doc.Saved = $true
}
finally {
    if ($null -ne $doc) {
        try {
            $doc.Saved = $true
            $doc.Close()
        }
        catch {
            Write-Warning "Visio document cleanup reported: $($_.Exception.Message)"
        }
    }
    if ($null -ne $app) {
        try { $app.Quit() } catch {}
        if ($null -ne $doc) {
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)
        }
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)
    }
}

$pdfSeparate = Get-Command 'pdfseparate.exe' -ErrorAction SilentlyContinue
if ($null -eq $pdfSeparate) {
    $pdfSeparate = Get-Command 'pdfseparate' -ErrorAction SilentlyContinue
}
if ($null -eq $pdfSeparate) {
    throw 'pdfseparate was not found; the bilingual PDF exists, but page PDFs were not split.'
}

& $pdfSeparate.Source $pdfBilingualPath $splitPattern
if ($LASTEXITCODE -ne 0) {
    throw "pdfseparate failed with exit code $LASTEXITCODE"
}
Move-Item -LiteralPath ($splitPattern -replace '%d', '1') -Destination $pdfZhPath -Force
Move-Item -LiteralPath ($splitPattern -replace '%d', '2') -Destination $pdfEnPath -Force

$expected = @(
    $vsdxPath, $svgZhPath, $svgEnPath, $pngZhPath, $pngEnPath,
    $pdfBilingualPath, $pdfZhPath, $pdfEnPath
)
$missing = @($expected | Where-Object { -not [System.IO.File]::Exists($_) })
if ($missing.Count -gt 0) {
    throw "Missing generated files: $($missing -join ', ')"
}

[pscustomobject]@{
    Vsdx = $vsdxPath
    Pages = @('中文流程图', 'English Flowchart')
    SvgZh = $svgZhPath
    SvgEn = $svgEnPath
    PngZh = $pngZhPath
    PngEn = $pngEnPath
    PdfBilingual = $pdfBilingualPath
    PdfZh = $pdfZhPath
    PdfEn = $pdfEnPath
} | ConvertTo-Json -Depth 3
