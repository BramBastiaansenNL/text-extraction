param(
    [string]$Python = 'python',
    [string]$ModelDir = '.\models'
)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $version = & $Python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
    if ($LASTEXITCODE -ne 0 -or $version -notin @('3.11', '3.12')) {
        throw 'Install Python 3.11 or 3.12, then rerun Setup.cmd. Use .\setup.ps1 -Python "C:\path\to\python.exe" for a specific interpreter.'
    }
    $resolvedModelDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $ModelDir))
    $env:PADDLE_PDX_CACHE_HOME = Join-Path $PSScriptRoot '.paddlex-cache'
    $venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
    }
    & $venvPython -m pip install -e '.[ocr,test]'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    & $venvPython -m ocrpipe.setup_models $resolvedModelDir
    if ($LASTEXITCODE -ne 0) { throw 'Model setup failed' }
    Write-Host "Setup complete. Double-click Start Review.cmd to open the local interface."
} finally {
    Pop-Location
}
