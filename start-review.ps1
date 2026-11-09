param(
    [string]$OutputRoot = '.\review-runs',
    [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $exe = Join-Path $PSScriptRoot '.venv\Scripts\ocrpipe.exe'
    $weights = Join-Path $PSScriptRoot 'models\.paddlex-cache\official_models\PP-OCRv5_mobile_rec'
    if (-not (Test-Path -LiteralPath $exe) -or -not (Test-Path -LiteralPath $weights)) {
        throw 'Setup is incomplete. Double-click Setup.cmd first.'
    }
    $output = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $OutputRoot))
    Write-Host 'Starting local review. Leave this window open while using the browser.'
    Write-Host 'Press Ctrl+C here when finished.'
    & $exe review --model-dir (Join-Path $PSScriptRoot 'models') --output-root $output --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Local review could not start' }
} finally {
    Pop-Location
}
