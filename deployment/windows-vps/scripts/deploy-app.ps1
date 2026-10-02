<#
.SYNOPSIS
  Copy application SOURCE from this repository to a VPS-style layout (default C:\HC\apps).

.SAFETY
  - Defaults to -WhatIf (dry run). Pass -ConfirmDeploy to write files.
  - Never copies secrets, .env, or financial state (manifest exclude list).
  - Does not restart Windows services or NSSM jobs.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory)][ValidateSet('tkp', 'tcp', 'agm', 'yq', 'shared')][string]$App,
    [string]$TargetRoot = 'C:\HC',
    [switch]$ConfirmDeploy,
    [switch]$AllowOverwriteData
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'Deploy-HCAppCore.ps1')

$repoRoot = Get-HCRepoRoot -StartDir $PSScriptRoot
$manifestDir = Join-Path $repoRoot 'deployment\windows-vps\manifests'
$manifest = Get-HCAppManifest -App $App -ManifestDir $manifestDir

$whatIf = -not $ConfirmDeploy
if ($whatIf) {
    Write-Host "SAFE MODE: dry run only. Pass -ConfirmDeploy to copy files to $TargetRoot"
}

if ($ConfirmDeploy -and $TargetRoot -eq 'C:\HC' -and $env:COMPUTERNAME -notmatch 'OVH|VPS|HC-') {
    Write-Warning "ConfirmDeploy targets $TargetRoot on host $($env:COMPUTERNAME). Ensure this is intentional."
}

$result = Invoke-HCAppDeploy -Manifest $manifest -RepoRoot $repoRoot -TargetRoot $TargetRoot -WhatIf:$whatIf -AllowOverwriteData:$AllowOverwriteData.IsPresent
Write-Host "Deploy summary: app=$($result.App) files=$($result.FileCount) whatIf=$($result.WhatIf) target=$($result.Target)"
