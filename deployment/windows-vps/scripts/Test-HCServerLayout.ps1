<#
.SYNOPSIS
    Validate that a directory tree matches the canonical H&C VPS layout.

.DESCRIPTION
    Read-only validator. Does not create, modify, or delete anything.

    Intended future invocation on the VPS:
        .\Test-HCServerLayout.ps1 -Root "C:\HC"

.PARAMETER Root
    Root path to validate (e.g. C:\HC).

.OUTPUTS
    Exit code 0 when valid; 1 when required paths are missing.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Root
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-HCRequiredRelativePaths {
    @(
        'apps\tkp',
        'apps\tcp',
        'apps\agm',
        'apps\yq',
        'apps\dashboard',
        'apps\shared',
        'data\tkp',
        'data\tcp',
        'data\agm',
        'data\yq',
        'config',
        'secrets',
        'logs\tkp',
        'logs\tcp',
        'logs\agm',
        'logs\yq',
        'logs\dashboard',
        'logs\ingest',
        'backups\tkp',
        'backups\tcp',
        'backups\agm',
        'backups\yq',
        'website',
        'deployment'
    )
}

$resolvedRoot = [System.IO.Path]::GetFullPath($Root)
$missing = @()

if (-not (Test-Path -LiteralPath $resolvedRoot)) {
    Write-Error "Root does not exist: $resolvedRoot"
    exit 1
}

foreach ($relative in (Get-HCRequiredRelativePaths)) {
    $target = Join-Path $resolvedRoot $relative
    if (-not (Test-Path -LiteralPath $target)) {
        $missing += $relative
    }
}

if ($missing.Count -gt 0) {
    Write-Host "INVALID: missing $($missing.Count) required path(s) under $resolvedRoot"
    foreach ($path in $missing) {
        Write-Host "  - $path"
    }
    exit 1
}

Write-Host "VALID: H&C layout complete under $resolvedRoot"
exit 0
