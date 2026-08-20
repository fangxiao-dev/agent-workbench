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
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'

export const name = 'do-review-orchestrator'
export const inject = ['tools', 'subagents', 'subprocess']

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

/* ── Orchestration: ReviewRun creation + parallel leaf dispatch ──────────── */

/** Tools a reviewer leaf may use (read-only; the leaf inherits the preset
 *  composition, so the whitelist hides write/edit/bash/impl_* mutation tools). */
export const READONLY_TOOLS = ['read', 'grep', 'glob', 'skill', 'git_show']

/** Compact read-only persona for one review leaf (Track A/B/C/Safety). */
export function leafPersona(track) {
  const skill = track.skill ?? 'reviewer'
  return [
    `You are a read-only reviewer leaf (${track.label}) for an Impl-Package ReviewRun.`,
    `Load and follow your declared skill (${skill}). Review only the supplied complete diff and the fixed comparison point; never re-derive the range.`,
    'Read-only contract: never write/edit files, issues, git state, data, or external systems; never dispatch subagents; never call do-review; never re-evaluate topology/capacity; never inspect other tracks in this round. Immutable contract sources must be read with git_show (<resolved-head>:<path>) only, never the working tree.',
    'Return a compact structured index:',
    '  verdict: PASS | FAIL | UNCERTAIN',
    '  coverage: <one compact line>',
    '  findings: <slug> | <repo-relative-file>:<line> | <severity> | <one sentence>   (or "findings: none")',
    'Every finding needs evidence; incomplete is not PASS.',
  ].join('\n')
}

/** Parse the leaf compact index out of its final text. */
export function parseLeafOutput(text) {
  const value = typeof text === 'string' ? text : ''
  const verdictMatch = /verdict:\s*(PASS|FAIL|UNCERTAIN)/i.exec(value)
  const coverageMatch = /coverage:\s*([^\n]+)/i.exec(value)
  const findings = []
  const findingRe = /^\s*[-*]\s*([^\n|]+)\s*\|\s*([^\n|]+):(\d+)\s*\|\s*([^\n|]+)\s*\|\s*(.+)$/gm
  for (const match of value.matchAll(findingRe)) {
    findings.push({ slug: match[1].trim(), file: match[2].trim(), line: Number(match[3]), severity: match[4].trim(), summary: match[5].trim() })
  }
  return {
    verdict: verdictMatch?.[1]?.toUpperCase(),
    coverage: coverageMatch?.[1]?.trim(),
    findings,
  }
}

/** Pure: build the review_ledger.py create argv. Exported for tests. */
export function buildReviewRunArgv(pluginRoot, { repoRoot, base, head, slug, mode, roundCap, sources = [] }) {
  const argv = [
    join(pluginRoot, 'skills/do-review/scripts/review_ledger.py'), 'create',
    '--repo-root', repoRoot,
    '--base', base,
    '--head', head,
    '--slug', slug,
    '--mode', mode,
    '--round-cap', String(roundCap),
  ]
  for (const source of sources) argv.push('--source', source)
  return argv
}

/** Resolve the impl-package plugin root from a repo cwd (or explicit config). */
export function resolvePluginRoot(cwd, explicitRoot) {
  if (typeof explicitRoot === 'string' && explicitRoot !== '') return explicitRoot
  let cur = cwd
  for (let i = 0; i < 16 && cur; i += 1) {
    const scripts = join(cur, 'plugin-marketplace', 'plugins', 'impl-package', 'scripts')
    if (existsSync(join(scripts, 'impl_package_state.py'))) return dirname(scripts)
    const parent = dirname(cur)
    if (parent === cur) break
    cur = parent
  }
  return undefined
}

/** Run review_ledger.py create; resolves the canonical ReviewRun (ledger path + JSON). */
export async function createReviewRun(ctx, { pluginRoot, python, repoRoot, base, head, slug, mode, roundCap, sources }) {
  if (pluginRoot === undefined) throw new Error('impl_review_run: cannot resolve impl-package plugin root (set pluginRoot in preset config)')
  const argv = buildReviewRunArgv(pluginRoot, { repoRoot, base, head, slug, mode, roundCap, sources })
  const handle = ctx.subprocess.spawn({
    argv: [python ?? 'python', ...argv],
    cwd: repoRoot,
    stdio: { stdin: 'ignore', stdout: { maxBytes: 1 << 20 }, stderr: { maxBytes: 1 << 20 } },
    graceMs: 3000,
  })
  const outcome = await handle.done
  let stdout = ''
  let stderr = ''
  try {
    stdout = handle.collected.stdout.readFrom(0).text
    stderr = handle.collected.stderr.readFrom(0).text
  } catch {
    // collected readers may be unavailable on some backends
  }
  if (outcome.exitCode !== 0) {
    throw new Error(`review_ledger create failed (${outcome.exitCode}): ${stderr || stdout || 'no output'}`)
  }
  let parsed
  try {
    parsed = JSON.parse(stdout)
  } catch {
    throw new Error(`review_ledger create produced invalid JSON: ${stdout.slice(0, 400)}`)
  }
  return {
    ...parsed,
    ledgerPath: parsed?.ledger_path ?? parsed?.ledgerPath,
    baseSha: parsed?.base_sha ?? parsed?.baseSha ?? base,
    headSha: parsed?.head_sha ?? parsed?.headSha ?? head,
  }
}

/** Coerce a subagent result output (string or content blocks) to text. */
function resultText(output) {
  if (typeof output === 'string') return output
  if (Array.isArray(output)) {
    return output
      .filter((block) => block?.type === 'text' && typeof block.text === 'string')
      .map((block) => block.text)
      .join('\n')
  }
  return ''
}

