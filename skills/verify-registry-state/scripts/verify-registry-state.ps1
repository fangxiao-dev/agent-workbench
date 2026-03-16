#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$SkillsRegistry = Join-Path $RepoRoot "registry\skills.md"
$SkillsLock = Join-Path $RepoRoot "registry\skills.lock.json"
$PluginsRegistry = Join-Path $RepoRoot "registry\plugins.md"
$AgentsLock = Join-Path $env:USERPROFILE ".agents\.skill-lock.json"
$ClaudeSettings = Join-Path $env:USERPROFILE ".claude\settings.json"
$ClaudeInstalledPlugins = Join-Path $env:USERPROFILE ".claude\plugins\installed_plugins.json"
$CodexConfig = Join-Path $env:USERPROFILE ".codex\config.toml"

function Get-JsonOrNull($path) {
    if (-not (Test-Path $path)) { return $null }
    return Get-Content $path -Raw | ConvertFrom-Json
}

function Test-SkillInstalled($entry, $agentsState) {
    $localPath = Join-Path $RepoRoot $entry.localPath
    if ($entry.localPath -and (Test-Path $localPath)) {
        return $true
    }

    if ($entry.host -eq ".agents" -and $agentsState -and $agentsState.skills) {
        return ($null -ne $agentsState.skills.PSObject.Properties[$entry.name])
    }

    return $false
}

function Test-PluginInstalled($name, $pluginHost, $settingsState, $installedPluginsState, $codexText) {
    if ($pluginHost -eq "Claude plugin") {
        $enabled = $false
        $installed = $false

        if ($settingsState -and $settingsState.enabledPlugins) {
            $enabled = [bool]$settingsState.enabledPlugins.PSObject.Properties[$name]
        }

        if ($installedPluginsState -and $installedPluginsState.plugins) {
            $installed = ($null -ne $installedPluginsState.plugins.PSObject.Properties[$name])
        }

        return ($enabled -and $installed)
    }

    if ($pluginHost -eq "Codex MCP server") {
        return ($codexText -match [regex]::Escape($name))
    }

    return $false
}

function Update-MarkdownTableStatus($path, $resolver) {
    $lines = Get-Content $path
    $statusIndex = $null
    $updated = foreach ($line in $lines) {
        if ($line -match '^\|') {
            $parts = $line.Split('|')
            if (-not $statusIndex) {
                $statusIndex = [Array]::IndexOf($parts, " 状态 ")
            }
            if ($parts.Length -ge 6 -and $parts[1].Trim() -notin @("Skill", "Plugin", "-------", "--------")) {
                $name = $parts[1].Trim()
                $assetHost = $parts[2].Trim()
                $status = & $resolver $name $assetHost
                if ($status -and $statusIndex -gt 0) {
                    $parts[$statusIndex] = " $status "
                    ($parts -join '|')
                    continue
                }
            }
        }
        $line
    }
    Set-Content -Path $path -Value $updated -Encoding UTF8
}

$skillsState = Get-JsonOrNull $SkillsLock
$agentsState = Get-JsonOrNull $AgentsLock
$settingsState = Get-JsonOrNull $ClaudeSettings
$installedPluginsState = Get-JsonOrNull $ClaudeInstalledPlugins
$codexText = if (Test-Path $CodexConfig) { Get-Content $CodexConfig -Raw } else { "" }

$skillsMap = @{}
if ($skillsState -and $skillsState.skills) {
    foreach ($entry in $skillsState.skills) {
        $skillsMap[$entry.name] = $entry
    }
}

Update-MarkdownTableStatus $SkillsRegistry {
    param($name, $assetHost)
    $entry = $skillsMap[$name]
    if (-not $entry) { return $null }
    if (Test-SkillInstalled $entry $agentsState) { return "✅ 已装" }
    return "⬜ 未装"
}

Update-MarkdownTableStatus $PluginsRegistry {
    param($name, $assetHost)
    if (Test-PluginInstalled $name $assetHost $settingsState $installedPluginsState $codexText) { return "✅ 已装" }
    return "⬜ 未装"
}

Write-Host "Registry 状态已刷新："
Write-Host "  - $SkillsRegistry"
Write-Host "  - $PluginsRegistry"




