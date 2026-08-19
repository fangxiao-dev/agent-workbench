/**
 * do-review-orchestrator — mechanical half of `do-review` (registry routing,
 * brief assembly, fail-closed aggregation, report rendering). The judgment
 * heuristics (Safety admission, finding acceptance/dedup/classification, Loop
 * clean, source-recheck conclusion) stay with the main session / do-review
 * skill; this module never invents rules.
 *
 * Loaded as a preset-local plugin (`name: ./do-review-orchestrator.mjs`);
 * registers one typed tool `impl_review_aggregate` so the model can run the
 * fail-closed aggregation mechanically instead of by hand.
 */

import { readFile } from 'node:fs/promises'
import { join } from 'node:path'

export const name = 'do-review-orchestrator'
export const inject = ['tools']

/* ── Pure: brief assembly (templates extracted from subagent-briefs.md) ──── */

function commonBlock(c) {
  return [
    'Review target:',
    `- Repo/worktree: ${c.repo ?? ''}`,
    `- Target revision or PR: ${c.target ?? ''}`,
    `- Resolved base SHA: ${c.baseSha ?? ''}`,
    `- Resolved head SHA: ${c.headSha ?? ''}`,
    `- Diff command/range: ${c.diffRange ?? ''}`,
    `- Included commits: ${c.commits ?? ''}`,
    `- Scope source / package roots: ${c.scope ?? ''}`,
    `- Mode: ${c.mode ?? ''}`,
    `- Review phase: ${c.phase ?? ''}`,
    `- Round: ${c.round ?? 1}`,
    `- Track label / reviewer role: ${c.trackLabel ?? ''}`,
    `- Assigned reviewer skill: ${c.skill ?? ''}`,
    `- Repository standards sources: ${c.standards ?? ''}`,
    `- Immutable contract sources: ${c.contractSources ?? ''}`,
    `- Spec discovery record / evidence gap: ${c.specDiscovery ?? ''}`,
    `- Out of scope: ${c.outOfScope ?? ''}`,
    `- User policy: ${c.userPolicy ?? ''}`,
    `- Safety applicability / evidence / coverage: ${c.safety ?? ''}`,
    `- Canonical ledger artifact (read-only): ${c.ledgerPath ?? ''}`,
    `- Review report artifact: ${c.reportPath ?? ''}`,
    '',
    'Known findings ledger:',
    c.priorLedger ?? 'none yet',
  ].join('\n')
}

const CLOSURE_BRIEF = `Use the assigned reviewer skill, but run closure verification only. The parent dispatches one fresh
independent reviewer for the whole named-finding set; do not split findings by source track or add a
separate Safety reviewer. For each assigned issue/finding: 1) read issue body and acceptance criteria;
2) inspect only code/tests needed to verify those criteria; 3) do not report unrelated new problems;
4) return PASS, FAIL, or UNCERTAIN. FAIL: quote the unsatisfied criterion, cite file:line, state the
minimal remaining work. UNCERTAIN: state exactly what evidence is missing.`

const ANTI_DUPLICATE = `The supplied artifact is the prior round's canonical ledger. Do not re-report those findings. Report a
related finding only if it breaks a different invariant; affects a different owner/release decision;
changes severity/classification; or gives narrower evidence that changes the fix. Otherwise mark it
duplicate/refinement and keep it short.`

const SOURCE_RECHECK = `Review only the supplied accepted finding and immutable design sources (Decision, Spec,
contract-design.md when present at the fixed head, directly referenced Ticket/cross-module authority).
Answer one question: do those sources uniquely determine the expected behavior for this finding?
If yes, cite exact sections (implementation may be corrected without changing the contract). If a
source is missing/ambiguous/conflicting, cite the exact gap and route to req-align before
implementation. If multiple product outcomes remain valid, state the owner decision required.
Return a concise conclusion with source citations.`

/** Build the full brief for one leaf dispatch. */
export function buildBrief({ reviewRun, phase, round = 1, priorLedger, extra = {} }) {
  const parts = [commonBlock({ ...reviewRun, phase, round, priorLedger })]
  if (phase === 'finding-closure') parts.push(CLOSURE_BRIEF)
  else if (round > 1) parts.push(ANTI_DUPLICATE)
  if (extra.trackCRecheck) parts.push(SOURCE_RECHECK)
  return parts.join('\n\n')
}