/** Dispatch one fresh independent leaf via the native subagent seam. */
export async function dispatchLeaf(ctx, { track, brief, signal }) {
  if (ctx.subagents === undefined) throw new Error('impl_review_run: subagents service unavailable')
  const run = await ctx.subagents.start('spawn', {
    label: `do-review-${track.label}`,
    prompt: [{ type: 'text', text: brief }],
    persona: leafPersona(track),
    toolFilter: { allow: READONLY_TOOLS },
    maxDepth: 1,
    ...(signal !== undefined ? { signal } : {}),
  })
  const result = await run.result
  const text = resultText(result?.output)
  return { ...parseLeafOutput(text), raw: text }
}

/**
 * Full orchestration: topology → ReviewRun → briefs → parallel dispatch →
 * fail-closed aggregation → report. Judgment inputs (safetyAdmission,
 * acceptedFindings) come from the main session; leaf failures surface as
 * missing verdicts so the aggregation stays fail-closed.
 */
export async function orchestrate(ctx, input) {
  const pluginRoot = resolvePluginRoot(input.repoRoot ?? process.cwd(), input.pluginRoot)
  const registry = await loadReviewerRegistry(pluginRoot)
  const topology = resolveTopology(registry, {
    phase: input.phase,
    explicitReviewers: input.explicitReviewers,
    safety: input.safetyAdmission ?? { applicable: false },
  })
  const reviewRun = await createReviewRun(ctx, { pluginRoot, python: input.python ?? 'python', repoRoot: input.repoRoot, base: input.base, head: input.head, slug: input.slug, mode: input.mode, roundCap: input.roundCap ?? 1, sources: input.sources ?? [] })
  const dispatches = topology.map((track) => ({
    track,
    brief: buildBrief({
      reviewRun: {
        ...reviewRun,
        target: input.target ?? input.slug,
        mode: input.mode,
        phase: input.phase,
        round: input.round ?? 1,
        trackLabel: track.label,
        skill: track.skill,
        safety: input.safetyText ?? '',
        reportPath: input.reportPath,
      },
      phase: input.phase,
      round: input.round ?? 1,
      priorLedger: input.priorLedger,
    }),
  }))
  const tracks = await Promise.all(dispatches.map(({ track, brief }) =>
    dispatchLeaf(ctx, { track, brief, signal: input.signal }).then(
      (leaf) => ({ ...track, ...leaf }),
      (error) => ({ ...track, error: error instanceof Error ? error.message : String(error) }),
    ),
  ))
  const aggregate = aggregateVerdicts({ tracks, safety: input.safetyAdmission ?? { applicable: false }, phase: input.phase })
  const report = renderReport({ reviewRun, tracks, aggregate, findings: input.acceptedFindings ?? [] })
  return { report, tracks, aggregate, ledgerPath: reviewRun.ledgerPath }
}

export function apply(ctx, config) {
  const cfg = config ?? {}
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

  ctx.tools.register({
    name: 'impl_review_run',
    description: 'Run one complete do-review pass: create the immutable ReviewRun (review_ledger.py create), resolve topology (registry default tracks + conditional Safety, or an explicit exact list), dispatch fresh independent read-only leaf reviewers in parallel, aggregate fail-closed (any required FAIL → FAIL; UNCERTAIN → UNCERTAIN; all PASS → PASS; Safety applicable but omitted from terminal-final → INCOMPLETE), and render the report. Judgment inputs are yours: safetyApplicable/safetySelected must reflect your Safety admission; the report returns leaf verdicts + your findings table for classification.',
    parameters: {
      type: 'object',
      additionalProperties: false,
      properties: {
        base: { type: 'string', description: 'Base ref (resolved to a commit SHA by the ledger).' },
        head: { type: 'string', description: 'Head ref (resolved to a commit SHA by the ledger); the review comparison point.' },
        slug: { type: 'string', description: 'ReviewRun slug (e.g. the PR/package identifier).' },
        mode: { type: 'string', enum: ['N rounds', 'Loop', 'Closure verification'], description: 'Review mode.' },
        phase: { type: 'string', enum: ['initial', 'finding-closure', 'terminal-final'], description: 'Review phase.' },
        roundCap: { type: 'integer', minimum: 1, description: 'Round cap (default 1).' },
        sources: { type: 'array', items: { type: 'string' }, description: 'Path-based contract sources (repeatable).' },
        safetyApplicable: { type: 'boolean', description: 'Your Safety admission: does the diff touch safety boundaries?' },
        safetySelected: { type: 'boolean', description: 'Was Safety selected for this pass?' },
        explicitReviewers: { type: 'array', items: { type: 'string' }, description: 'Optional exact reviewer list (runs in order; finding-closure requires exactly one).' },
        repoRoot: { type: 'string', description: 'Repo root; default: session cwd.' },
      },
      required: ['base', 'head', 'slug', 'mode', 'phase'],
    },
    output: {
      schema: { type: 'object', additionalProperties: false, properties: { text: { type: 'string' } }, required: ['text'] },
      render: (_args, value) => [{ type: 'text', text: value.text }],
    },
    async execute(args, exec) {
      const cwd = typeof exec?.agent?.session?.header?.cwd === 'string' ? exec.agent.session.header.cwd : process.cwd()
      const result = await orchestrate(ctx, {
        pluginRoot: cfg.pluginRoot,
        python: cfg.python,
        repoRoot: args.repoRoot ?? cwd,
        base: args.base,
        head: args.head,
        slug: args.slug,
        mode: args.mode,
        phase: args.phase,
        roundCap: args.roundCap ?? 1,
        sources: args.sources ?? [],
        safetyAdmission: { applicable: args.safetyApplicable === true, selected: args.safetySelected === true },
        explicitReviewers: args.explicitReviewers,
        signal: exec?.signal,
      })
      return { text: result.report }
    },
  })
}
