# Requires PowerShell 5.1+
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ActiveSkillPath = Join-Path $RepoRoot "skills\orchestrator"
$RetiredSkillPath = Join-Path $RepoRoot "skills-deprecated\orchestrator"
$HistoricalSkillPath = Join-Path $RetiredSkillPath "SKILL.md"
$HandoffEvalPath = Join-Path $RepoRoot "skills\eval-auto-handoff-by-session-hist\evals\evals.json"
$HandoffSkillPath = Join-Path $RepoRoot "skills\eval-auto-handoff-by-session-hist\SKILL.md"

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

Assert-True (-not (Test-Path -LiteralPath $ActiveSkillPath)) "Active skills directory must not expose orchestrator."
Assert-True (Test-Path -LiteralPath $HistoricalSkillPath) "Retired orchestrator history must remain available."

$historicalSkill = Get-Content -LiteralPath $HistoricalSkillPath -Raw
Assert-True ($historicalSkill -match "(?m)^name:\s*orchestrator\s*$") "Retired history must preserve the orchestrator skill definition."

@($HandoffSkillPath, $HandoffEvalPath) | ForEach-Object {
    $content = Get-Content -LiteralPath $_ -Raw
    Assert-True ($content -notmatch "(?i)\borchestrator\b") "Active handoff evaluation must not route to retired orchestrator: $_"
}

Write-Host "[OK] Retired orchestrator is preserved but no longer active."
