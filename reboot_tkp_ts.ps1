$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'

# Refuse production launch from the dirty Tearsheet Generator checkout.
$dirtyRoot = [System.IO.Path]::GetFullPath('C:\Coding Projects\Tearsheet Generator')
$here = [System.IO.Path]::GetFullPath($PSScriptRoot)
if ($here -eq $dirtyRoot) {
    Write-Error @"
Refusing to start production TKP from the dirty Tearsheet Generator checkout:
  $here
Use the canonical runtime:
  C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main\reboot_tkp_ts.bat
Configured via: C:\Coding Projects\Manager\tearsheet_fleet_runtime.json
"@
    exit 1
}

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
$envFile = Join-Path $PSScriptRoot '.tkp_production.env'
if (Test-Path $envFile) { Import-BatchEnvFile $envFile }

# Public client mode: Werkzeug debugger off (legacy mode enables debug=True).
$env:TEARSHEET_MODE = 'public'

$python = Join-Path $PSScriptRoot '.venv310\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'tkp_ts.py')
