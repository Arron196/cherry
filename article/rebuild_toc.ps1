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

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($InputPath)

    $tocHeading = $null
    for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
        $para = $doc.Paragraphs.Item($i)
        $text = ($para.Range.Text -replace "`r", '' -replace [char]7, '').Trim()
        if ($text -eq '目  录' -or $text -eq '目录' -or $text -eq '目 录') {
            $tocHeading = $para
            break
        }
    }

    if ($null -eq $tocHeading) {
        throw '未找到目录标题段落。'
    }

    # 强制去掉目录标题前的任何自动编号/列表编号
    try {
        $tocHeading.Range.ListFormat.RemoveNumbers() | Out-Null
    } catch {}
    $tocHeading.Range.Text = "目  录`r"
    $tocHeading.Alignment = 1

    # 删除已有目录字段
    while ($doc.TablesOfContents.Count -gt 0) {
        $doc.TablesOfContents.Item(1).Delete()
    }

    # 在“目 录”标题后重新插入目录
    $tocRange = $tocHeading.Range.Duplicate
    $tocRange.Collapse($wdCollapseEnd)
    $tocRange.InsertParagraphAfter() | Out-Null
    $tocRange.Collapse($wdCollapseEnd)

    $null = $doc.TablesOfContents.Add(
        $tocRange,
        $false,
        1,
        3,
        $false,
        '',
        $true,
        $true,
        '论文一级标题,1,论文二级标题,2,论文三级标题,3',
        $false,
        $true,
        $false
    )

    # 重新设置两节页脚，避免目录页混入正文页码
    for ($i = 1; $i -le $doc.Sections.Count; $i++) {
        $sec = $doc.Sections.Item($i)
        $header = $sec.Headers.Item(1)
        $footer = $sec.Footers.Item(1)
        $header.Range.Text = ''
        $footer.Range.Text = ''
        $footer.LinkToPrevious = $false

        if ($i -eq 2) {
            $range = $footer.Range
            $range.Text = ''
            $range.ParagraphFormat.Alignment = 1
            $range.Collapse($wdCollapseEnd)
            $null = $doc.Fields.Add($range, 33)
            $range.Font.Name = 'Times New Roman'
            $range.Font.Size = 9
            $footer.PageNumbers.RestartNumberingAtSection = $true
            $footer.PageNumbers.StartingNumber = 1
        }
    }

    $doc.Repaginate()
    for ($i = 1; $i -le $doc.TablesOfContents.Count; $i++) {
        $doc.TablesOfContents.Item($i).Update()
    }
    $doc.Fields.Update() | Out-Null

    $doc.SaveAs([ref]$OutputPath)
    $doc.Close($false)
}
finally {
    $word.Quit()
}
