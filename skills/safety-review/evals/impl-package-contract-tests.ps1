$ErrorActionPreference = 'Stop'

$skill = Join-Path $PSScriptRoot '..\SKILL.md'
$evals = Join-Path $PSScriptRoot 'evals.json'

function Require-Text {
    param([string]$Text, [string]$Needle)
    if (-not $Text.Contains($Needle)) {
        throw "Expected safety-review contract text: $Needle"
    }
}

if (-not (Test-Path $skill)) {
    throw 'Expected skills/safety-review/SKILL.md to exist.'
}

$body = Get-Content -Raw $skill
@(
    'Data integrity',
    'Security boundary',
    'Concurrency',
    'External side effects',
    'Change map',
    'auth',
    'payment',
    'webhook',
    'migration',
    'external mutation',
    'Verification Gates',
    'Planned Verification',
    'Execution Record',
    'idempotency',
    'compensation',
    'permission',
    'rollback',
    'comparison ref'
    'git rev-parse'
    'base-sha'
    'head-sha'
) | ForEach-Object { Require-Text $body $_ }

if (-not (Test-Path $evals)) {
    throw 'Expected safety-review evals.json to exist.'
}

$parsed = Get-Content -Raw $evals | ConvertFrom-Json
if ($parsed.skill_name -ne 'safety-review' -or $parsed.evals.Count -lt 7) {
    throw 'Safety-review evals must identify the skill and cover all five review domains.'
}

Write-Output 'safety-review Impl-Package contract checks passed'
