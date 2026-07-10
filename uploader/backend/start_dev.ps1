# Start the Glenn Daily Uploader backend on the standard local dev port (8091).
# Usage (from backend/):  .\start_dev.ps1
# Fresh DB first:          python scripts/reset_local_db.py --confirm

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error "Missing .venv - run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}

$env:DATABASE_PATH = if ($env:DATABASE_PATH) { $env:DATABASE_PATH } else { "data/uploader_sandbox.db" }
Write-Host "Starting backend on http://127.0.0.1:8091 (DATABASE_PATH=$env:DATABASE_PATH)"
& $venvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8091
