$ErrorActionPreference = 'Stop'

$skillRoot = Split-Path -Parent $PSScriptRoot
$skill = Get-Content -Raw (Join-Path $skillRoot 'SKILL.md')
$template = Get-Content -Raw (Join-Path $skillRoot 'assets/templates/plan.md')
$patching = Get-Content -Raw (Join-Path $skillRoot 'patching.md')
$sharedContract = Get-Content -Raw (Join-Path $skillRoot '..\..\docs\skill-design\references\impl-package-composition-contract.md')
$repoRoot = Split-Path -Parent (Split-Path -Parent $skillRoot)

function Assert-Contains([string]$Content, [string]$Needle, [string]$Label) {
    if (-not $Content.Contains($Needle)) {
        throw "Missing ${Label}: $Needle"
    }
}

function Assert-NotContains([string]$Content, [string]$Needle, [string]$Label) {
    if ($Content.Contains($Needle)) {
        throw "Unexpected ${Label}: $Needle"
    }
}

function Assert-Matches([string]$Content, [string]$Pattern, [string]$Label) {
    if ($Content -notmatch $Pattern) {
        throw "Missing ${Label}: $Pattern"
    }
}

function Get-Section([string]$Content, [string]$StartHeading, [string]$NextHeading) {
    $start = $Content.IndexOf($StartHeading)
    if ($start -lt 0) {
        throw "Missing section start: $StartHeading"
    }
    $end = $Content.IndexOf($NextHeading, $start + $StartHeading.Length)
    if ($end -lt 0) {
        throw "Missing section end: $NextHeading"
    }
    return $Content.Substring($start, $end - $start)
}

Assert-Contains $skill 'Impl-Package' 'leading word'
Assert-Contains $skill 'impl-package-composition-contract.md' 'shared-contract reference'
Assert-Contains $skill 'plan → to-tickets draft → cross-check plan' 'required creation order'
Assert-Contains $skill '不得自行改写 `Composition:`' 'spec ownership boundary'
Assert-Contains $skill '受控 Composition 升级迁移' 'composition-upgrade workflow'
Assert-Contains $skill '每 ticket patch' 'per-ticket patch prohibition'
Assert-Contains $skill '计划修正只由本 skill 原地更新 `plan.md`' 'planning-only plan correction ownership'
Assert-Contains $skill '`dag.md` 修正路由 `create-task-dag`' 'DAG correction owner routing'
Assert-Contains $skill 'tracking 修正路由 `dev-with-track`' 'tracking correction owner routing'
Assert-Contains $skill '`tickets=true, dag=false` 时' 'tickets-only guard'
Assert-Contains $skill '不得调用 `create-task-dag`' 'tickets-only DAG prohibition'
Assert-Contains $skill '`tickets=true, dag=true` 时' 'ticketed-DAG guard'
Assert-Matches $skill '`tickets=false, dag=true`\s*时，plan 填写 Package Engineering Contract' 'only-DAG engineering-contract guard'
Assert-Contains $skill 'tickets-only 仍填写 Package Engineering Contract' 'tickets-only engineering-contract guard'
Assert-Contains $skill 'Seam ID、Contract owner、Acceptance owner、Affected targets' 'DAG seam-record fields'

