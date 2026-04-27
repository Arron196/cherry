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

    $tocHeading = $null
    $tocHeadingIndex = 0
    for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
        $p = $doc.Paragraphs.Item($i)
        $text = ($p.Range.Text -replace "`r", '' -replace [char]7, '').Trim()
        if ($text -eq '目  录' -or $text -eq '目录' -or $text -eq '目 录') {
            $tocHeading = $p
            $tocHeadingIndex = $i
            break
        }
    }

    if ($null -eq $tocHeading) {
        throw '未找到目录标题。'
    }

    # 目录标题单独定型
    try { $tocHeading.Range.ListFormat.RemoveNumbers() | Out-Null } catch {}
    $tocHeading.Range.Text = "目  录`r"
    $tocHeading.Alignment = 1
    $tocHeading.LeftIndent = 0
    $tocHeading.FirstLineIndent = 0
    $tocHeading.Range.Font.NameAscii = 'Times New Roman'
    $tocHeading.Range.Font.NameFarEast = '宋体'
    $tocHeading.Range.Font.Size = 16
    $tocHeading.Range.Font.Bold = -1

    # 目录项统一字体，修正第一条目录项被带成标题样式的问题
    for ($i = $tocHeadingIndex + 1; $i -le $doc.Paragraphs.Count; $i++) {
        $p = $doc.Paragraphs.Item($i)
        $text = ($p.Range.Text -replace "`r", '' -replace [char]7, '').Trim()
        if (-not $text) { continue }
        if ($text -eq '目  录') { continue }
        if ($text -notmatch "`t") { break }

        try {
            if ($text -match '^\d+\.\d+\.\d+') {
                $p.Range.Style = $doc.Styles.Item('TOC 3')
            } elseif ($text -match '^\d+\.\d+') {
                $p.Range.Style = $doc.Styles.Item('TOC 2')
            } else {
                $p.Range.Style = $doc.Styles.Item('TOC 1')
            }
        } catch {}

        $p.Range.Font.NameAscii = 'Times New Roman'
        $p.Range.Font.NameFarEast = '宋体'
        $p.Range.Font.Size = 12
        $p.Range.Font.Bold = 0
    }

    $doc.Fields.Update() | Out-Null
    $doc.SaveAs([ref]$OutputPath)
    $doc.Close($false)
}
finally {
    $word.Quit()
}
