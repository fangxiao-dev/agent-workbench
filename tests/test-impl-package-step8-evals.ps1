$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$sourceDraft = 'D:\CodeSpace\TaskManager\Dev-with-Track 体系讨论.md'

function Assert-Contains([string]$Text, [string]$Needle, [string]$Message) {
    if (-not $Text.Contains($Needle)) { throw "$Message Missing: $Needle" }
}

function Assert-NotContains([string]$Text, [string]$Needle, [string]$Message) {
    if ($Text.Contains($Needle)) { throw "$Message Unexpected: $Needle" }
}

function Find-Eval([object]$EvalFile, [int]$Id) {
    $match = @($EvalFile.evals | Where-Object { [int]$_.id -eq $Id })
    if ($match.Count -ne 1) { throw "Expected exactly one eval id $Id" }
    return $match[0]
}

function Eval-Text([object]$Eval) {
    return $Eval.prompt + "`n" + $Eval.expected_output + "`n" + ($Eval.expectations -join "`n")
}

if (-not (Test-Path -LiteralPath $sourceDraft)) { throw "Source discussion draft is unavailable: $sourceDraft" }
$draft = Get-Content -Raw -LiteralPath $sourceDraft
Assert-Contains $draft '已由' 'Discussion draft replacement marker is missing.'
Assert-Contains $draft 'impl-package-system-design.md' 'Discussion draft does not point to the approved design.'

$evalPaths = @{
    'req-align' = 'skills\impl-package\req-align\evals\evals.json'
    'to-tickets' = 'skills\impl-package\to-tickets\evals\evals.json'
    'impl-planning' = 'skills\impl-package\impl-planning\evals\evals.json'
    'create-task-dag' = 'skills\impl-package\create-task-dag\evals\evals.json'
    'dev-with-track' = 'skills\impl-package\dev-with-track\evals\evals.json'
    'module-review' = 'skills\impl-package\reviews\module-review\evals\evals.json'
    'safety-review' = 'skills\impl-package\reviews\safety-review\evals\evals.json'
}

$evals = @{}
foreach ($skill in $evalPaths.Keys) {
    $path = Join-Path $repo $evalPaths[$skill]
    $parsed = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    if ($parsed.skill_name -ne $skill -or $parsed.evals.Count -lt 1) { throw "Invalid eval file: $path" }
    $evals[$skill] = $parsed
}

Assert-Contains (Eval-Text (Find-Eval $evals['req-align'] 4)) 'implementation-only' 'Req-align drift eval'
Assert-Contains (Eval-Text (Find-Eval $evals['req-align'] 4)) 'Design then Spec' 'Req-align design drift eval'

$simplePatch = Eval-Text (Find-Eval $evals['impl-planning'] 4)
Assert-Contains $simplePatch 'tickets=false, dag=false' 'Simple patch composition eval'
Assert-Contains $simplePatch 'Planned Verification' 'Simple patch planned verification eval'
Assert-Contains $simplePatch 'Execution Record' 'Simple patch execution record eval'
Assert-Contains $simplePatch 'no task checklist' 'Simple patch no-checklist eval'
$dagPatch = Eval-Text (Find-Eval $evals['impl-planning'] 5)
Assert-Contains $dagPatch 'tickets=false, dag=true' 'Patch DAG composition eval'
Assert-NotContains $dagPatch 'Patch execution topology' 'Retired patch topology eval'

$ticketDraft = Eval-Text (Find-Eval $evals['to-tickets'] 1)
Assert-Contains $ticketDraft 'current attempt plan' 'To-tickets plan composition source'
$ticketMismatch = Eval-Text (Find-Eval $evals['to-tickets'] 5)
Assert-Contains $ticketMismatch 'impl-planning' 'To-tickets composition mismatch routing'
Assert-Contains $ticketMismatch 'without rerunning the Spec gate solely for Composition' 'To-tickets must not re-gate composition-only changes'
Assert-NotContains $ticketMismatch 'Routes to req-align' 'To-tickets composition-only mismatch must not route to req-align'
$ticketAttemptBoundary = Eval-Text (Find-Eval $evals['to-tickets'] 6)
Assert-Contains $ticketAttemptBoundary 'same Attempt ID' 'To-tickets must reject historical-attempt blockers'

