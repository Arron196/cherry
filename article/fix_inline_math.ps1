param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

function Get-ContentRange {
    param($Paragraph)
    $rng = $Paragraph.Range.Duplicate
    if ($rng.End -gt $rng.Start) {
        $rng.End = $rng.End - 1
    }
    return $rng
}

function Replace-TextWithOMath {
    param(
        $Paragraph,
        [string]$FindText,
        [string]$LinearText
    )

    $rng = Get-ContentRange $Paragraph
    $find = $rng.Find
    $find.ClearFormatting()
    $find.Text = $FindText
    $find.Forward = $true
    $find.Wrap = 0

    if ($find.Execute()) {
        $rng.Text = $LinearText
        $Paragraph.Range.OMaths.Add($rng) | Out-Null
        if ($rng.OMaths.Count -gt 0) {
            $rng.OMaths.Item(1).BuildUp()
        }
        return $true
    }
    return $false
}

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($InputPath)

    $replacements = @(
        @{
            Anchor = '设第i个区块的哈希为H_i = SHA3-256(blockHeader_i)'
            Items = @(
                @{ Find = 'H_i = SHA3-256(blockHeader_i)'; Math = 'H_i = SHA3-256(blockHeader_i)' },
                @{ Find = 'blockHeader_i.parentHash = H_{i-1}'; Math = 'blockHeader_i.parentHash = H_(i-1)' },
                @{ Find = 'H_i'; Math = 'H_i' }
            )
        },
        @{
            Anchor = '其中S_T和S_{RH}分别为16位温度和湿度原始值。'
            Items = @(
                @{ Find = 'S_T'; Math = 'S_T' },
                @{ Find = 'S_{RH}'; Math = 'S_(RH)' }
            )
        },
        @{
            Anchor = '本系统采集三轴加速度的合矢量 a = sqrt'
            Items = @(
                @{ Find = 'a = sqrt{a_x^2 + a_y^2 + a_z^2}'; Math = 'a = \sqrt(a_x^2 + a_y^2 + a_z^2)' }
            )
        },
        @{
            Anchor = '其中素数 p = 2^{256} - 2^{224} + 2^{192} + 2^{96} - 1'
            Items = @(
                @{ Find = 'p = 2^{256} - 2^{224} + 2^{192} + 2^{96} - 1'; Math = 'p = 2^256 - 2^224 + 2^192 + 2^96 - 1' },
                @{ Find = 'a = -3'; Math = 'a = -3' },
                @{ Find = 'Q = d · G'; Math = 'Q = d \cdot G' }
            )
        },
        @{
            Anchor = '随机生成临时密钥 k ∈ [1, n-1]'
            Items = @(
                @{ Find = 'k ∈ [1, n-1]'; Math = 'k \in [1, n-1]' }
            )
        },
        @{
            Anchor = '计算椭圆曲线点 (x_1, y_1) = k · G'
            Items = @(
                @{ Find = '(x_1, y_1) = k · G'; Math = '(x_1, y_1) = k \cdot G' },
                @{ Find = 'r = x_1 mod n'; Math = 'r = x_1 \bmod n' }
            )
        },
        @{
            Anchor = '计算 s = k^{-1}(e + r · d) mod n'
            Items = @(
                @{ Find = 's = k^{-1}(e + r · d) mod n'; Math = 's = k^(-1)(e + r \cdot d) \bmod n' }
            )
        },
        @{
            Anchor = '验证方持有公钥 Q 时，可独立验证：计算 u_1 = e · s^{-1} mod n'
            Items = @(
                @{ Find = 'Q'; Math = 'Q' },
                @{ Find = 'u_1 = e · s^{-1} mod n'; Math = 'u_1 = e \cdot s^(-1) \bmod n' },
                @{ Find = 'u_2 = r · s^{-1} mod n'; Math = 'u_2 = r \cdot s^(-1) \bmod n' },
                @{ Find = '(x, y) = u_1G + u_2Q'; Math = '(x, y) = u_1 G + u_2 Q' },
                @{ Find = 'x ≡ r (mod n)'; Math = 'x \equiv r \pmod n' }
            )
        },
        @{
            Anchor = '其中B_i为第i个指标的分段得分'
            Items = @(
                @{ Find = 'B_i'; Math = 'B_i' },
                @{ Find = 'w_i'; Math = 'w_i' }
            )
        }
    )

    for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
        $para = $doc.Paragraphs.Item($i)
        $text = ($para.Range.Text -replace "`r", '' -replace [char]7, '')
        foreach ($group in $replacements) {
            if ($text -like "*$($group.Anchor)*") {
                foreach ($item in $group.Items) {
                    Replace-TextWithOMath -Paragraph $para -FindText $item.Find -LinearText $item.Math | Out-Null
                }
            }
        }
    }

    $doc.Fields.Update() | Out-Null
    $doc.SaveAs([ref]$OutputPath)
    $doc.Close($false)
}
finally {
    $word.Quit()
}
