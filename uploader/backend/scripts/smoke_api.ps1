# API-only smoke test for the Glenn Daily Uploader backend.
# Usage (from backend/):  .\scripts\smoke_api.ps1
# Optional:              .\scripts\smoke_api.ps1 -Port 8091

param(
    [int]$Port = 8091,
    [string]$BaseUrl = ""
)

$ErrorActionPreference = "Stop"
if (-not $BaseUrl) { $BaseUrl = "http://127.0.0.1:$Port" }

function Invoke-Smoke {
    param([string]$Label, [scriptblock]$Block)
    Write-Host "  $Label..." -NoNewline
    & $Block
    Write-Host " OK"
}

Write-Host "Glenn Uploader backend smoke (base=$BaseUrl)"

Invoke-Smoke "GET /health" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec 10
    if ($r.StatusCode -ne 200) { throw "status $($r.StatusCode)" }
}

Invoke-Smoke "GET /api/programs" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/api/programs" -UseBasicParsing -TimeoutSec 10
    if ($r.StatusCode -ne 200) { throw "status $($r.StatusCode)" }
}

$today = (Get-Date).ToString("yyyy-MM-dd")
$body = @{
    date = $today
    stonex_nlv = 100001
    plus500_nlv = 50001
    cash_transfer = 0
} | ConvertTo-Json

Invoke-Smoke "POST /api/rows/TKP" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/api/rows/TKP" -Method POST `
        -Body $body -ContentType "application/json" -UseBasicParsing -TimeoutSec 10
    if ($r.StatusCode -ne 200) { throw "status $($r.StatusCode)" }
}

Invoke-Smoke "GET /api/rows/TKP" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/api/rows/TKP?limit=1" -UseBasicParsing -TimeoutSec 10
    if ($r.StatusCode -ne 200) { throw "status $($r.StatusCode)" }
    if ($r.Content -notmatch $today) { throw "saved row not found in response" }
}

Invoke-Smoke "POST /api/export/all" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/api/export/all" -Method POST -UseBasicParsing -TimeoutSec 10
    if ($r.StatusCode -ne 200) { throw "status $($r.StatusCode)" }
    if ($r.Content -notmatch '"dry_run"') { throw "unexpected export response" }
}

Write-Host "All API smoke checks passed."