$dagInput = Eval-Text (Find-Eval $evals['create-task-dag'] 1)
Assert-Contains $dagInput 'current attempt plan' 'Task-DAG current-attempt input'
Assert-Contains $dagInput 'contributes-to' 'Task-DAG AC traceability'
$dagPersistence = Eval-Text (Find-Eval $evals['create-task-dag'] 7)
Assert-Contains $dagPersistence 'requires dag.md or a patch DAG' 'Task-DAG persistence contract'
$noDagRoute = Eval-Text (Find-Eval $evals['create-task-dag'] 14)
Assert-Contains $noDagRoute 'tickets=false, dag=false' 'Task-DAG no-DAG patch rejection'
Assert-Contains $noDagRoute 'no task checklist' 'Task-DAG no-checklist patch behavior'
$patchDagRoute = Eval-Text (Find-Eval $evals['create-task-dag'] 15)
Assert-Contains $patchDagRoute 'tickets=false, dag=true' 'Task-DAG patch DAG acceptance'

$blockedPass = Eval-Text (Find-Eval $evals['dev-with-track'] 9)
Assert-Contains $blockedPass 'Supersedes' 'Append-only blocked-to-pass gate eval'
Assert-Contains $blockedPass 'old entry' 'Append-only old-entry preservation'
$revisionProof = Eval-Text (Find-Eval $evals['dev-with-track'] 10)
Assert-Contains $revisionProof 'S1' 'Gate revision binding source'
Assert-Contains $revisionProof 'S2' 'Gate revision binding target'
$policyBoundary = Eval-Text (Find-Eval $evals['dev-with-track'] 11)
Assert-Contains $policyBoundary 'policy' 'Verification policy reference eval'
Assert-Contains $policyBoundary 'gate' 'Gate summary boundary eval'

$specTemplate = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\req-align\assets\templates\spec.md')
Assert-Contains $specTemplate 'Design Revision: D<n>' 'Spec must resolve lightweight Design revision.'
Assert-Contains $specTemplate 'Spec Revision: S<n>' 'Spec revision header.'
Assert-NotContains $specTemplate 'Composition:' 'Spec must not own Composition.'
Assert-NotContains $specTemplate 'Status: Draft | Spec Gate Passed | Spec Gate Blocked | Superseded' 'Current spec SoT must not be superseded as a whole file.'
$designTemplate = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\req-align\assets\templates\design.md')
Assert-Contains $designTemplate 'current design choices and rationale SoT' 'Design must be current SoT.'
Assert-NotContains $designTemplate 'point-in-time research and decision record' 'Design must not retain event-only identity.'

$planTemplate = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\impl-planning\assets\templates\plan.md')
Assert-Contains $planTemplate '## Planned Verification' 'Plan verification selection.'
Assert-Contains $planTemplate '## Execution Record' 'Plan execution evidence.'
Assert-NotContains $planTemplate 'Executable Checklist' 'Plan must not contain task checklist.'

$gateTemplate = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\dev-with-track\assets\templates\gate.md')
Assert-Contains $gateTemplate '# Gate Ledger' 'Single gate ledger.'
Assert-Contains $gateTemplate 'Supersedes:' 'Gate supersession chain.'
Assert-Contains $gateTemplate 'Evidence:' 'Gate execution-record link.'
Assert-Contains $gateTemplate '### Durable Deltas' 'Gate durable-delta capture.'
Assert-NotContains $gateTemplate 'Verification checklist' 'Gate must not copy full verification checklist.'
$progressTemplate = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\dev-with-track\assets\templates\progress.md')
Assert-Contains $progressTemplate 'Kind：[attempt / task / ticket]' 'Progress must represent a no-DAG attempt recovery unit.'
Assert-Contains $progressTemplate 'tasks/<attempt-id>-progress.md' 'Attempt progress path must be canonical.'

