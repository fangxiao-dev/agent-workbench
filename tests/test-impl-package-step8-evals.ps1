$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$sourceDraft = 'D:\CodeSpace\TaskManager\Dev-with-Track 体系讨论.md'
$designPath = Join-Path $repo 'docs\skill-design\2026-07-10-impl-package-system-design.md'

function Assert-Contains([string]$Text, [string]$Needle, [string]$Message) {
    if (-not $Text.Contains($Needle)) { throw "$Message Missing: $Needle" }
}

if (-not (Test-Path -LiteralPath $sourceDraft)) { throw "Source discussion draft is unavailable: $sourceDraft" }
$draft = Get-Content -Raw -LiteralPath $sourceDraft
Assert-Contains $draft '已由' 'Discussion draft replacement marker is missing.'
Assert-Contains $draft '2026-07-10-impl-package-system-design.md' 'Discussion draft does not point to the approved design.'

$evalPaths = @{
    'req-align' = 'skills\req-align\evals\evals.json'
    'to-tickets' = 'skills\to-tickets\evals\evals.json'
    'impl-planning' = 'skills\impl-planning\evals\evals.json'
    'create-task-dag' = 'skills\create-task-dag\evals\evals.json'
    'dev-with-track' = 'skills\dev-with-track\evals\evals.json'
    'module-review' = 'skills\module-review\evals\evals.json'
    'safety-review' = 'skills\safety-review\evals\evals.json'
}

$evals = @{}
foreach ($skill in $evalPaths.Keys) {
    $path = Join-Path $repo $evalPaths[$skill]
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing Step 8 eval file for ${skill}: $path" }
    $parsed = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    if ($parsed.skill_name -ne $skill) { throw "Wrong skill_name in $path" }
    if ($parsed.evals.Count -lt 1) { throw "No eval cases in $path" }
    $evals[$skill] = $parsed
}

function Find-Eval([object]$EvalFile, [string]$Id) {
    return @($EvalFile.evals | Where-Object { $_.id -eq $Id })[0]
}

$designBlocked = Find-Eval $evals['req-align'] '1'
Assert-Contains ($designBlocked.prompt + $designBlocked.expected_output + ($designBlocked.expectations -join "`n")) 'Design Gate' 'Requirement-alignment must evaluate the Design gate before spec.'
$thickSpec = Find-Eval $evals['req-align'] '2'
Assert-Contains ($thickSpec.prompt + $thickSpec.expected_output + ($thickSpec.expectations -join "`n")) 'Error Boundaries' 'Requirement-alignment must evaluate the thick spec contract.'

$ticketsOnlyPlan = Find-Eval $evals['impl-planning'] '1'
Assert-Contains ($ticketsOnlyPlan.prompt + $ticketsOnlyPlan.expected_output + ($ticketsOnlyPlan.expectations -join "`n")) 'tickets=true, dag=false' 'Planning eval must cover tickets-only composition.'
$onlyDagPlan = Find-Eval $evals['impl-planning'] '2'
Assert-Contains ($onlyDagPlan.prompt + $onlyDagPlan.expected_output + ($onlyDagPlan.expectations -join "`n")) 'tickets=false, dag=true' 'Planning eval must cover only-dag composition.'

$ticketsOnly = Find-Eval $evals['dev-with-track'] '1'
Assert-Contains ($ticketsOnly.prompt + $ticketsOnly.expected_output + ($ticketsOnly.expectations -join "`n")) 'tickets=true, dag=false' 'Dev-with-track eval ID 1 must cover tickets-only status ownership.'
$onlyDag = Find-Eval $evals['dev-with-track'] '2'
Assert-Contains ($onlyDag.prompt + $onlyDag.expected_output + ($onlyDag.expectations -join "`n")) 'tickets=false, dag=true' 'Dev-with-track eval ID 2 must cover only-dag status ownership.'
$both = Find-Eval $evals['dev-with-track'] '3'
Assert-Contains ($both.prompt + $both.expected_output + ($both.expectations -join "`n")) 'tickets=true, dag=true' 'Dev-with-track eval ID 3 must cover ticket plus DAG projection ownership.'
$readiness = Find-Eval $evals['dev-with-track'] '4'
Assert-Contains ($readiness.prompt + $readiness.expected_output + ($readiness.expectations -join "`n")) 'readiness' 'Dev-with-track eval ID 4 must cover deterministic readiness.'
$stage7 = Find-Eval $evals['dev-with-track'] '5'
Assert-Contains ($stage7.prompt + $stage7.expected_output + ($stage7.expectations -join "`n")) 'Stage 7' 'Dev-with-track eval ID 5 must cover complete Stage 7 closure.'

$ticketText = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\to-tickets\SKILL.md')
Assert-Contains $ticketText 'Publication Status: Draft' 'To-tickets must name Draft as publication status.'
if ($ticketText -match 'Status: Draft file') { throw 'To-tickets retains the ambiguous Status: Draft file wording.' }
$ticketCycle = Find-Eval $evals['to-tickets'] '3'
Assert-Contains ($ticketCycle.prompt + $ticketCycle.expected_output + ($ticketCycle.expectations -join "`n")) 'cyclic' 'To-tickets eval must preserve typed-edge cycle validation.'
$dagTraceability = Find-Eval $evals['create-task-dag'] '1'
Assert-Contains ($dagTraceability.prompt + $dagTraceability.expected_output + ($dagTraceability.expectations -join "`n")) 'contributes-to' 'Task-DAG eval must retain task-to-AC traceability.'
$specAxis = Find-Eval $evals['module-review'] '4'
Assert-Contains ($specAxis.prompt + $specAxis.expected_output + ($specAxis.expectations -join "`n")) 'seam drift' 'Module-review eval must keep seam drift on the Spec axis.'
Assert-Contains ($specAxis.prompt + $specAxis.expected_output + ($specAxis.expectations -join "`n")) 'no third drift reviewer' 'Module-review eval must preserve the two-reviewer topology.'
$safetyP0 = Find-Eval $evals['safety-review'] '1'
Assert-Contains ($safetyP0.prompt + $safetyP0.expected_output + ($safetyP0.expectations -join "`n")) 'idempotency' 'Safety-review eval must retain the external-mutation P0 guard.'

$activeRoots = @(
    'skills\req-align', 'skills\to-tickets', 'skills\impl-planning',
    'skills\create-task-dag', 'skills\dev-with-track', 'skills\module-review', 'skills\safety-review'
)
foreach ($relativeRoot in $activeRoots) {
    $matches = Get-ChildItem -Path (Join-Path $repo $relativeRoot) -Recurse -File |
        Select-String -SimpleMatch -Pattern 'to-issues'
    if ($matches) { throw "Active Impl-Package skill retains to-issues: $($matches[0].Path):$($matches[0].LineNumber)" }
}

Write-Output 'Step 8 Impl-Package eval contract checks passed.'
