<#
.SYNOPSIS
  Single-table migration readiness report for GitHub → VPS tearsheet apps.
#>
param(
    [string]$RepoRoot = '',
    [string]$TargetRoot = 'C:\H&C'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Deploy-HCAppCore.ps1')

if (-not $RepoRoot) {
    $RepoRoot = Get-HCRepoRoot -StartDir $PSScriptRoot
}

$manifestDir = Join-Path $RepoRoot 'deployment\windows-vps\manifests'
$apps = @('tkp', 'tcp', 'agm', 'yq')

$rows = @()
foreach ($app in $apps) {
    $m = Get-HCAppManifest -App $app -ManifestDir $manifestDir
    $missing = @()
    foreach ($rel in $m.source_files) {
        $src = Join-Path $RepoRoot ($rel -replace '/', '\')
        if (-not (Test-Path $src)) { $missing += $rel }
    }
    $blockers = @()
    if ($missing.Count) { $blockers += "missing source: $($missing -join '; ')" }
    if ($app -eq 'yq' -and -not $m.health_endpoint) { $blockers += 'no /healthz endpoint' }
    if ($app -eq 'agm') { $blockers += 'tracked AGM balances CSV in Git — migrate data separately' }

    $ready = ($blockers.Count -eq 0 -or ($blockers.Count -eq 1 -and $blockers[0] -like 'no /healthz*'))
    $rows += [pscustomobject]@{
        App = $app
        SourcePath = $RepoRoot
        TargetPath = $m.target_app_directory
        Entrypoint = $m.entrypoint
        Port = $m.port
        Service = $m.service_name
        DataPath = ($m.persistent_data_paths | ForEach-Object { $_.vps_default }) -join '; '
        ConfigPath = ($m.config_env_files -join '; ')
        SecretsRequired = ($m.secret_variable_names -join ', ')
        ReadyForGitHubDeploy = if ($ready) { 'yes' } else { 'no' }
        Blocker = ($blockers -join ' | ')
    }
}

$rows | Format-Table -AutoSize
return $rows