/* ── Pure: fail-closed aggregation ───────────────────────────────────────── */

/**
 * Fail-closed: any required FAIL → FAIL; else any required UNCERTAIN → UNCERTAIN;
 * all required PASS → PASS; Safety applicable but omitted from an explicit
 * terminal-final list → INCOMPLETE (non-terminal phases only record the omission).
 */
export function aggregateVerdicts({ tracks, safety = { applicable: false, selected: false }, phase = 'terminal-final' }) {
  const required = tracks.filter((track) => track.required)
  if (required.length === 0) return { overall: 'INCOMPLETE', reason: 'no required track' }
  if (required.some((track) => track.verdict === 'FAIL')) return { overall: 'FAIL', reason: 'required FAIL' }
  if (required.some((track) => track.verdict === 'UNCERTAIN')) return { overall: 'UNCERTAIN', reason: 'required UNCERTAIN' }
  if (required.some((track) => track.verdict !== 'PASS')) {
    return { overall: 'INCOMPLETE', reason: `missing verdict: ${required.filter((track) => track.verdict !== 'PASS').map((track) => track.label).join(', ')}` }
  }
  if (safety.applicable && !safety.selected && phase === 'terminal-final') {
    return { overall: 'INCOMPLETE', reason: 'omitted applicable Safety risk' }
  }
  return { overall: 'PASS', reason: 'all required PASS' }
}

/* ── Pure: report rendering (smallest matching template) ─────────────────── */

/** Render the report from output-templates.md's smallest matching template. */
export function renderReport({ reviewRun, tracks, aggregate, findings = [], lifecycle }) {
  if (reviewRun.phase === 'finding-closure') {
    return [
      '## Closure Verification Summary',
      '| Field | Value |',
      '| --- | --- |',
      '| Review phase | finding-closure |',
      `| Safety applicability / coverage | ${reviewRun.safetyText ?? ''} |`,
      '',
      '| Reviewer | Verdict | Coverage / note |',
      '| --- | --- | --- |',
      `| Independent closure reviewer | ${aggregate.overall} |  |`,
      '',
      '| Issue | Verdict | Disposition | Reason / evidence | Suggested action |',
      '| --- | --- | --- | --- | --- |',
      ...findings.map((finding) => `| ${finding.title ?? ''} | ${finding.verdict ?? ''} | ${finding.disposition ?? ''} | ${finding.reason ?? ''} | ${finding.action ?? ''} |`),
    ].join('\n')
  }
  const rows = tracks.map((track) => `| ${track.label} | ${track.verdict} | ${track.coverage ?? ''} |`).join('\n')
  const lines = [
    '## Review Summary',
    '| Field | Value |',
    '| --- | --- |',
    `| Target | ${reviewRun.target ?? ''} |`,
    `| Base / Head | ${reviewRun.baseSha ?? ''} / ${reviewRun.headSha ?? ''} |`,
    `| Mode | ${reviewRun.mode ?? ''} |`,
    `| Review phase | ${reviewRun.phase ?? ''} |`,
    `| Safety applicability / coverage | ${reviewRun.safetyText ?? ''} |`,
    `| Rounds | ${reviewRun.round ?? 1} |`,
    `| Stop reason | ${reviewRun.stopReason ?? ''} |`,
    `| Overall verdict | ${aggregate.overall} |`,
    '',
    '## Track Verdicts',
    '| Track | Verdict | Coverage / note |',
    '| --- | --- | --- |',
    rows,
    '',
    '## Findings',
    '| Classification | ID | Title | Source | Evidence | Decision |',
    '| --- | --- | --- | --- | --- | --- |',
    ...findings.map((finding) => `| ${finding.classification ?? ''} | ${finding.id ?? ''} | ${finding.title ?? ''} | ${finding.source ?? ''} | ${finding.evidence ?? ''} | ${finding.decision ?? ''} |`),
    '',
    '## Recommended Next Actions',
    '1. ',
    '2. ',
    '3. ',
  ]
  if (reviewRun.mode === 'Loop' && lifecycle) {
    lines.push('', '## Track Lifecycle', '| Track | Final state | Consecutive clean rounds | Last review round | Reactivated because |', '| --- | --- | --- | --- | --- |',
      ...lifecycle.map((track) => `| ${track.track} | ${track.state} | ${track.cleanRounds} | ${track.lastRound} | ${track.reactivated ?? ''} |`))
  }
  return lines.join('\n')
}

