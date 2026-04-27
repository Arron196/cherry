param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

function Set-ParaFont {
    param(
        $Paragraph,
        [string]$Ascii,
        [string]$FarEast,
        [double]$Size,
        [int]$Bold
    )

    $Paragraph.Range.Font.NameAscii = $Ascii
    $Paragraph.Range.Font.NameFarEast = $FarEast
    $Paragraph.Range.Font.Size = $Size
    $Paragraph.Range.Font.Bold = $Bold
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($InputPath)

    # 修 TOC 样式本身
    foreach ($styleName in @('TOC 1', 'TOC 2', 'TOC 3')) {
        try {
            $style = $doc.Styles.Item($styleName)
            $style.Font.NameAscii = 'Times New Roman'
            $style.Font.NameFarEast = '宋体'
            $style.Font.Size = 12
            $style.Font.Bold = 0
        } catch {}
    }
    try {
        $style = $doc.Styles.Item('TOC 标题')
        $style.Font.NameAscii = 'Times New Roman'
        $style.Font.NameFarEast = '宋体'
        $style.Font.Size = 16
        $style.Font.Bold = -1
    } catch {}

    $tocHeadingIndex = 0
    for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
        $p = $doc.Paragraphs.Item($i)
        $text = ($p.Range.Text -replace "`r", '' -replace [char]7, '').Trim()
        if ($text -eq '目  录' -or $text -eq '目录' -or $text -eq '目 录') {
            $tocHeadingIndex = $i
            break
        }
    }

    if ($tocHeadingIndex -eq 0) {
        throw '未找到目录标题。'
    }

    $tocHeading = $doc.Paragraphs.Item($tocHeadingIndex)
    try { $tocHeading.Range.ListFormat.RemoveNumbers() | Out-Null } catch {}
    $tocHeading.Range.Text = "目  录`r"
    try { $tocHeading.Range.Style = $doc.Styles.Item('TOC 标题') } catch {}
    $tocHeading.Alignment = 1
    $tocHeading.LeftIndent = 0
    $tocHeading.FirstLineIndent = 0
    Set-ParaFont -Paragraph $tocHeading -Ascii 'Times New Roman' -FarEast '宋体' -Size 16 -Bold -1

    # 修目录内容段落，不动字段，只统一样式和字体
    for ($i = $tocHeadingIndex + 1; $i -le $doc.Paragraphs.Count; $i++) {
        $p = $doc.Paragraphs.Item($i)
        $text = ($p.Range.Text -replace "`r", '' -replace [char]7, '')
        $trim = $text.Trim()

        if (-not $trim) { continue }
        if ($trim -eq '目  录') { continue }

        # 目录项都有 Tab + 页码；遇到正文就停止
        if ($text -notmatch "`t\d+") { break }

        if ($trim -match '^\d+\.\d+\.\d+') {
            try { $p.Range.Style = $doc.Styles.Item('TOC 3') } catch {}
        } elseif ($trim -match '^\d+\.\d+') {
            try { $p.Range.Style = $doc.Styles.Item('TOC 2') } catch {}
        } else {
            try { $p.Range.Style = $doc.Styles.Item('TOC 1') } catch {}
        }

        Set-ParaFont -Paragraph $p -Ascii 'Times New Roman' -FarEast '宋体' -Size 12 -Bold 0
    }

    $doc.Fields.Update() | Out-Null
    $doc.SaveAs([ref]$OutputPath)
    $doc.Close($false)
}
finally {
    $word.Quit()
}
