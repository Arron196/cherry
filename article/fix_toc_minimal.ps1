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

    foreach ($styleName in @('TOC 1', 'TOC 2', 'TOC 3')) {
        try {
            $s = $doc.Styles.Item($styleName)
            $s.Font.NameAscii = 'Times New Roman'
            $s.Font.NameFarEast = '宋体'
            $s.Font.Size = 12
            $s.Font.Bold = 0
        } catch {}
    }

    try {
        $s = $doc.Styles.Item('TOC 标题')
        $s.Font.NameAscii = 'Times New Roman'
        $s.Font.NameFarEast = '宋体'
        $s.Font.Size = 16
        $s.Font.Bold = -1
    } catch {}

    $tocHeading = $null
    for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
        $p = $doc.Paragraphs.Item($i)
        $text = ($p.Range.Text -replace "`r", '' -replace [char]7, '').Trim()
        if ($text -eq '目  录' -or $text -eq '目录' -or $text -eq '目 录') {
            $tocHeading = $p
            break
        }
    }

    if ($null -eq $tocHeading) {
        throw '未找到目录标题。'
    }

    try { $tocHeading.Range.ListFormat.RemoveNumbers() | Out-Null } catch {}
    $tocHeading.Range.Text = "目  录`r"
    $tocHeading.Alignment = 1
    $tocHeading.LeftIndent = 0
    $tocHeading.FirstLineIndent = 0
    $tocHeading.Range.Font.NameAscii = 'Times New Roman'
    $tocHeading.Range.Font.NameFarEast = '宋体'
    $tocHeading.Range.Font.Size = 16
    $tocHeading.Range.Font.Bold = -1

    $doc.Fields.Update() | Out-Null
    $doc.SaveAs([ref]$OutputPath)
    $doc.Close($false)
}
finally {
    $word.Quit()
}
