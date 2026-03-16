#Requires -Version 5.1
param(
    [string]$ClaudeSkillsRoot,
    [string]$CodexSkillsRoot,
    [string]$CodexSuperpowersRoot,
    [string]$AgentsSkillsRoot,
    [ValidateSet("Text", "Json")]
    [string]$Format = "Text"
)

$ErrorActionPreference = "Stop"

if (-not $ClaudeSkillsRoot) {
    $ClaudeSkillsRoot = Join-Path $env:USERPROFILE ".claude\skills"
}
if (-not $CodexSkillsRoot) {
    $CodexSkillsRoot = Join-Path $env:USERPROFILE ".codex\skills"
}
if (-not $CodexSuperpowersRoot) {
    $CodexSuperpowersRoot = Join-Path $env:USERPROFILE ".codex\superpowers\skills"
}
if (-not $AgentsSkillsRoot) {
    $AgentsSkillsRoot = Join-Path $env:USERPROFILE ".agents\skills"
}

function Get-SkillEntries {
    param(
        [string]$RootPath,
        [string]$SourceLabel
    )

    $entries = @()
    if (-not (Test-Path $RootPath)) {
        return $entries
    }

    Get-ChildItem -Path $RootPath -Directory | ForEach-Object {
        $entries += [PSCustomObject]@{
            Name = $_.Name
            Path = $_.FullName
            Source = $SourceLabel
        }
    }

    return $entries
}

function Get-VisibleHostSkills {
    param(
        [string]$HostName,
        [object[]]$SourceSpecs
    )

    $sourceSummaries = @()
    $allEntries = @()

    foreach ($sourceSpec in $SourceSpecs) {
        $sourcePath = $sourceSpec.Path
        $sourceLabel = $sourceSpec.Label
        $entries = Get-SkillEntries -RootPath $sourcePath -SourceLabel $sourceLabel
        $sourceSummaries += [PSCustomObject]@{
            Label = $sourceLabel
            Path = $sourcePath
            Skills = @($entries.Name | Sort-Object)
        }
        $allEntries += $entries
    }

    $mergedSkills = @()
    $grouped = $allEntries | Group-Object -Property Name | Sort-Object Name
    foreach ($group in $grouped) {
        $mergedSkills += [PSCustomObject]@{
            Name = $group.Name
            Sources = @($group.Group | Sort-Object Source, Path | ForEach-Object {
                [PSCustomObject]@{
                    Source = $_.Source
                    Path = $_.Path
                }
            })
            DuplicateCount = $group.Count
        }
    }

    return [PSCustomObject]@{
        Host = $HostName
        Sources = $sourceSummaries
        MergedSkills = $mergedSkills
    }
}

function Write-HostReport {
    param(
        [object]$Report
    )

    Write-Output "$($Report.Host):"
    foreach ($source in $Report.Sources) {
        $names = if ($source.Skills.Count -gt 0) { $source.Skills -join ", " } else { "(none)" }
        Write-Output "  $($source.Label): $($source.Path)"
        Write-Output "    $names"
    }

    Write-Output "  Merged visible set:"
    if ($Report.MergedSkills.Count -eq 0) {
        Write-Output "    (none)"
        return
    }

    foreach ($skill in $Report.MergedSkills) {
        $sources = @($skill.Sources | ForEach-Object { "$($_.Source)=$($_.Path)" }) -join "; "
        if ($skill.DuplicateCount -gt 1) {
            Write-Output "    $($skill.Name) [duplicate x$($skill.DuplicateCount)] -> $sources"
        }
        else {
            Write-Output "    $($skill.Name) -> $sources"
        }
    }
}

$claudeReport = Get-VisibleHostSkills -HostName "Claude" -SourceSpecs @(
    @{ Label = "installed by workbench"; Path = $ClaudeSkillsRoot }
    @{ Label = "personal/global"; Path = $AgentsSkillsRoot }
)

$codexReport = Get-VisibleHostSkills -HostName "Codex" -SourceSpecs @(
    @{ Label = "installed by workbench"; Path = $CodexSkillsRoot }
    @{ Label = "superpowers"; Path = $CodexSuperpowersRoot }
    @{ Label = "personal/global"; Path = $AgentsSkillsRoot }
)

$report = [PSCustomObject]@{
    GeneratedAt = (Get-Date).ToString("s")
    Hosts = @($claudeReport, $codexReport)
}

if ($Format -eq "Json") {
    $report | ConvertTo-Json -Depth 10
    exit 0
}

foreach ($hostReport in $report.Hosts) {
    Write-HostReport -Report $hostReport
    Write-Output ""
}
