$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$dirtyRoot = [System.IO.Path]::GetFullPath('C:\Coding Projects\Tearsheet Generator')
$here = [System.IO.Path]::GetFullPath($PSScriptRoot)
if ($here -eq $dirtyRoot) {
    Write-Error "Refusing to start Y&Q from the dirty Tearsheet Generator checkout: $here"
    exit 1
}

$env:PYTHONIOENCODING = 'utf-8'
# Authoritative monthly CSV remains at the repo root; do not invent/copy data.
$env:YQ_CSV_PATH = Join-Path $dirtyRoot 'yq.csv'

$python = Join-Path $PSScriptRoot '.venv310\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = 'python'
}
& $python (Join-Path $PSScriptRoot 'yq_ts.py')
