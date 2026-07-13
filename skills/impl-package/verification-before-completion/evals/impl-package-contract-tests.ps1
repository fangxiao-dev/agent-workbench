$ErrorActionPreference = 'Stop'

$skillDir = Split-Path -Parent $PSScriptRoot
$implRoot = Split-Path -Parent $skillDir
$repoRoot = Split-Path -Parent (Split-Path -Parent $implRoot)
$skill = Join-Path $skillDir 'SKILL.md'
$router = Join-Path $implRoot 'SKILL.md'
$executor = Join-Path $implRoot 'dev-with-track\SKILL.md'
$contract = Join-Path $implRoot 'references\impl-package-composition-contract.md'
$oldSkill = Join-Path $repoRoot 'skills\superpowers\verification-before-completion\SKILL.md'

foreach ($path in @($skill, $router, $executor, $contract)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Expected Impl-Package verification contract file: $path"
    }
}

if (Test-Path -LiteralPath $oldSkill) {
    throw 'verification-before-completion must live under skills/impl-package, not skills/superpowers.'
}

function Require-Text {
    param([string]$Text, [string]$Needle, [string]$Owner)
    if (-not $Text.Contains($Needle)) {
        throw "Expected $Owner contract text: $Needle"
    }
}

$skillBody = Get-Content -LiteralPath $skill -Raw
foreach ($needle in @('Impl-Package', 'not a DAG task', 'terminal `pass`', 'implemented, not verified', 'merge-ready', 'release-ready')) {
    Require-Text $skillBody $needle 'skill'
}

$routerBody = Get-Content -LiteralPath $router -Raw
Require-Text $routerBody 'verification-before-completion' 'router'

$executorBody = Get-Content -LiteralPath $executor -Raw
foreach ($needle in @('## Completion claim gate', 'terminal `pass`', '不机械重跑全部检查', '目标分支')) {
    Require-Text $executorBody $needle 'dev-with-track'
}

$contractBody = Get-Content -LiteralPath $contract -Raw
foreach ($needle in @('completion claim', '不进入 DAG', 'terminal pass entry 写入前')) {
    Require-Text $contractBody $needle 'composition contract'
}

$evals = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'evals.json') -Raw | ConvertFrom-Json
if ($evals.skill_name -ne 'verification-before-completion' -or $evals.evals.Count -lt 3) {
    throw 'Expected verification-before-completion evals to cover pass, stale evidence and post-merge claims.'
}

Write-Output 'verification-before-completion Impl-Package contract checks passed'
