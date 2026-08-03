$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# Main dirty checkout guard — override only via HC_DIRTY_ROOT when explicitly supplied.
$defaultDirtyRoot = [System.IO.Path]::GetFullPath('C:\Coding Projects\Tearsheet Generator')
$dirtyRoot = if ($env:HC_DIRTY_ROOT -and $env:HC_DIRTY_ROOT.Trim()) {
    [System.IO.Path]::GetFullPath($env:HC_DIRTY_ROOT.Trim())
} else {
    $defaultDirtyRoot
}

$here = [System.IO.Path]::GetFullPath($PSScriptRoot)
if ($here -eq $dirtyRoot) {
    Write-Error "Refusing to start Y&Q from the dirty Tearsheet Generator checkout: $here"
    exit 1
}

$env:PYTHONIOENCODING = 'utf-8'
# Authoritative monthly CSV remains at the repo root; do not invent/copy data.
if ($env:HC_YQ_DATA_ROOT -and $env:HC_YQ_DATA_ROOT.Trim()) {
    $yqRoot = [System.IO.Path]::GetFullPath($env:HC_YQ_DATA_ROOT.Trim())
    $env:YQ_CSV_PATH = Join-Path $yqRoot 'yq.csv'
} else {
    $env:YQ_CSV_PATH = Join-Path $dirtyRoot 'yq.csv'
}

$python = Join-Path $PSScriptRoot '.venv310\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = 'python'
}
& $python (Join-Path $PSScriptRoot 'yq_ts.py')
