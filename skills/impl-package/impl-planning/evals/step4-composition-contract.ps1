$ErrorActionPreference = 'Stop'

$skillRoot = Split-Path -Parent $PSScriptRoot
$skill = Get-Content -Raw (Join-Path $skillRoot 'SKILL.md')
$template = Get-Content -Raw (Join-Path $skillRoot 'assets/templates/plan.md')
$patching = Get-Content -Raw (Join-Path $skillRoot 'patching.md')
$rubric = Get-Content -Raw (Join-Path $skillRoot 'rubric.md')
$shared = Get-Content -Raw (Join-Path $skillRoot '..\references\impl-package-composition-contract.md')
$gateTemplate = Get-Content -Raw (Join-Path $skillRoot '..\dev-with-track\assets\templates\gate.md')
$bindingTemplate = Get-Content -Raw (Join-Path $skillRoot '..\assets\templates\revision-bindings.json')
$readinessTemplate = Get-Content -Raw (Join-Path $skillRoot '..\dev-with-track\assets\templates\manual-acceptance-readiness.md')
$ticketTemplate = Get-Content -Raw (Join-Path $skillRoot '..\to-tickets\assets\templates\ticket.md')
$dagTemplate = Get-Content -Raw (Join-Path $skillRoot '..\dev-with-track\assets\templates\dag.md')
$devWithTrack = Get-Content -Raw (Join-Path $skillRoot '..\dev-with-track\SKILL.md')
$reqAlign = Get-Content -Raw (Join-Path $skillRoot '..\req-align\SKILL.md')

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
    @($shared, 'Revision-blob binding', 'revision-blob binding section'),
    @($shared, 'git rev-parse HEAD:<package-relative-path>', 'git blob resolution command'),
    @($shared, 'NEEDS-REVALIDATION', 'ticket/DAG plan-revision drift rule'),
    @($shared, 'Module Knowledge Watermark', 'module knowledge watermark mechanism'),
    @($shared, '不只 pass', 'terminal-entry findings block covers fail/defer'),
    @($template, 'Module Knowledge Watermark', 'plan-side watermark field'),
    @($template, 'Binding Validation at Publication: Pending | Passed', 'human-readable plan publication conclusion'),
    @($gateTemplate, 'Revision set: D<n> / S<n> / P<n>', 'human-readable gate revision set'),
    @($gateTemplate, 'Binding validation: <passed | failed>', 'human-readable gate binding conclusion'),
    @($gateTemplate, 'Machine audit metadata:', 'hidden machine audit metadata'),
    @($bindingTemplate, '"current"', 'binding registry current selection'),
    @($bindingTemplate, '"purpose": "internal-machine-sidecar"', 'binding sidecar internal purpose'),
    @($bindingTemplate, '"ownerFacing": false', 'binding sidecar non-delivery marker'),
    @($bindingTemplate, '"blob"', 'binding registry blob field'),
    @($bindingTemplate, '"mode": "exact-blob"', 'exact artifact binding mode'),
    @($bindingTemplate, '"mode": "plan-contract-v1"', 'plan contract projection mode'),
    @($shared, 'Integrated, gate open', 'derived integration qualifier'),
    @($readinessTemplate, '### 必须', 'manual readiness required fields'),
    @($readinessTemplate, '### Optional', 'manual readiness optional fields'),
    @($ticketTemplate, 'Plan Revision', 'ticket plan-revision field'),
    @($dagTemplate, 'NEEDS-REVALIDATION', 'dag plan-revision drift note'),
    @($devWithTrack, 'terminal entry（pass/fail/defer', 'findings block covers all terminal verdicts'),
    @($devWithTrack, 'git rev-parse HEAD:<package-relative-path>', 'restore recomputes artifact blob'),
    @($devWithTrack, 'plan-contract-v1', 'restore permits append-only execution evidence without P drift'),
    @($devWithTrack, 'manual-acceptance-readiness.md', 'lightweight manual readiness handoff'),
    @($skill, '正文不得要求 owner 打开 JSON', 'planning handoff stays Markdown-first'),
    @($devWithTrack, '正文不得要求 owner 打开 JSON', 'execution handoff stays Markdown-first'),
    @($reqAlign, '正文不得要求 owner 打开 JSON', 'alignment handoff stays Markdown-first')
) | ForEach-Object { Assert-Contains $_[0] $_[1] $_[2] }

@(
    'Patch execution topology',
    '## When tickets=false: Executable Checklist',
    '## When Patch topology=no-DAG: Patch Execution Checklist',
    '## Package Engineering Contract'
) | ForEach-Object { Assert-NotContains $template $_ 'retired plan shape' }

Assert-NotContains $skill 'Composition 由 spec' 'spec-owned composition'
Assert-NotContains $patching '原 package 的 `Composition:`' 'inherited patch composition'
Assert-NotContains $template 'Status: Draft | Active | Frozen' 'manually maintained plan lifecycle'
Assert-NotContains $template '(commit <sha>)' 'self-referential plan commit binding'
Assert-NotContains $gateTemplate '(commit <sha>)' 'legacy gate commit binding'
Assert-NotContains $template 'Revision Bindings: [revision-bindings.json]' 'owner-facing JSON link in plan'
Assert-NotContains $gateTemplate '- Revision bindings: revision-bindings.json' 'owner-facing JSON field in gate'

Assert-Contains $rubric '每次 attempt 独立决定 Composition' 'rubric composition preference'
Assert-Contains $rubric '简单 no-DAG attempt 不建立 task checklist' 'rubric no-checklist preference'
Assert-Contains $rubric 'gate 只保存 newest-first append-only 判决摘要' 'rubric gate summary preference'

Write-Host 'Step 4 attempt-lifecycle contract checks passed.'
