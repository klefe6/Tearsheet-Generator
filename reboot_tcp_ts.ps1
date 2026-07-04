$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$envFile = Join-Path $PSScriptRoot '.tcp_production.env'
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        # Batch format: set "NAME=value" (single quoted token, not set "NAME"=value)
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
$python = Join-Path $PSScriptRoot '.venv310\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'tcp_ts_v2.py')
