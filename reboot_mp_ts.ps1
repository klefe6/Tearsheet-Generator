$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'

# Refuse production launch from the dirty Tearsheet Generator checkout.
$dirtyRoot = [System.IO.Path]::GetFullPath('C:\Coding Projects\Tearsheet Generator')
$here = [System.IO.Path]::GetFullPath($PSScriptRoot)
if ($here -eq $dirtyRoot) {
    Write-Error @"
Refusing to start production AGM from the dirty Tearsheet Generator checkout:
  $here
Use the canonical runtime:
  C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main\reboot_mp_ts.bat
Configured via: C:\Coding Projects\Manager\tearsheet_fleet_runtime.json
"@
    exit 1
}

function Import-BatchEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content -LiteralPath $Path | ForEach-Object {
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
$env:MP_TS_PRODUCTION = '1'

Set-Location (Join-Path $PSScriptRoot 'Momentum Pacer')
$python = Join-Path $PSScriptRoot '.venv310\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'Momentum Pacer\mp_ts.py')
