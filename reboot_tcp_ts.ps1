$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$envFile = Join-Path $PSScriptRoot '.tcp_production.env'
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^set "(.+)"=(.*)$') {
            Set-Item -Path "Env:$($matches[1])" -Value $matches[2]
        }
    }
}
$python = Join-Path $PSScriptRoot '.venv310\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'tcp_ts_v2.py')
