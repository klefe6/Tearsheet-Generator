# Shared helpers for safe GitHub → VPS code deployment (no service restarts).
$ErrorActionPreference = 'Stop'

function Get-HCRepoRoot {
    param([string]$StartDir = $PSScriptRoot)
    $dir = Resolve-Path $StartDir
    while ($dir) {
        if (Test-Path (Join-Path $dir '.git')) {
            return $dir.Path
        }
        $parent = Split-Path $dir.Path -Parent
        if (-not $parent -or $parent -eq $dir.Path) { break }
        $dir = Resolve-Path $parent
    }
    throw "Could not locate repository root from $StartDir"
}

function Get-HCAppManifest {
    param(
        [Parameter(Mandatory)][string]$App,
        [Parameter(Mandatory)][string]$ManifestDir
    )
    $path = Join-Path $ManifestDir "$App.json"
    if (-not (Test-Path $path)) {
        throw "Missing manifest: $path"
    }
    return Get-Content $path -Raw | ConvertFrom-Json
}

function Test-HCPathExcluded {
    param(
        [string]$RelativePath,
        [string[]]$ExcludePatterns
    )
    $norm = $RelativePath -replace '\\', '/'
    foreach ($pat in $ExcludePatterns) {
        $rx = '^' + ($pat -replace '\.', '\.' -replace '\*', '.*' -replace '\?', '.') + '$'
        if ($norm -match $rx) { return $true }
        if ($pat.EndsWith('/') -and $norm.StartsWith($pat.TrimEnd('/'))) { return $true }
    }
    return $false
}

function Invoke-HCAppDeploy {
    param(
        [Parameter(Mandatory)][psobject]$Manifest,
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$TargetRoot,
        [bool]$WhatIf = $true,
        [bool]$AllowOverwriteData = $false
    )

    $appId = $Manifest.app
    $targetApp = if ($Manifest.target_app_directory) {
        $Manifest.target_app_directory
    } else {
        Join-Path $TargetRoot "apps\$appId"
    }
    if ($targetApp -notlike "$TargetRoot*") {
        throw "Refusing deploy: target_app_directory must be under TargetRoot ($TargetRoot)"
    }

    $missing = @()
    $planned = @()
    foreach ($rel in @($Manifest.source_files)) {
        $src = Join-Path $RepoRoot ($rel -replace '/', '\')
        if (-not (Test-Path $src)) {
            $missing += $rel
            continue
        }
        $exclude = @($Manifest.exclude_from_git_deploy)
        if (Test-HCPathExcluded -RelativePath $rel -ExcludePatterns $exclude) {
            throw "Source file $rel matches exclude_from_git_deploy; refuse to deploy sensitive artifact."
        }
        $sub = ''
        if ($Manifest.PSObject.Properties['source_repository_subpath'] -and $Manifest.source_repository_subpath) {
            $sub = ($Manifest.source_repository_subpath -replace '\\', '/').TrimEnd('/')
        }
        $normRel = $rel -replace '\\', '/'
        if ($sub -and $normRel.StartsWith("$sub/")) {
            $destRel = $normRel.Substring($sub.Length + 1)
        } elseif ($normRel.StartsWith('Momentum Pacer/')) {
            $destRel = $normRel
        } elseif ($normRel.StartsWith('assets/')) {
            $destRel = $normRel
        } else {
            $destRel = Split-Path $normRel -Leaf
        }
        $dest = Join-Path $targetApp ($destRel -replace '/', '\')
        $planned += [pscustomobject]@{ Action = 'Copy'; Source = $src; Destination = $dest }
    }

    if ($missing.Count -gt 0) {
        throw "Manifest validation failed for $($Manifest.app): missing source files: $($missing -join ', ')"
    }

    foreach ($row in $planned) {
        $destDir = Split-Path $row.Destination -Parent
        if ($WhatIf) {
            Write-Host ('[WhatIf] COPY ' + $row.Source + ' -> ' + $row.Destination)
        } else {
            if (-not (Test-Path $destDir)) {
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            }
            Copy-Item -Path $row.Source -Destination $row.Destination -Force
            Write-Host "COPY $($row.Source) -> $($row.Destination)"
        }
    }

    if (-not $AllowOverwriteData) {
        Write-Host '[OK] Persistent data paths were not touched (AllowOverwriteData=false).'
    }

    return [pscustomobject]@{
        App = $appId
        Target = $targetApp
        FileCount = $planned.Count
        WhatIf = $WhatIf
    }
}
