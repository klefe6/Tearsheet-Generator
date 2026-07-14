$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'

$dirtyRoot = [System.IO.Path]::GetFullPath('C:\Coding Projects\Tearsheet Generator')
$here = [System.IO.Path]::GetFullPath($PSScriptRoot)
if ($here -eq $dirtyRoot) {
    Write-Error "Refusing to start TCP staff from the dirty Tearsheet Generator checkout: $here"
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
$envFile = Join-Path $PSScriptRoot '.tcp_production.env'
if (Test-Path $envFile) { Import-BatchEnvFile $envFile }
$staffEnv = Join-Path $PSScriptRoot '.staff.env'
if (-not (Test-Path $staffEnv)) {
    $staffEnv = 'C:\Coding Projects\Tearsheet Generator\.staff.env'
}
Import-BatchEnvFile $staffEnv

# Staff/admin runtime — forced AFTER env imports so .tcp_production.env's
# TCP_V2_BIND_PORT=8302 (and anything else) cannot override the staff port.
# State/auth config still comes from .tcp_production.env, so the staff admin
# edits the real TCP state (state writes are lock-protected, multi-process safe).
# Expose publicly ONLY via a Cloudflare tunnel hostname behind Cloudflare Access.
$env:TEARSHEET_MODE = 'staff'
$env:TCP_V2_BIND_PORT = '8322'

$python = Join-Path $PSScriptRoot '.venv310\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'tcp_ts_v2.py')
