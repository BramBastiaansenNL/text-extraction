param(
    [string]$Python = 'python',
    [string]$ModelDir = '.\models'
)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $resolvedModelDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $ModelDir))
    $env:PADDLE_PDX_CACHE_HOME = Join-Path $PSScriptRoot '.paddlex-cache'
    $venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        try {
            $version = & $Python -c 'import sys; print(sys.version_info.major * 100 + sys.version_info.minor)'
        } catch {
            throw 'Install Python 3.11 or 3.12 and enable Add Python to PATH, or run .\setup.ps1 -Python "C:\path\to\python.exe".'
        }
        if ($LASTEXITCODE -ne 0 -or $version -notin @('311', '312')) {
            throw 'Setup needs Python 3.11 or 3.12. Run .\setup.ps1 -Python "C:\path\to\python.exe" for a specific interpreter.'
        }
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
    }
    $version = & $venvPython -c 'import sys; print(sys.version_info.major * 100 + sys.version_info.minor)'
    if ($LASTEXITCODE -ne 0 -or $version -notin @('311', '312')) {
        throw 'The existing .venv uses an unsupported Python version. Remove it or specify Python 3.11/3.12 in a fresh setup.'
    }
    & $venvPython -m pip install -e '.[ocr,test]'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    & $venvPython -m ocrpipe.setup_models $resolvedModelDir
    if ($LASTEXITCODE -ne 0) { throw 'Model setup failed' }
    Write-Host "Setup complete. Double-click Start Review.cmd to open the local interface."
} finally {
    Pop-Location
}