Assert-Contains $template 'Composition: tickets=<true|false>, dag=<true|false>' 'composition declaration'
Assert-Contains $template '## When tickets=false: Executable Checklist' 'no-ticket plan branch'
Assert-Contains $template 'contributes-to: spec:AC-<n>' 'no-DAG task AC traceability'
Assert-Contains $template 'seam: none' 'no-DAG seam restriction'
Assert-Contains $template '## When tickets=true: Ticketed Plan Branches' 'ticketed plan branch'
Assert-Contains $template '## Seam Contracts' 'seam contract home'
Assert-Contains $template '## Composition Migration' 'migration record'
Assert-Contains $template 'Granularity：repo-local executable checklist | micro-step fallback | N/A — task decomposition outside plan' 'non-checklist granularity marker'
Assert-Contains $template 'create-task-dag 输入（唯一）：本 plan' 'no-ticket DAG input contract'
Assert-Contains $template 'create-task-dag 输入（唯一）：本 plan + 相关 approved tickets 子集' 'ticketed DAG input contract'
Assert-Contains $template '## When tickets=true, dag=false: Ticket-Only Acceptance' 'tickets-only branch'
Assert-Contains $template '## When tickets=true, dag=true: Ticketed DAG Handoff' 'ticketed-DAG branch'
Assert-Contains $template '## Package Engineering Contract' 'shared engineering-contract section'
Assert-Contains $template '### Cross-Slice / Execution Strategy' 'engineering strategy section'
Assert-Contains $template '### Seam Contracts' 'shared seam-contract section'
Assert-Contains $template '| Seam ID（或 none / N/A） | Contract owner |' 'seam contract-owner column'
Assert-Contains $template '<plan owner or named owner>' 'seam contract-owner identity placeholder'
Assert-Contains $template '### Migration / Rollback' 'shared rollback section'
Assert-Contains $template '### Verification Policy' 'shared verification section'
Assert-Contains $template '### Global Constraints' 'shared constraints section'

$generatedPlan = Join-Path $repoRoot 'docs\implementations\example\plan.md'
$templateLink = '../../skill-design/references/impl-package-composition-contract.md'
$resolvedTemplateLink = (Resolve-Path (Join-Path (Split-Path -Parent $generatedPlan) $templateLink)).Path
$resolvedSharedContract = (Resolve-Path (Join-Path $repoRoot 'docs\skill-design\references\impl-package-composition-contract.md')).Path
if ($resolvedTemplateLink -ne $resolvedSharedContract) {
    throw "Generated-plan shared-contract link does not resolve to the shared contract: $resolvedTemplateLink"
}
Assert-Contains $template $templateLink 'generated-plan shared-contract link'

$ticketBranch = $template.Substring($template.IndexOf('## When tickets=true: Ticketed Plan Branches'))
Assert-NotContains $ticketBranch '### T<n>:' 'task checklist in ticketed plan branch'
Assert-NotContains $ticketBranch '## Current Next' 'runtime next-state section in ticketed plan branch'
Assert-NotContains $ticketBranch '## Files To Modify Or Create' 'file-level implementation section in ticketed plan branch'

$ticketOnlyBranch = Get-Section $template '## When tickets=true, dag=false: Ticket-Only Acceptance' '## When tickets=true, dag=true: Ticketed DAG Handoff'
Assert-NotContains $ticketOnlyBranch 'create-task-dag' 'DAG invocation in tickets-only branch'
Assert-NotContains $ticketOnlyBranch 'dag.md' 'DAG artifact in tickets-only branch'
Assert-Contains $ticketOnlyBranch 'ticket 文件是 AC evidence 与验收状态的事实源' 'tickets-only fact source'
Assert-Contains $ticketOnlyBranch '填写上述 Package Engineering Contract' 'tickets-only engineering-contract handoff'
Assert-Contains $ticketOnlyBranch 'Seam: none | N/A' 'tickets-only seam restriction'

$ticketDagBranch = $template.Substring($template.IndexOf('## When tickets=true, dag=true: Ticketed DAG Handoff'))
Assert-Contains $ticketDagBranch 'create-task-dag 输入（唯一）：本 plan + 相关 approved tickets 子集' 'DAG handoff in ticketed-DAG branch'

$onlyDagBranch = Get-Section $template '## When tickets=false and dag=true: DAG Handoff' '## Package Engineering Contract'
Assert-Contains $onlyDagBranch '填写下方 Package Engineering Contract' 'only-DAG engineering-contract handoff'
Assert-Contains $onlyDagBranch 'execution owner 仅在 dag.md' 'only-DAG execution-owner boundary'

Assert-Contains $patching 'post-gate' 'post-gate lifecycle boundary'
Assert-Contains $patching 'to-tickets' 'ticket lifecycle cross-reference'
Assert-Contains $sharedContract 'Controlled composition upgrade' 'shared contract availability'

$rubric = Get-Content -Raw (Join-Path $skillRoot 'rubric.md')
Assert-Contains $rubric 'Contract owner' 'rubric seam contract-owner boundary'

Write-Host 'Step 4 composition-contract checks passed.'
