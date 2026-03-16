#Requires -Version 5.1
param(
    [Parameter(Mandatory = $true)][string]$SkillName,
    [Parameter(Mandatory = $true)][string]$Package,
    [Parameter(Mandatory = $true)][string]$TargetDir,
    [string]$SourceType = "github",
    [string]$SourceUrl,
    [string]$InstallMethod = "npx skills add",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$TargetRoot = Join-Path $RepoRoot $TargetDir
$TargetPath = Join-Path $TargetRoot $SkillName
$RegistryMarkdown = Join-Path $RepoRoot "registry\third-party-skills.md"
$RegistryLock = Join-Path $RepoRoot "registry\skills.lock.json"

function Get-JsonOrNull($Path) {
    if (-not (Test-Path $Path)) { return $null }
    return Get-Content $Path -Raw | ConvertFrom-Json
}

function Resolve-InstalledSkillPath($Name) {
    $candidates = @(
        (Join-Path $RepoRoot ".claude\skills\$Name"),
        (Join-Path $env:USERPROFILE ".claude\skills\$Name"),
        (Join-Path $env:USERPROFILE ".agents\skills\$Name")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }
    throw "Installed skill '$Name' not found under .claude/skills or .agents/skills."
}

function Ensure-ParentDirectory($Path) {
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
}

function Copy-SkillDirectory($SourcePath, $DestinationPath, [bool]$Overwrite) {
    Ensure-ParentDirectory $DestinationPath
    if (Test-Path $DestinationPath) {
        if (-not $Overwrite) {
            throw "Target path already exists: $DestinationPath. Re-run with -Force to overwrite."
        }
        Remove-Item $DestinationPath -Recurse -Force
    }
    Copy-Item $SourcePath $DestinationPath -Recurse -Force
}

function Build-SourceUrl($Package) {
    if ($Package -match '^(?<owner>[^/]+)/(?<repo>[^@]+)@(?<skill>.+)$') {
        return "https://github.com/$($Matches.owner)/$($Matches.repo).git"
    }
    return $null
}

function Normalize-TargetDir($Value) {
    return (($Value -replace '[\\/]+$','').Replace('\','/'))
}

function Update-LockFile($LockPath, $Name, $Package, $TargetDir, $SourceType, $SourceUrl, $InstallMethod) {
    $lockState = Get-JsonOrNull $LockPath
    if (-not $lockState) {
        $lockState = [ordered]@{
            version = 1
            description = "Machine-readable metadata for third-party skills managed by this repository."
            skills = @()
        }
    }

    $source = if ($Package -match '^(?<owner>[^/]+)/(?<repo>[^@]+)@(?<skill>.+)$') {
        "$($Matches.owner)/$($Matches.repo)"
    } else {
        $Package
    }

    $normalizedTargetDir = Normalize-TargetDir $TargetDir
    $entry = [ordered]@{
        name = $Name
        host = "vendored"
        source = $source
        sourceType = $SourceType
        sourceUrl = $(if ($SourceUrl) { $SourceUrl } else { Build-SourceUrl $Package })
        upstreamPath = "skills/$Name/SKILL.md"
        localPath = "$normalizedTargetDir/$Name"
        installMethod = "vendored into this repository"
        installCommand = "$InstallMethod $Package -g -y"
        updateCommand = $null
        configSource = "registry/skills.lock.json"
        status = "installed"
        installedAt = (Get-Date).ToUniversalTime().ToString("o")
        lastUpdatedAt = (Get-Date).ToUniversalTime().ToString("o")
        managedBy = "registry/skills.lock.json"
        notes = "Vendored from a locally installed skill after search/recommendation via find-skills."
    }

    $skills = @($lockState.skills)
    $existing = $skills | Where-Object { $_.name -eq $Name } | Select-Object -First 1
    if ($existing) {
        foreach ($key in $entry.Keys) {
            $existing.$key = $entry[$key]
        }
    } else {
        $lockState.skills = $skills + @([pscustomobject]$entry)
    }

    $lockState | ConvertTo-Json -Depth 8 | Set-Content -Path $LockPath -Encoding UTF8
}

function Update-MarkdownRegistry($Path, $Name, $Source, $TargetDir) {
    $normalizedTargetDir = Normalize-TargetDir $TargetDir
    $row = "| $Name | vendored in this repo | ``$Source`` | ✅ 已装 | 已收录到 ``$normalizedTargetDir/$Name/``；上游元数据见 ``registry/skills.lock.json`` |"
    $lines = Get-Content $Path
    $output = New-Object System.Collections.Generic.List[string]
    $updated = $false

    foreach ($line in $lines) {
        if ($line -match "^\| $([regex]::Escape($Name)) \|") {
            $output.Add($row)
            $updated = $true
        } else {
            $output.Add($line)
        }
    }

    if (-not $updated) {
        $inserted = $false
        $newOutput = New-Object System.Collections.Generic.List[string]
        foreach ($line in $output) {
            $newOutput.Add($line)
            if (-not $inserted -and $line -eq "|-------|------|------|------|------|") {
                $newOutput.Add($row)
                $inserted = $true
            }
        }
        $output = $newOutput
    }

    Set-Content -Path $Path -Value $output -Encoding UTF8
}

$installedPath = Resolve-InstalledSkillPath $SkillName
Copy-SkillDirectory -SourcePath $installedPath -DestinationPath $TargetPath -Overwrite $Force.IsPresent

$source = if ($Package -match '^(?<owner>[^/]+)/(?<repo>[^@]+)@(?<skill>.+)$') {
    "$($Matches.owner)/$($Matches.repo)"
} else {
    $Package
}

Update-LockFile -LockPath $RegistryLock -Name $SkillName -Package $Package -TargetDir $TargetDir -SourceType $SourceType -SourceUrl $SourceUrl -InstallMethod $InstallMethod
Update-MarkdownRegistry -Path $RegistryMarkdown -Name $SkillName -Source $source -TargetDir $TargetDir

Write-Host "Imported third-party skill:"
Write-Host "  - Name: $SkillName"
Write-Host "  - Source: $installedPath"
Write-Host "  - Target: $TargetPath"
