<#
.SYNOPSIS
    Create the canonical Hughes & Company Windows VPS directory layout.

.DESCRIPTION
    Idempotent layout initializer for a future Windows Server VPS. Creates only
    empty directories — no application files, no production data, no services,
    no ACL changes, no software installation.

    Intended future invocation on the VPS:
        .\Initialize-HCServerLayout.ps1 -Root "C:\HC"

    Safe to run twice; existing directories are left untouched.

.PARAMETER Root
    Root path for the H&C layout (e.g. C:\HC).

.PARAMETER WhatIf
    Show what would be created without creating directories.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$Root
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-HCLayoutRelativePaths {
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
$relativePaths = Get-HCLayoutRelativePaths

Write-Verbose "H&C layout root: $resolvedRoot"
$created = 0
$skipped = 0

foreach ($relative in $relativePaths) {
    $target = Join-Path $resolvedRoot $relative
    if (Test-Path -LiteralPath $target) {
        $skipped++
        Write-Verbose "Exists: $target"
        continue
    }
    if ($PSCmdlet.ShouldProcess($target, 'Create directory')) {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
        $created++
        Write-Verbose "Created: $target"
    }
}

Write-Host "H&C layout initialization complete."
Write-Host "  Root:    $resolvedRoot"
Write-Host "  Created: $created"
Write-Host "  Skipped: $skipped (already present)"