$dagSkill = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\create-task-dag\SKILL.md')
Assert-Contains $dagSkill '必须持久化为当前 attempt' 'Impl-Package DAG must be durable.'
Assert-NotContains $dagSkill '持久化始终可选' 'Impl-Package DAG persistence cannot be optional.'
Assert-Contains $dagSkill 'Composition 未决，或当前 plan Composition 与现有 artifact 不一致：路由' 'Composition mismatch route must be explicit.'
Assert-Contains $dagSkill '`impl-planning` 升级 P revision' 'Composition mismatch must route to impl-planning.'

$safetySkill = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\reviews\safety-review\SKILL.md')
Assert-Contains $safetySkill 'git rev-parse <comparison-ref>^{commit}' 'Safety base ref must resolve to a commit SHA.'
Assert-Contains $safetySkill 'git diff <base-sha>...<head-sha>' 'Safety diff must use immutable SHAs.'
$pinnedSafety = Eval-Text (Find-Eval $evals['safety-review'] 7)
Assert-Contains $pinnedSafety 'immutable commit SHAs' 'Safety eval must pin movable refs.'

$specAxis = Eval-Text (Find-Eval $evals['module-review'] 4)
Assert-Contains $specAxis 'seam drift' 'Module-review Spec axis'
Assert-Contains $specAxis 'no third drift reviewer' 'Module-review reviewer topology'
$safetyP0 = Eval-Text (Find-Eval $evals['safety-review'] 1)
Assert-Contains $safetyP0 'idempotency' 'Safety-review P0 guard'

$implEntry = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\SKILL.md')
$compositionContract = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\references\impl-package-composition-contract.md')
$systemDesign = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\references\impl-package-system-design.md')
$backfillDesign = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\references\evergreen-module-spec-and-backfill-design.md')
$devWithTrack = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\dev-with-track\SKILL.md')
$introHtml = Get-Content -Raw -LiteralPath (Join-Path $repo 'skills\impl-package\assets\impl-package-intro.html')
foreach ($surface in @($implEntry, $compositionContract, $systemDesign, $backfillDesign, $devWithTrack, $introHtml)) {
    Assert-Contains $surface '不阻塞' 'Backfill must be explicitly non-blocking across every current guidance surface.'
}
Assert-Contains $compositionContract 'terminal gate entry 写入前必须完成 Stage 7 durable-delta capture' 'Composition contract must keep capture inside the terminal gate.'
Assert-Contains $compositionContract '提示本身不构成 report/apply 授权' 'Composition contract must separate prompting from authorization.'
Assert-Contains $backfillDesign '## 当前稳态用法' 'Backfill design must lead with current steady-state usage.'
Assert-Contains $backfillDesign '不替 terminal gate 履行 Stage 7 capture' 'Backfill cannot replace gate capture.'
Assert-Contains $devWithTrack '另以非阻塞 follow-up 提示可选 backfill' 'Execution owner must report optional backfill without reopening the gate.'
Assert-Contains $introHtml '第二部分 · 6 步主流程' 'Human intro must present a six-step main flow.'
Assert-Contains $introHtml 'Gate 后可选维护:提示 Backfill,但不自动执行' 'Human intro must place backfill outside the numbered flow.'
Assert-NotContains $introHtml '开发 6+1' 'Human intro must not retain the obsolete 6+1 model.'
Assert-NotContains $introHtml '+1 回刷交接' 'Human intro must not present backfill as a seventh step.'

$activeRoots = @('skills\impl-package\req-align', 'skills\impl-package\to-tickets', 'skills\impl-package\impl-planning', 'skills\impl-package\create-task-dag', 'skills\impl-package\dev-with-track', 'skills\impl-package\reviews\module-review', 'skills\impl-package\reviews\safety-review')
foreach ($relativeRoot in $activeRoots) {
    $matches = Get-ChildItem -Path (Join-Path $repo $relativeRoot) -Recurse -File | Select-String -SimpleMatch -Pattern 'to-issues'
    if ($matches) { throw "Active Impl-Package skill retains to-issues: $($matches[0].Path):$($matches[0].LineNumber)" }
}

Write-Output 'Step 8 Impl-Package lifecycle eval contract checks passed.'
