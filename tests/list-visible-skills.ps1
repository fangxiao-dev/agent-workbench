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

        New-Item -ItemType Directory -Path (Join-Path $claudeRoot "local-only") | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $agentsRoot "shared-skill") | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $claudeRoot "shared-skill") | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $codexRoot "codex-local") | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $superpowersRoot "brainstorming") | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $agentsRoot "find-skills") | Out-Null

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
        $shared = $claude.MergedSkills | Where-Object { $_.Name -eq "shared-skill" }
        Assert-True ($shared.DuplicateCount -eq 2) "shared-skill should show duplicate count 2."
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

        New-Item -ItemType Directory -Path (Join-Path $codexRoot "codex-local") | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $superpowersRoot "brainstorming") | Out-Null

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
