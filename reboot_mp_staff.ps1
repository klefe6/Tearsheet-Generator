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
Import-BatchEnvFile (Join-Path $PSScriptRoot '.staff.env')

# Staff/admin runtime — forced AFTER env imports so no env file can override.
# MP_TS_PRODUCTION=1 keeps debug/reloader off (same as the client launcher).
# Expose publicly ONLY via a Cloudflare tunnel hostname behind Cloudflare Access.
$env:MP_TS_PRODUCTION = '1'
$env:TEARSHEET_MODE = 'staff'
$env:AGM_BIND_PORT = '8324'

# Match reboot_mp_ts.bat: run from the Momentum Pacer folder.
Set-Location (Join-Path $PSScriptRoot 'Momentum Pacer')
$python = Join-Path $PSScriptRoot '.venv310\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'Momentum Pacer\mp_ts.py')
