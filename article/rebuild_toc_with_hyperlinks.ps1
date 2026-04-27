param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

$wdCollapseEnd = 0
$wdAlignParagraphLeft = 0
$wdAlignParagraphCenter = 1
$wdAlignTabRight = 2
$wdTabLeaderDots = 1
$wdLineSpaceExactly = 4
$tabPosition = 467.2

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($InputPath)

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

    # 标题单独设置，去掉可能的列表编号
    try { $tocHeading.Range.ListFormat.RemoveNumbers() | Out-Null } catch {}
    $tocHeading.Range.Text = "目  录`r"
    $tocHeading.Alignment = $wdAlignParagraphCenter
    $tocHeading.LeftIndent = 0
    $tocHeading.FirstLineIndent = 0
    $tocHeading.LineSpacingRule = 0
    $tocHeading.Range.Font.NameAscii = 'Times New Roman'
    $tocHeading.Range.Font.NameFarEast = '宋体'
    $tocHeading.Range.Font.Size = 16
    $tocHeading.Range.Font.Bold = -1

    # 删除旧自动目录
    while ($doc.TablesOfContents.Count -gt 0) {
        $doc.TablesOfContents.Item(1).Delete()
    }

    # 在“目 录”后插入一个空段和新的自动目录
    $tocRange = $tocHeading.Range.Duplicate
    $tocRange.Collapse($wdCollapseEnd)
    $tocRange.InsertParagraphAfter() | Out-Null
    $tocRange.Collapse($wdCollapseEnd)

    $null = $doc.TablesOfContents.Add(
        $tocRange,
        $true,   # UseHeadingStyles
        1,
        3,
        $false,  # UseFields
        '',
        $true,   # RightAlignPageNumbers
        $true,   # IncludePageNumbers
        '论文一级标题,1,论文二级标题,2,论文三级标题,3',
        $true,   # UseHyperlinks
        $false,  # HidePageNumbersInWeb
        $false   # UseOutlineLevels
    )

    $doc.Repaginate()
    $doc.TablesOfContents.Item(1).Update()
    $doc.Fields.Update() | Out-Null

    # 精修目录项版式，但保留自动目录超链接
    $toc = $doc.TablesOfContents.Item(1)
    $paras = $toc.Range.Paragraphs
    for ($i = 1; $i -le $paras.Count; $i++) {
        $p = $paras.Item($i)
        $text = ($p.Range.Text -replace "`r", '' -replace [char]7, '').Trim()
        if (-not $text) { continue }

        $p.Alignment = $wdAlignParagraphLeft
        $p.LeftIndent = 0
        $p.FirstLineIndent = 0
        $p.LineSpacingRule = $wdLineSpaceExactly
        $p.LineSpacing = 20
        try { $p.TabStops.ClearAll() } catch {}
        $null = $p.TabStops.Add($tabPosition, $wdAlignTabRight, $wdTabLeaderDots)

        if ($text -match '^\d+\.\d+\.\d+') {
            $p.LeftIndent = 24
        } elseif ($text -match '^\d+\.\d+') {
            $p.LeftIndent = 12
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

    $doc.SaveAs([ref]$OutputPath)
    $doc.Close($false)
}
finally {
    $word.Quit()
}
