# Quick connectivity check - backend must already be running on :8091.
# Usage (from frontend/):  npm run smoke:check

$ErrorActionPreference = "Stop"

$frontendUrl = "http://127.0.0.1:5173"
$apiBase = "http://127.0.0.1:8091"

Write-Host "Checking backend $apiBase/health..."
$r = Invoke-WebRequest -Uri "$apiBase/health" -UseBasicParsing -TimeoutSec 5
if ($r.StatusCode -ne 200) { throw "backend health failed" }
Write-Host "  backend OK"

Write-Host "Checking frontend $frontendUrl (optional; start npm run dev first)..."
try {
    $f = Invoke-WebRequest -Uri $frontendUrl -UseBasicParsing -TimeoutSec 3
    if ($f.Content -notmatch "Glenn Daily Uploader") { throw "title missing" }
    Write-Host "  frontend OK"
} catch {
    Write-Host "  frontend not running (start with: npm run dev)" -ForegroundColor Yellow
}

Write-Host "Smoke check complete. For full API smoke run backend/scripts/smoke_api.ps1"
