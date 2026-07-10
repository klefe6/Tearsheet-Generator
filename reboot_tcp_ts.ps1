$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'

function Import-BatchEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^set "(.+)"$') {
            $pair = $matches[1]
            $eq = $pair.IndexOf('=')
            if ($eq -gt 0) {
                $name = $pair.Substring(0, $eq)
                $value = $pair.Substring($eq + 1)
                Set-Item -Path "Env:$name" -Value $value
            }
        }
    }
}

Import-BatchEnvFile (Join-Path $PSScriptRoot '.local_dev.env')
$envFile = Join-Path $PSScriptRoot '.tcp_production.env'
if (Test-Path $envFile) { Import-BatchEnvFile $envFile }
$python = Join-Path $PSScriptRoot '.venv310\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'tcp_ts_v2.py')