/* ── Topology resolution (deterministic; judgment-free) ──────────────────── */

/**
 * Resolve the reviewer topology from reviewer-registry.json.
 * - `initial` / `terminal-final`: default tracks, Safety appended when applicable.
 * - `finding-closure`: exactly one fresh independent reviewer.
 * - explicitReviewers: run exactly the stated list in order.
 * Exported for tests; pure given the registry content.
 */
export function resolveTopology(registry, { phase, explicitReviewers, safety = { applicable: false } }) {
  if (Array.isArray(explicitReviewers) && explicitReviewers.length > 0) {
    if (phase === 'finding-closure' && explicitReviewers.length !== 1) {
      throw new Error('finding-closure requires exactly one explicit reviewer')
    }
    return explicitReviewers.map((label, index) => ({ label, required: true, order: index }))
  }
  if (phase === 'finding-closure') {
    return [{ label: 'Independent closure reviewer', skill: 'reviewer', required: true, order: 0 }]
  }
  const tracks = (registry.default_tracks ?? []).map((track, index) => ({
    label: track.label,
    skill: track.skill,
    required: true,
    order: index,
  }))
  if (safety.applicable && (phase === 'initial' || phase === 'terminal-final')) {
    tracks.push({ label: 'Conditional Safety', skill: 'safety-review', required: true, order: tracks.length })
  }
  return tracks
}

/** Read and parse the bundled reviewer registry (relative to this module). */
export async function loadReviewerRegistry(pluginRoot) {
  const raw = await readFile(join(pluginRoot, 'skills/do-review/references/reviewer-registry.json'), 'utf-8')
  return JSON.parse(raw)
}

/* ── Orchestration outline ─────────────────────────────────────────────────
 * 1. loadReviewerRegistry → resolveTopology
 * 2. Safety admission ← main session judgement (orchestrator only receives it)
 * 3. createReviewRun via review_ledger.py create (atomic; stop before dispatch on error)
 * 4. buildBrief × track → parallel fresh independent leaf dispatch (native subagents)
 * 5. wait all; unavailable leaf → stop and ask, never silently degrade
 * 6. aggregateVerdicts; main session classifies/dedupes → renderReport
 * The dispatch/ledger plumbing is wired in a later iteration; the pure core
 * above is complete and tested.
 */

export function apply(ctx, config) {
  const pluginRoot = typeof config?.pluginRoot === 'string' && config.pluginRoot !== ''
    ? config.pluginRoot
    : undefined
  ctx.tools.register({
    name: 'impl_review_aggregate',
    description: 'Mechanically apply the do-review fail-closed aggregation: any required FAIL → FAIL; else any required UNCERTAIN → UNCERTAIN; all required PASS → PASS; Safety applicable but omitted from an explicit terminal-final list → INCOMPLETE. Pass tracks as JSON [{label, verdict, required}], safety as {applicable, selected}, phase as initial|finding-closure|terminal-final.',
    parameters: {
      type: 'object',
      additionalProperties: false,
      properties: {
        tracks: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            properties: {
              label: { type: 'string' },
              verdict: { type: 'string', enum: ['PASS', 'FAIL', 'UNCERTAIN'] },
              required: { type: 'boolean' },
            },
            required: ['label', 'verdict'],
          },
        },
        safety: {
          type: 'object',
          additionalProperties: false,
          properties: {
            applicable: { type: 'boolean' },
            selected: { type: 'boolean' },
          },
        },
        phase: { type: 'string', enum: ['initial', 'finding-closure', 'terminal-final'], default: 'terminal-final' },
      },
      required: ['tracks'],
    },
    output: {
      schema: { type: 'object', additionalProperties: false, properties: { text: { type: 'string' } }, required: ['text'] },
      render: (_args, value) => [{ type: 'text', text: value.text }],
    },
    async execute(args) {
      const tracks = args.tracks.map((track) => ({ ...track, required: track.required !== false }))
      const safety = args.safety ?? { applicable: false, selected: false }
      const phase = args.phase ?? 'terminal-final'
      const result = aggregateVerdicts({ tracks, safety, phase })
      return { text: `Overall: ${result.overall} — ${result.reason}` }
    },
  })
}
