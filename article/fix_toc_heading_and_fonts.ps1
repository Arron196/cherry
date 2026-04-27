param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

function Set-StyleFont {
    param(
        $Styles,
        [string]$Name,
        [string]$Ascii,
        [string]$FarEast,
        [double]$Size,
        [int]$Bold
    )

    try {
        $style = $Styles.Item($Name)
        $style.Font.NameAscii = $Ascii
        $style.Font.NameFarEast = $FarEast
        $style.Font.Name = $FarEast
        $style.Font.Size = $Size
        $style.Font.Bold = $Bold
    } catch {}
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($InputPath)

    $styles = $doc.Styles

    # 核心样式字体统一
    Set-StyleFont -Styles $styles -Name '正文' -Ascii 'Times New Roman' -FarEast '宋体' -Size 12 -Bold 0
    Set-StyleFont -Styles $styles -Name '论文一级标题' -Ascii 'Times New Roman' -FarEast '宋体' -Size 15 -Bold -1
    Set-StyleFont -Styles $styles -Name '论文二级标题' -Ascii 'Times New Roman' -FarEast '宋体' -Size 14 -Bold -1
    Set-StyleFont -Styles $styles -Name '论文三级标题' -Ascii 'Times New Roman' -FarEast '宋体' -Size 12 -Bold -1
    Set-StyleFont -Styles $styles -Name 'TOC 1' -Ascii 'Times New Roman' -FarEast '宋体' -Size 12 -Bold 0
    Set-StyleFont -Styles $styles -Name 'TOC 2' -Ascii 'Times New Roman' -FarEast '宋体' -Size 12 -Bold 0
    Set-StyleFont -Styles $styles -Name 'TOC 3' -Ascii 'Times New Roman' -FarEast '宋体' -Size 12 -Bold 0
    Set-StyleFont -Styles $styles -Name 'TOC 标题' -Ascii 'Times New Roman' -FarEast '宋体' -Size 16 -Bold -1

    # 修正目录标题段落
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
    try { $tocHeading.Range.Style = $styles.Item('正文') } catch {}
    $tocHeading.Range.Text = "目  录`r"
    $tocHeading.Alignment = 1
    $tocHeading.LeftIndent = 0
    $tocHeading.FirstLineIndent = 0
    $tocHeading.Range.Font.NameAscii = 'Times New Roman'
    $tocHeading.Range.Font.NameFarEast = '宋体'
    $tocHeading.Range.Font.Name = '宋体'
    $tocHeading.Range.Font.Size = 16
    $tocHeading.Range.Font.Bold = -1

    # 再更新一次目录和字段
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
