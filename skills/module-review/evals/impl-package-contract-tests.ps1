$ErrorActionPreference = 'Stop'

$skill = Join-Path $PSScriptRoot '..\SKILL.md'
if (-not (Test-Path $skill)) {
    throw 'Expected skills/module-review/SKILL.md to exist.'
}

$body = Get-Content -Raw $skill
function Require-Text {
    param([string]$Text, [string]$Needle)
    if (-not $Text.Contains($Needle)) {
        throw "Expected module-review contract text: $Needle"
    }
}

@(
    'Standards',
    'Spec',
    '两个 general-purpose subagent',
    'codebase-design',
    'deep module',
    'interface',
    'seam',
    'contract fidelity',
    'tickets',
    'dag',
    'state machine',
    'module boundary',
    'fixed point'
) | ForEach-Object { Require-Text $body $_ }

if ($body.Contains('third reviewer') -or $body.Contains('第三 reviewer')) {
    throw 'module-review must not introduce a third drift reviewer.'
}

$evals = Join-Path $PSScriptRoot 'evals.json'
if (-not (Test-Path $evals)) {
    throw 'Expected module-review evals.json to cover the Impl-Package trigger mapping.'
}

$parsed = Get-Content -Raw $evals | ConvertFrom-Json
if ($parsed.skill_name -ne 'module-review' -or $parsed.evals.Count -lt 4) {
    throw 'module-review evals must identify the skill and cover trigger, fixed-point, and dual-axis behavior.'
}

Write-Output 'module-review Impl-Package contract checks passed'
