param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($InputPath)

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
            $range.Collapse(0)
            $null = $doc.Fields.Add($range, 33)
            $range.Font.Name = 'Times New Roman'
            $range.Font.Size = 9
            $footer.PageNumbers.RestartNumberingAtSection = $true
            $footer.PageNumbers.StartingNumber = 1
        }
    }

    while ($doc.TablesOfContents.Count -gt 0) {
        $doc.TablesOfContents.Item(1).Delete()
    }

    $findRange = $doc.Content
    $find = $findRange.Find
    $find.ClearFormatting()
    $find.Text = '[[TOC]]'
    if ($find.Execute()) {
        $tocRange = $findRange
        $tocRange.Text = ''
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
