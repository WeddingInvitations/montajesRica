# Regenera iconos públicos desde el logo original, sin recortarlo ni deformarlo.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$root = Split-Path $PSScriptRoot -Parent
$output = Join-Path $root 'static\icons'
[System.IO.Directory]::CreateDirectory($output) | Out-Null
$source = [System.Drawing.Image]::FromFile((Join-Path $root 'logoMontajes.jpeg'))
try {
    foreach ($size in @(16, 32, 48, 180, 192, 512)) {
        $bitmap = New-Object System.Drawing.Bitmap($size, $size)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.Clear([System.Drawing.ColorTranslator]::FromHtml('#292725'))
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $ratio = [Math]::Min($size / $source.Width, $size / $source.Height)
            $width = [int][Math]::Round($source.Width * $ratio)
            $height = [int][Math]::Round($source.Height * $ratio)
            $graphics.DrawImage($source, [int](($size - $width) / 2), [int](($size - $height) / 2), $width, $height)
            $bitmap.Save((Join-Path $output "icon-$size.png"), [System.Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    }
    # ICO multirresolución con imágenes PNG para navegadores modernos.
    $sizes = @(16, 32, 48)
    $stream = [System.IO.File]::Create((Join-Path $output 'favicon.ico'))
    $writer = New-Object System.IO.BinaryWriter($stream)
    try {
        $writer.Write([uint16]0)
        $writer.Write([uint16]1)
        $writer.Write([uint16]$sizes.Count)
        $offset = 6 + 16 * $sizes.Count
        foreach ($size in $sizes) {
            $bytes = [System.IO.File]::ReadAllBytes((Join-Path $output "icon-$size.png"))
            $writer.Write([byte]$size)
            $writer.Write([byte]$size)
            $writer.Write([byte]0)
            $writer.Write([byte]0)
            $writer.Write([uint16]1)
            $writer.Write([uint16]32)
            $writer.Write([uint32]$bytes.Length)
            $writer.Write([uint32]$offset)
            $offset += $bytes.Length
        }
        foreach ($size in $sizes) {
            $writer.Write([System.IO.File]::ReadAllBytes((Join-Path $output "icon-$size.png")))
        }
    } finally { $writer.Dispose() }
} finally { $source.Dispose() }
Write-Output 'Iconos generados desde logoMontajes.jpeg.'