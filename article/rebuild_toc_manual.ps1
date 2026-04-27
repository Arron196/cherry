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

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($InputPath)

    $tocHeadingIndex = 0
    $tocStartIndex = 0
    $tocEndIndex = 0
    $entries = @()

    for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
        $p = $doc.Paragraphs.Item($i)
        $text = ($p.Range.Text -replace "`r", '' -replace [char]7, '')
        $trim = $text.Trim()

        if ($tocHeadingIndex -eq 0 -and ($trim -eq '目  录' -or $trim -eq '目录' -or $trim -eq '目 录')) {
            $tocHeadingIndex = $i
            continue
        }

        if ($tocHeadingIndex -gt 0 -and $tocStartIndex -eq 0 -and $text -match "`t\d+\s*$") {
            $tocStartIndex = $i
        }

        if ($tocStartIndex -gt 0) {
            if ($text -match "^(.*)`t(\d+)\s*$") {
                $entries += [PSCustomObject]@{
                    Title = $matches[1]
                    Page = $matches[2]
                }
                $tocEndIndex = $i
            } elseif ($trim -eq '') {
                continue
            } else {
                break
            }
        }
    }

    if ($tocHeadingIndex -eq 0 -or $tocStartIndex -eq 0 -or $tocEndIndex -eq 0) {
        throw '未能识别目录区间。'
    }

    $headingPara = $doc.Paragraphs.Item($tocHeadingIndex)
    while ($doc.TablesOfContents.Count -gt 0) {
        $doc.TablesOfContents.Item(1).Delete()
    }
    # 删除旧目录条目，倒序删可避开字段范围问题
    for ($i = $tocEndIndex; $i -ge $tocStartIndex; $i--) {
        try {
            $doc.Paragraphs.Item($i).Range.Delete() | Out-Null
        } catch {}
    }

    # 目录标题单独排版
    try { $headingPara.Range.ListFormat.RemoveNumbers() | Out-Null } catch {}
    $headingPara.Range.Text = "目  录`r"
    $headingPara.Alignment = $wdAlignParagraphCenter
    $headingPara.LeftIndent = 0
    $headingPara.FirstLineIndent = 0
    $headingPara.Range.Font.NameAscii = 'Times New Roman'
    $headingPara.Range.Font.NameFarEast = '宋体'
    $headingPara.Range.Font.Size = 16
    $headingPara.Range.Font.Bold = -1
    $headingPara.LineSpacingRule = 0

    # 在目录标题后插入一个空行
    $insertPos = $headingPara.Range.End
    $doc.Range($insertPos, $insertPos).InsertAfter("`r")

    # 节分隔段落现在位于目录后，反向插入条目可保持顺序
    $anchorPara = $doc.Paragraphs.Item($tocHeadingIndex + 2)

    for ($idx = $entries.Count - 1; $idx -ge 0; $idx--) {
        $entry = $entries[$idx]
        $r = $doc.Range($anchorPara.Range.Start, $anchorPara.Range.Start)
        $r.InsertBefore($entry.Title + "`t" + $entry.Page + "`r")
    }

    # 重新获取并格式化目录条目
    for ($i = $tocHeadingIndex + 2; $i -lt $anchorPara.Range.Paragraphs(1).Range.Start; $i++) {
        # noop placeholder to satisfy parser
    }

    $firstNewIndex = $tocHeadingIndex + 2
    $lastNewIndex = $firstNewIndex + $entries.Count - 1

    for ($i = $firstNewIndex; $i -le $lastNewIndex; $i++) {
        $p = $doc.Paragraphs.Item($i)
        $text = ($p.Range.Text -replace "`r", '' -replace [char]7, '').Trim()

        $p.Alignment = $wdAlignParagraphLeft
        $p.LeftIndent = 0
        $p.FirstLineIndent = 0
        try { $p.TabStops.ClearAll() } catch {}
        $null = $p.TabStops.Add(467.2, $wdAlignTabRight, $wdTabLeaderDots)

        $p.Range.Font.NameAscii = 'Times New Roman'
        $p.Range.Font.NameFarEast = '宋体'
        $p.Range.Font.Size = 12
        $p.Range.Font.Bold = 0
        $p.LineSpacingRule = 4
        $p.LineSpacing = 20

        # 目录缩进
        if ($text -match '^\d+\.\d+\.\d+') {
            $p.LeftIndent = 24
        } elseif ($text -match '^\d+\.\d+') {
            $p.LeftIndent = 12
        } else {
            $p.LeftIndent = 0
        }

        # 摘要、关键词、Abstract、Keywords、参考文献等一级特殊项可加粗
        if ($text -match '^(摘要|关键词|Abstract|Keywords|参考文献|致谢|附录)\b') {
            $p.Range.Font.Bold = -1
        }
    }

    $doc.SaveAs([ref]$OutputPath)
    $doc.Close($false)
}
finally {
    $word.Quit()
}
