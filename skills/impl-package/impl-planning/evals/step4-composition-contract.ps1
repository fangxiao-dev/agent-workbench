$ErrorActionPreference = 'Stop'

$skillRoot = Split-Path -Parent $PSScriptRoot
$skill = Get-Content -Raw (Join-Path $skillRoot 'SKILL.md')
$template = Get-Content -Raw (Join-Path $skillRoot 'assets/templates/plan.md')
$patching = Get-Content -Raw (Join-Path $skillRoot 'patching.md')
$rubric = Get-Content -Raw (Join-Path $skillRoot 'rubric.md')
$shared = Get-Content -Raw (Join-Path $skillRoot '..\references\impl-package-composition-contract.md')
$gateTemplate = Get-Content -Raw (Join-Path $skillRoot '..\dev-with-track\assets\templates\gate.md')
$ticketTemplate = Get-Content -Raw (Join-Path $skillRoot '..\to-tickets\assets\templates\ticket.md')
$dagTemplate = Get-Content -Raw (Join-Path $skillRoot '..\dev-with-track\assets\templates\dag.md')
$devWithTrack = Get-Content -Raw (Join-Path $skillRoot '..\dev-with-track\SKILL.md')

function Assert-Contains([string]$Content, [string]$Needle, [string]$Label) {
    if (-not $Content.Contains($Needle)) { throw "Missing ${Label}: $Needle" }
}

function Assert-NotContains([string]$Content, [string]$Needle, [string]$Label) {
    if ($Content.Contains($Needle)) { throw "Unexpected ${Label}: $Needle" }
}

@(
    @($skill, 'Attempt ID', 'attempt identity'),
    @($skill, 'Composition 是当前 plan 的事实', 'plan-owned composition'),
    @($skill, 'Planned Verification', 'planned verification'),
    @($skill, 'Execution Record', 'execution record'),
    @($skill, '不在 plan 保存 task checklist', 'no task checklist rule'),
    @($skill, 'terminal gate verdict 后 plan 冻结', 'terminal freeze'),
    @($template, 'Design Revision: D<n>', 'design revision'),
    @($template, 'Spec Revision: S<n>', 'spec revision'),
    @($template, 'Plan Revision: P<n>', 'plan revision'),
    @($template, 'Composition: tickets=<true|false>, dag=<true|false>', 'composition declaration'),
    @($template, '## Planned Verification', 'planned verification section'),
    @($template, '## Execution Record', 'execution record section'),
    @($template, '### ER-<n>', 'stable execution-record anchor'),
    @($template, '## Plan Revision History', 'revision history'),
    @($patching, 'plan 独立声明 P1 与 Composition', 'patch-owned composition'),
    @($patching, '不建立 executable task checklist', 'no-DAG patch checklist prohibition'),
    @($patching, '不创建 patch-gate 文件', 'single gate ledger'),
    @($shared, 'Composition 的唯一事实源是当前 attempt plan', 'shared composition source'),
    @($shared, 'Append-only Gate Ledger', 'shared gate lifecycle'),
    @($shared, 'Revision-commit binding', 'revision-commit binding section'),
    @($shared, 'git log -1 --format=%H', 'git commit resolution command'),
    @($shared, 'NEEDS-REVALIDATION', 'ticket/DAG plan-revision drift rule'),
    @($shared, 'Module Knowledge Watermark', 'module knowledge watermark mechanism'),
    @($shared, '不只 pass', 'terminal-entry findings block covers fail/defer'),
    @($template, 'Module Knowledge Watermark', 'plan-side watermark field'),
    @($template, 'D<n> (commit <sha>)', 'plan design-revision commit binding'),
    @($gateTemplate, 'D<n> (commit <sha>)', 'gate design-revision commit binding'),
    @($gateTemplate, 'S<n> (commit <sha>)', 'gate spec-revision commit binding'),
    @($gateTemplate, 'P<n> (commit <sha>)', 'gate plan-revision commit binding'),
    @($ticketTemplate, 'Plan Revision', 'ticket plan-revision field'),
    @($dagTemplate, 'NEEDS-REVALIDATION', 'dag plan-revision drift note'),
    @($devWithTrack, 'terminal entry（pass/fail/defer', 'findings block covers all terminal verdicts'),
    @($devWithTrack, '重新计算', 'restore recomputes commit SHA for drift check')
) | ForEach-Object { Assert-Contains $_[0] $_[1] $_[2] }

@(
    'Patch execution topology',
    '## When tickets=false: Executable Checklist',
    '## When Patch topology=no-DAG: Patch Execution Checklist',
    '## Package Engineering Contract'
) | ForEach-Object { Assert-NotContains $template $_ 'retired plan shape' }

Assert-NotContains $skill 'Composition 由 spec' 'spec-owned composition'
Assert-NotContains $patching '原 package 的 `Composition:`' 'inherited patch composition'

Assert-Contains $rubric '每次 attempt 独立决定 Composition' 'rubric composition preference'
Assert-Contains $rubric '简单 no-DAG attempt 不建立 task checklist' 'rubric no-checklist preference'
Assert-Contains $rubric 'gate 只保存 newest-first append-only 判决摘要' 'rubric gate summary preference'

Write-Host 'Step 4 attempt-lifecycle contract checks passed.'
