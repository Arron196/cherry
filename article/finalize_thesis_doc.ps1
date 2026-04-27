param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

function Get-CleanParagraphText {
    param($Paragraph)
    return ($Paragraph.Range.Text -replace "`r", "" -replace [char]7, "").Trim()
}

function Get-ContentRange {
    param($Paragraph)
    $rng = $Paragraph.Range.Duplicate
    if ($rng.End -gt $rng.Start) {
        $rng.End = $rng.End - 1
    }
    return $rng
}

function Convert-InlineMathText {
    param([string]$Text)

    $t = $Text
    $t = [regex]::Replace($t, '\$\$([^$]+)\$\$', '$1')
    $t = [regex]::Replace($t, '\$([^$]+)\$', '$1')
    $t = $t.Replace('\mathbb{F}_p', 'F_p')
    $t = [regex]::Replace($t, '\\text\{([^}]*)\}', '$1')
    $t = $t.Replace('\cdot', '·')
    $t = $t.Replace('\times', '×')
    $t = $t.Replace('\equiv', '≡')
    $t = [regex]::Replace($t, '\\pmod\{([^}]*)\}', '(mod $1)')
    $t = [regex]::Replace($t, '\\in\b', '∈')
    $t = [regex]::Replace($t, '\\le\b', '≤')
    $t = [regex]::Replace($t, '\\ge\b', '≥')
    $t = [regex]::Replace($t, '\\', '')
    return $t
}

function Get-DisplayFormulaLinear {
    param([string]$Text)

    if ($Text -match '^\$\$T\{°C\}') {
        return 'T_(°C) = -45 + 175 × S_T/(2^16 - 1)'
    }
    if ($Text -match '^\$\$RH\{\\%\}') {
        return 'RH_(%) = 100 × S_RH/(2^16 - 1)'
    }
    if ($Text -match '^\$\$y\^2') {
        return 'y^2 ≡ x^3 + ax + b (mod p)'
    }
    if ($Text -match '^\$\$Q = ') {
        return 'Q = ∑_(i) w_i · B_i'
    }
    return $null
}

function Replace-FigureCaptionWithField {
    param($Document, $Paragraph, [int]$Chapter, [string]$Title)

    $Paragraph.Alignment = 1
    $content = Get-ContentRange $Paragraph
    $content.Text = "图$Chapter-"

    $seqRange = Get-ContentRange $Paragraph
    $seqRange.Collapse(0)
    $null = $Document.Fields.Add($seqRange, -1, "SEQ fig_ch$Chapter \* ARABIC", $false)

    $tailRange = Get-ContentRange $Paragraph
    $tailRange.Collapse(0)
    $tailRange.InsertAfter(" $Title")
}

function Replace-DisplayFormula {
    param($Paragraph, [string]$LinearText)

    $Paragraph.Alignment = 1
    $content = Get-ContentRange $Paragraph
    $content.Text = $LinearText
    $Paragraph.Range.OMaths.Add($content) | Out-Null
    if ($Paragraph.Range.OMaths.Count -gt 0) {
        $Paragraph.Range.OMaths.Item(1).BuildUp()
    }
}

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($InputPath)

    # 图题改为自动编号字段
    for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
        $para = $doc.Paragraphs.Item($i)
        $clean = Get-CleanParagraphText $para
        if ($clean -match '^图(\d+)-\d+\s+(.+)$') {
            $chapter = [int]$matches[1]
            $title = $matches[2]
            Replace-FigureCaptionWithField $doc $para $chapter $title
        }
    }

    # 显示公式与行内公式处理
    for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
        $para = $doc.Paragraphs.Item($i)
        $clean = Get-CleanParagraphText $para
        if (-not $clean) {
            continue
        }

        $display = Get-DisplayFormulaLinear $clean
        if ($null -ne $display) {
            Replace-DisplayFormula $para $display
            continue
        }

        if ($clean.Contains('$')) {
            $converted = Convert-InlineMathText $clean
            if ($converted -ne $clean) {
                $content = Get-ContentRange $para
                $content.Text = $converted
            }
        }
    }

    # 表格宽度收敛到版心
    for ($i = 1; $i -le $doc.Tables.Count; $i++) {
        $table = $doc.Tables.Item($i)
        $table.AllowAutoFit = $true
        $table.AutoFitBehavior(2)
        $table.Rows.Alignment = 1
        $table.Rows.LeftIndent = 0
    }

    # 页眉页脚与目录更新
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
