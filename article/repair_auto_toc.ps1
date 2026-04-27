param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

$wdAlignParagraphLeft = 0
$wdAlignParagraphCenter = 1
$wdAlignTabRight = 2
$wdTabLeaderDots = 1
$wdLineSpaceExactly = 4
$tabPosition = 467.2

function Set-StyleFont {
    param(
        $Style,
        [string]$Ascii,
        [string]$FarEast,
        [double]$Size,
        [int]$Bold
    )
    $Style.Font.NameAscii = $Ascii
    $Style.Font.NameFarEast = $FarEast
    $Style.Font.Size = $Size
    $Style.Font.Bold = $Bold
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($InputPath)

    # 先更新自动目录，确保页码正确
    $doc.Repaginate()
    if ($doc.TablesOfContents.Count -gt 0) {
        $doc.TablesOfContents.Item(1).Update()
    }
    $doc.Fields.Update() | Out-Null

    # 修目录相关样式，保证后续更新不至于完全跑偏
    try { Set-StyleFont -Style $doc.Styles.Item('TOC 标题') -Ascii 'Times New Roman' -FarEast '宋体' -Size 16 -Bold -1 } catch {}
    foreach ($name in @('TOC 1', 'TOC 2', 'TOC 3')) {
        try { Set-StyleFont -Style $doc.Styles.Item($name) -Ascii 'Times New Roman' -FarEast '宋体' -Size 12 -Bold 0 } catch {}
    }

    # 找目录标题
    $tocHeading = $null
    for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
        $p = $doc.Paragraphs.Item($i)
        $text = ($p.Range.Text -replace "`r", '' -replace [char]7, '').Trim()
        if ($text -eq '目  录' -or $text -eq '目录' -or $text -eq '目 录') {
            $tocHeading = $p
            break
        }
    }
    if ($null -eq $tocHeading) { throw '未找到目录标题。' }

    # 目录标题：去掉误加的自动编号，并设置成独立标题样式
    try { $tocHeading.Range.ListFormat.RemoveNumbers() | Out-Null } catch {}
    try { $tocHeading.Range.Style = $doc.Styles.Item('正文') } catch {}
    $tocHeading.Range.Text = "目  录`r"
    $tocHeading.Alignment = $wdAlignParagraphCenter
    $tocHeading.LeftIndent = 0
    $tocHeading.FirstLineIndent = 0
    try { $tocHeading.Range.ParagraphFormat.TabStops.ClearAll() } catch {}
    $tocHeading.LineSpacingRule = 0
    $tocHeading.Range.Font.NameAscii = 'Times New Roman'
    $tocHeading.Range.Font.NameFarEast = '宋体'
    $tocHeading.Range.Font.Size = 16
    $tocHeading.Range.Font.Bold = -1

    # 自动目录正文：保持超链接，同时重设点线、缩进、字体、行距
    if ($doc.TablesOfContents.Count -gt 0) {
        $toc = $doc.TablesOfContents.Item(1)
        $paras = $toc.Range.Paragraphs
        for ($i = 1; $i -le $paras.Count; $i++) {
            $p = $paras.Item($i)
            $text = ($p.Range.Text -replace "`r", '' -replace [char]7, '').Trim()
            if (-not $text) { continue }

            $p.Alignment = $wdAlignParagraphLeft
            $p.Range.ParagraphFormat.FirstLineIndent = 0
            try { $p.Range.ParagraphFormat.CharacterUnitFirstLineIndent = 0 } catch {}
            $p.LeftIndent = 0
            $p.LineSpacingRule = $wdLineSpaceExactly
            $p.LineSpacing = 20
            try { $p.TabStops.ClearAll() } catch {}
            $null = $p.TabStops.Add($tabPosition, $wdAlignTabRight, $wdTabLeaderDots)

            if ($text -match '^\d+\.\d+\.\d+') {
                $p.LeftIndent = 24
            } elseif ($text -match '^\d+\.\d+') {
                $p.LeftIndent = 12
            } else {
                $p.LeftIndent = 0
            }

            $p.Range.Font.NameAscii = 'Times New Roman'
            $p.Range.Font.NameFarEast = '宋体'
            $p.Range.Font.Size = 12

            if ($text -match '^(摘要|关键词|Abstract|Keywords|参考文献|致谢|附录)') {
                $p.Range.Font.Bold = -1
            } else {
                $p.Range.Font.Bold = 0
            }
        }
    }

    $doc.SaveAs([ref]$OutputPath)
    $doc.Close($false)
}
finally {
    $word.Quit()
}
