# Requires PowerShell 5.1+
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ScriptPath = Join-Path $RepoRoot "scripts\list-visible-skills.ps1"

function New-TestWorkspace {
    $root = Join-Path ([System.IO.Path]::GetTempPath()) ("agent-workbench-visible-skills-" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $root | Out-Null
    return $root
}

function Remove-TestWorkspace($path) {
    if ((Test-Path $path)) {
        Remove-Item -Path $path -Recurse -Force
    }
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Contains {
    param(
        [string]$Haystack,
        [string]$Needle,
        [string]$Message
    )

    if (-not $Haystack.Contains($Needle)) {
        throw $Message
    }
}

function New-TestSkill {
    param(
        [string]$Root,
        [string]$RelativePath,
        [string]$Name
    )

    $skillDir = Join-Path $Root $RelativePath
    New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
    $content = @"
---
name: $Name
description: Test skill.
---

# $Name
"@
    Set-Content -Path (Join-Path $skillDir "SKILL.md") -Value $content -NoNewline
}

function Test-JsonReportMergesSources {
    $workspace = New-TestWorkspace
    try {
        $claudeRoot = Join-Path $workspace "claude-skills"
        $codexRoot = Join-Path $workspace "codex-skills"
        $superpowersRoot = Join-Path $workspace "codex-superpowers"
        $agentsRoot = Join-Path $workspace "agents-skills"
        @($claudeRoot, $codexRoot, $superpowersRoot, $agentsRoot) | ForEach-Object {
            New-Item -ItemType Directory -Path $_ | Out-Null
        }

        New-TestSkill -Root $claudeRoot -RelativePath "local-only" -Name "local-only"
        New-TestSkill -Root $agentsRoot -RelativePath "shared-skill" -Name "shared-skill"
        New-TestSkill -Root $claudeRoot -RelativePath "shared-skill" -Name "shared-skill"
        New-TestSkill -Root $codexRoot -RelativePath "codex-local" -Name "codex-local"
        New-TestSkill -Root $superpowersRoot -RelativePath "brainstorming" -Name "brainstorming"
        New-TestSkill -Root $agentsRoot -RelativePath "find-skills" -Name "find-skills"
        New-TestSkill -Root $claudeRoot -RelativePath "feishu-skills\feishu-base" -Name "feishu-base"
        New-Item -ItemType Directory -Path (Join-Path $claudeRoot "empty-bundle") | Out-Null

        $json = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ScriptPath `
            -ClaudeSkillsRoot $claudeRoot `
            -CodexSkillsRoot $codexRoot `
            -CodexSuperpowersRoot $superpowersRoot `
            -AgentsSkillsRoot $agentsRoot `
            -Format Json | Out-String

        $report = $json | ConvertFrom-Json
        $claude = $report.Hosts | Where-Object { $_.Host -eq "Claude" }
        $codex = $report.Hosts | Where-Object { $_.Host -eq "Codex" }

        Assert-True ($claude.MergedSkills.Name -contains "local-only") "Claude merged set should include local-only."
        Assert-True ($claude.MergedSkills.Name -contains "shared-skill") "Claude merged set should include shared-skill."
        Assert-True ($claude.MergedSkills.Name -contains "feishu-base") "Claude merged set should include bundled skill by frontmatter name."
        Assert-True (-not ($claude.MergedSkills.Name -contains "feishu-skills")) "Bundle root without SKILL.md should not be listed."
        $shared = $claude.MergedSkills | Where-Object { $_.Name -eq "shared-skill" }
        Assert-True ($shared.DuplicateCount -eq 2) "shared-skill should show duplicate count 2."
        $bundled = $claude.MergedSkills | Where-Object { $_.Name -eq "feishu-base" }
        Assert-True ($bundled.Sources[0].RelativePath -eq "feishu-skills/feishu-base") "Bundled skill should retain relative path metadata."
        Assert-True ($codex.MergedSkills.Name -contains "brainstorming") "Codex merged set should include superpowers skill."
        Assert-True ($codex.MergedSkills.Name -contains "find-skills") "Codex merged set should include agents skill."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-TextReportLabelsSources {
    $workspace = New-TestWorkspace
    try {
        $claudeRoot = Join-Path $workspace "claude-skills"
        $codexRoot = Join-Path $workspace "codex-skills"
        $superpowersRoot = Join-Path $workspace "codex-superpowers"
        $agentsRoot = Join-Path $workspace "agents-skills"
        @($claudeRoot, $codexRoot, $superpowersRoot, $agentsRoot) | ForEach-Object {
            New-Item -ItemType Directory -Path $_ | Out-Null
        }

        New-TestSkill -Root $codexRoot -RelativePath "codex-local" -Name "codex-local"
        New-TestSkill -Root $superpowersRoot -RelativePath "brainstorming" -Name "brainstorming"

        $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ScriptPath `
            -ClaudeSkillsRoot $claudeRoot `
            -CodexSkillsRoot $codexRoot `
            -CodexSuperpowersRoot $superpowersRoot `
            -AgentsSkillsRoot $agentsRoot | Out-String

        Assert-Contains $output "Codex:" "Text report should include Codex header."
        Assert-Contains $output "superpowers:" "Text report should label superpowers source."
        Assert-Contains $output "brainstorming" "Text report should list brainstorming."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

$tests = @(
    @{ Name = "json report merges sources"; Action = { Test-JsonReportMergesSources } }
    @{ Name = "text report labels sources"; Action = { Test-TextReportLabelsSources } }
)

$failures = @()
foreach ($test in $tests) {
    try {
        & $test.Action
        Write-Host "[PASS] $($test.Name)"
    }
    catch {
        $failures += "$($test.Name): $($_.Exception.Message)"
        Write-Host "[FAIL] $($test.Name)"
        Write-Host $_.Exception.Message
    }
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Failures:"
    $failures | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host ""
Write-Host "[OK] All visible skills tests passed."
