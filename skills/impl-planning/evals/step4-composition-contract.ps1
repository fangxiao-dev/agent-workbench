$ErrorActionPreference = 'Stop'

$skillRoot = Split-Path -Parent $PSScriptRoot
$skill = Get-Content -Raw (Join-Path $skillRoot 'SKILL.md')
$template = Get-Content -Raw (Join-Path $skillRoot 'assets/templates/plan.md')
$patching = Get-Content -Raw (Join-Path $skillRoot 'patching.md')
$rubric = Get-Content -Raw (Join-Path $skillRoot 'rubric.md')
$shared = Get-Content -Raw (Join-Path $skillRoot '..\impl-package\references\impl-package-composition-contract.md')

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
    @($shared, 'Append-only Gate Ledger', 'shared gate lifecycle')
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
