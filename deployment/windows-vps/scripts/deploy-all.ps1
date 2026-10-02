<#
.SYNOPSIS
  Deploy shared + all tearsheet apps (source only). Never restarts services.
#>
[CmdletBinding()]
param(
    [string]$TargetRoot = 'C:\HC',
    [switch]$ConfirmDeploy,
    [switch]$AllowOverwriteData
)

$ErrorActionPreference = 'Stop'
$apps = @('shared', 'tkp', 'tcp', 'agm', 'yq')
foreach ($app in $apps) {
    Write-Host "=== $app ==="
    & (Join-Path $PSScriptRoot 'deploy-app.ps1') -App $app -TargetRoot $TargetRoot -ConfirmDeploy:$ConfirmDeploy -AllowOverwriteData:$AllowOverwriteData
}
