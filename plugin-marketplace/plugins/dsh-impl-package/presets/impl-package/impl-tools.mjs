/**
 * impl-tools — typed model-facing wrappers over the existing
 * impl_package_state.py CLI (package / ticket / evidence / recovery / gate /
 * trail command groups). The model stops composing shell commands and JSON
 * payloads by hand; the Python CLI remains the authority on state.json.
 *
 * Loaded as a preset-local plugin (`name: ./impl-tools.mjs`). Package and
 * scripts-root resolution are shared with the situation hook
 * (./situation-hook.mjs); stdin payload commands use the host subprocess
 * seam's `stdio.stdin = { data }` form.
 */

import { join } from 'node:path'
import { resolvePackageDir, resolveImplScripts } from './situation-hook.mjs'

export const name = 'impl-tools'
export const inject = ['subprocess', 'tools']

const MAX_OUTPUT_BYTES = 1 << 20
const TIMEOUT_MS = 60000

const TEXT_OUTPUT = {
  schema: {
    type: 'object',
    additionalProperties: false,
    properties: { text: { type: 'string' } },
    required: ['text'],
  },
  render: (_args, value) => [{ type: 'text', text: value.text }],
}

function str(value, field) {
  if (typeof value !== 'string' || value.trim() === '') throw new Error(`impl-tools: ${field} is required`)
  return value.trim()
}

function optionalStr(value) {
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : undefined
}

function strList(value, field) {
  if (value === undefined) return []
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string' || item.trim() === '')) {
    throw new Error(`impl-tools: ${field} must be an array of non-empty strings`)
  }
  return value.map((item) => item.trim())
}

/** Run one CLI invocation; throws on non-zero exit or spawn failure. */
async function runCli(ctx, python, argv, cwd, signal, stdinData) {
  let handle
  try {
    handle = ctx.subprocess.spawn({
      argv: [python, ...argv],
      cwd,
      stdio: {
        stdin: stdinData === undefined ? 'ignore' : { data: stdinData },
        stdout: { maxBytes: MAX_OUTPUT_BYTES },
        stderr: { maxBytes: MAX_OUTPUT_BYTES },
      },
      ...(signal !== undefined ? { signal } : {}),
      graceMs: 3000,
    })
  } catch (error) {
    throw new Error(`impl-tools: spawn failed (${python}): ${error instanceof Error ? error.message : String(error)}`)
  }
  const timer = new Promise((resolveTimer) => {
    setTimeout(() => resolveTimer({ timedOut: true }), TIMEOUT_MS)
  })
  const outcome = await Promise.race([handle.done, timer])
  if (outcome.timedOut === true) throw new Error('impl-tools: command timed out')
  let stdout = ''
  let stderr = ''
  try {
    stdout = handle.collected.stdout.readFrom(0).text
    stderr = handle.collected.stderr.readFrom(0).text
  } catch {
    // collected readers may be unavailable on some backends
  }
  const text = [stdout, stderr].filter((part) => part.length > 0).join('\n')
  if (outcome.exitCode !== 0) throw new Error(text.length > 0 ? text : `impl-tools: exit code ${outcome.exitCode}`)
  return text
}

/** Resolve the package dir for an execution, defaulting to the session cwd. */
function resolveForExec(exec, cfg, stateFileName) {
  const cwd = typeof exec?.agent?.session?.header?.cwd === 'string' ? exec.agent.session.header.cwd : undefined
  const packageDir = resolvePackageDir(cwd ?? process.cwd(), stateFileName, cfg.packagePath)
  if (packageDir === undefined) {
    throw new Error(`impl-tools: no Impl-Package state file (${stateFileName}) found under the session cwd`)
  }
  const scriptsRoot = resolveImplScripts(packageDir, cfg.implScriptsRoot)
  if (scriptsRoot === undefined) {
    throw new Error('impl-tools: cannot resolve impl-package scripts root (set implScriptsRoot in preset config)')
  }
  return { packageDir, scriptsRoot }
}

function registerTool(ctx, cfg, stateFileName, def) {
  const { name: toolName, description, parameters, execute } = def
  ctx.tools.register({
    name: toolName,
    description,
    parameters,
    output: TEXT_OUTPUT,
    async execute(args, exec) {
      const { packageDir, scriptsRoot } = resolveForExec(exec, cfg, stateFileName)
      const python = String(cfg.python || 'python')
      const text = await execute(args, exec, { packageDir, scriptsRoot, python })
      return { text }
    },
  })
}

/** Pure: build the `ticket <action>` argv. Exported for tests. */
export function buildTicketArgv(scriptsRoot, packageDir, args) {
  const argv = [join(scriptsRoot, 'impl_package_state.py'), '--package', packageDir, 'ticket', args.action, str(args.ticket, 'ticket')]
  const expect = str(args.expect, 'expect')
  argv.push('--expect', expect)
  if (args.action === 'satisfy') {
    argv.push('--revision', str(args.revision, 'revision (required for satisfy)'))
    argv.push('--environment', str(args.environment, 'environment (required for satisfy)'))
  } else if (args.action === 'block') {
    argv.push('--evidence', str(args.evidence, 'evidence (required for block)'))
  } else if (args.action === 'needs-revalidation') {
    const claims = strList(args.claims, 'claims')
    if (claims.length === 0) throw new Error('impl-tools: needs-revalidation requires at least one claim')
    for (const claim of claims) argv.push('--claim', claim)
    argv.push('--invalidated-by', str(args.invalidatedBy, 'invalidatedBy (required for needs-revalidation)'))
    const evidence = optionalStr(args.evidence)
    if (evidence !== undefined) argv.push('--evidence', evidence)
  } else if (args.action === 'pending') {
    const plan = optionalStr(args.revalidationPlan)
    if (plan !== undefined) argv.push('--revalidation-plan', plan)
  } else if (args.action === 'retire') {
    argv.push('--disposition', str(args.disposition, 'disposition (required for retire)'))
    argv.push('--evidence', str(args.evidence, 'evidence (required for retire)'))
    const successor = optionalStr(args.successor)
    if (successor !== undefined) argv.push('--successor', successor)
  } else {
    throw new Error(`impl-tools: unknown ticket action ${args.action}`)
  }
  return argv
}

export function apply(ctx, config) {
  const cfg = { ...config ?? {} }
  const stateFileName = String(cfg.stateFileName || '.impl-package/state.json')

  registerTool(ctx, cfg, stateFileName, {
    name: 'impl_package_validate',
    description: 'Validate the active Impl-Package state (exit code is the signal: 0 = valid, non-zero = projection drift or invalid state). Optionally pin the comparison point with --commit.',
    parameters: {
      type: 'object',
      properties: {
        package: { type: 'string', description: 'Package directory; default: resolved from the session cwd.' },
        commit: { type: 'string', description: 'Optional Git commit to compare against (cross-session or authorization binding).' },
      },
      additionalProperties: false,
    },
    async execute(args, _exec, { packageDir, scriptsRoot, python }) {
      const argv = [join(scriptsRoot, 'impl_package_state.py'), '--package', packageDir, 'package', 'validate']
      if (args.commit !== undefined && args.commit !== '') argv.push('--commit', args.commit)
      return runCli(ctx, python, argv, packageDir)
    },
  })

  registerTool(ctx, cfg, stateFileName, {
    name: 'impl_situation_render',
    description: 'Render the current Impl-Package situation (digest + selected situation + legal actions) via situation.py render --json. Omit validationResult to run package validate first and derive projection_drift. Returns the JSON render as text; use the digest for trail dispatch events.',
    parameters: {
      type: 'object',
      properties: {
        package: { type: 'string', description: 'Package directory; default: resolved from the session cwd.' },
        validationResult: { type: 'string', description: 'Optional JSON like {"projection_drift":false,"source":"package validate"}; computed when omitted.' },
        since: { type: 'string', description: 'Optional previous digest; when unchanged the render reports unchanged=true.' },
      },
      additionalProperties: false,
    },
    async execute(args, _exec, { packageDir, scriptsRoot, python }) {
      let validationResult = args.validationResult
      if (validationResult === undefined || validationResult === '') {
        const validate = await runCli(
          ctx,
          python,
          [join(scriptsRoot, 'impl_package_state.py'), '--no-situation', '--package', packageDir, 'package', 'validate'],
          packageDir,
        ).then(() => ({ code: 0 }), (error) => ({ code: 1, message: error.message }))
        validationResult = JSON.stringify({ projection_drift: validate.code !== 0, source: 'package validate' })
      }
      const argv = [join(scriptsRoot, 'situation.py'), 'render', '--package', packageDir, '--validation-result', validationResult]
      if (args.since !== undefined && args.since !== '') argv.push('--since', args.since)
      argv.push('--json')
      return runCli(ctx, python, argv, packageDir)
    },
  })

  registerTool(ctx, cfg, stateFileName, {
    name: 'impl_ticket_transition',
    description: 'Apply a semantic Ticket transition (PENDING | BLOCKED | NEEDS-REVALIDATION | SATISFIED | RETIRED). satisfy requires revision+environment; block requires evidence; needs-revalidation requires claims+invalidatedBy; retire requires disposition (waived|superseded)+evidence. Every transition requires the current state via expect; stale transitions are rejected.',
    parameters: {
      type: 'object',
      properties: {
        package: { type: 'string', description: 'Package directory; default: resolved from the session cwd.' },
        ticket: { type: 'string', description: 'Ticket id, e.g. TKT-01.' },
        action: { type: 'string', enum: ['satisfy', 'block', 'needs-revalidation', 'pending', 'retire'] },
        expect: { type: 'string', enum: ['PENDING', 'BLOCKED', 'NEEDS-REVALIDATION', 'SATISFIED', 'RETIRED'], description: 'Expected current state; stale transition is rejected.' },
        revision: { type: 'string', description: 'Git commit (satisfy, required).' },
        environment: { type: 'string', description: 'Explicit environment id (satisfy, required).' },
        evidence: { type: 'string', description: 'Repo-relative evidence path (block/retire required; needs-revalidation optional).' },
        claims: { type: 'array', items: { type: 'string' }, description: 'Claim ids (needs-revalidation, required).' },
        invalidatedBy: { type: 'string', description: 'Reason (needs-revalidation, required).' },
        revalidationPlan: { type: 'string', description: 'Plan path (pending, optional).' },
        disposition: { type: 'string', enum: ['waived', 'superseded'], description: 'Retire disposition (retire, required).' },
        successor: { type: 'string', description: 'Successor ticket (retire/superseded, optional).' },
      },
      required: ['ticket', 'action', 'expect'],
      additionalProperties: false,
    },
    async execute(args, _exec, { packageDir, scriptsRoot, python }) {
      const argv = buildTicketArgv(scriptsRoot, packageDir, args)
      return runCli(ctx, python, argv, packageDir)
    },
  })

  registerTool(ctx, cfg, stateFileName, {
    name: 'impl_evidence_add',
    description: 'Append one evidence record to a Ticket claim. Required: ticket, claim, timing (early-falsification|remaining-completion), artifact (repo-relative), revision (resolvable commit), environment, conclusion (supporting|contradictory|inconclusive). Optional invalidatedBy.',
    parameters: {
      type: 'object',
      properties: {
        package: { type: 'string', description: 'Package directory; default: resolved from the session cwd.' },
        ticket: { type: 'string' },
        claim: { type: 'string' },
        timing: { type: 'string', enum: ['early-falsification', 'remaining-completion'] },
        artifact: { type: 'string', description: 'Repo-relative path, e.g. evidence/test.md#anchor.' },
        revision: { type: 'string', description: 'Git commit id.' },
        environment: { type: 'string' },
        conclusion: { type: 'string', enum: ['supporting', 'contradictory', 'inconclusive'] },
        invalidatedBy: { type: 'string' },
      },
      required: ['ticket', 'claim', 'timing', 'artifact', 'revision', 'environment', 'conclusion'],
      additionalProperties: false,
    },
    async execute(args, _exec, { packageDir, scriptsRoot, python }) {
      const payload = {
        ticket: str(args.ticket, 'ticket'),
        claim: str(args.claim, 'claim'),
        timing: str(args.timing, 'timing'),
        artifact: str(args.artifact, 'artifact'),
        revision: str(args.revision, 'revision'),
        environment: str(args.environment, 'environment'),
        conclusion: str(args.conclusion, 'conclusion'),
      }
      if (args.invalidatedBy !== undefined && args.invalidatedBy !== '') payload.invalidatedBy = args.invalidatedBy
      const argv = [join(scriptsRoot, 'impl_package_state.py'), '--package', packageDir, 'evidence', 'add']
      return runCli(ctx, python, argv, packageDir, undefined, JSON.stringify(payload))
    },
  })

  registerTool(ctx, cfg, stateFileName, {
    name: 'impl_evidence_invalidate',
    description: 'Mark one evidence artifact invalidated on a Ticket claim (artifact + invalidatedBy required).',
    parameters: {
      type: 'object',
      properties: {
        package: { type: 'string', description: 'Package directory; default: resolved from the session cwd.' },
        ticket: { type: 'string' },
        claim: { type: 'string' },
        artifact: { type: 'string', description: 'Repo-relative artifact path.' },
        invalidatedBy: { type: 'string' },
      },
      required: ['ticket', 'claim', 'artifact', 'invalidatedBy'],
      additionalProperties: false,
    },
    async execute(args, _exec, { packageDir, scriptsRoot, python }) {
      const argv = [
        join(scriptsRoot, 'impl_package_state.py'), '--package', packageDir, 'evidence', 'invalidate',
        '--ticket', str(args.ticket, 'ticket'),
        '--claim', str(args.claim, 'claim'),
        '--artifact', str(args.artifact, 'artifact'),
        '--invalidated-by', str(args.invalidatedBy, 'invalidatedBy'),
      ]
      return runCli(ctx, python, argv, packageDir)
    },
  })

  registerTool(ctx, cfg, stateFileName, {
    name: 'impl_recovery_checkpoint',
    description: 'Overwrite the active checkpoint for a subject (attempt | ticket:<id>): next action, optional blocker, evidence paths, optional handoff flag. Checkpoints do not authorize dispatch — they record recovery facts.',
    parameters: {
      type: 'object',
      properties: {
        package: { type: 'string', description: 'Package directory; default: resolved from the session cwd.' },
        subject: { type: 'string', description: 'attempt or ticket:<id>.' },
        next: { type: 'string', description: 'The one next action.' },
        blocker: { type: 'string' },
        evidence: { type: 'array', items: { type: 'string' }, description: 'Repo-relative evidence paths.' },
        handoff: { type: 'boolean', description: 'True for an explicit handoff checkpoint (rotates the trail file).' },
      },
      required: ['subject', 'next'],
      additionalProperties: false,
    },
    async execute(args, _exec, { packageDir, scriptsRoot, python }) {
      const argv = [
        join(scriptsRoot, 'impl_package_state.py'), '--package', packageDir, 'recovery', 'checkpoint',
        '--subject', str(args.subject, 'subject'),
        '--next', str(args.next, 'next'),
      ]
      if (args.blocker !== undefined && args.blocker !== '') argv.push('--blocker', args.blocker)
      for (const item of strList(args.evidence, 'evidence')) argv.push('--evidence', item)
      if (args.handoff === true) argv.push('--handoff')
      return runCli(ctx, python, argv, packageDir)
    },
  })

  registerTool(ctx, cfg, stateFileName, {
    name: 'impl_recovery_judgment',
    description: 'Append a judgment to the current Attempt Execution Record. Payload: subject (attempt | ticket:<id>), title, content, optional evidence paths.',
    parameters: {
      type: 'object',
      properties: {
        package: { type: 'string', description: 'Package directory; default: resolved from the session cwd.' },
        subject: { type: 'string', description: 'attempt or ticket:<id>.' },
        title: { type: 'string' },
        content: { type: 'string' },
        evidence: { type: 'array', items: { type: 'string' }, description: 'Repo-relative evidence paths.' },
      },
      required: ['subject', 'title', 'content'],
      additionalProperties: false,
    },
    async execute(args, _exec, { packageDir, scriptsRoot, python }) {
      const payload = {
        purpose: 'judgment',
        subject: str(args.subject, 'subject'),
        title: str(args.title, 'title'),
        content: str(args.content, 'content'),
      }
      const evidence = strList(args.evidence, 'evidence')
      if (evidence.length > 0) payload.evidence = evidence
      const argv = [join(scriptsRoot, 'impl_package_state.py'), '--package', packageDir, 'recovery', 'judgment']
      return runCli(ctx, python, argv, packageDir, undefined, JSON.stringify(payload))
    },
  })

  registerTool(ctx, cfg, stateFileName, {
    name: 'impl_gate_commit',
    description: 'Write a Gate verdict for the current Attempt: pass | fail | defer | blocked (blocked keeps the attempt active). comparisonCommit + reason required. Terminal pass requires Stage 7: pass durableDelta entries (path + _pending.md/truth pointer) or an explicit noDurableDeltaReason.',
    parameters: {
      type: 'object',
      properties: {
        package: { type: 'string', description: 'Package directory; default: resolved from the session cwd.' },
        verdict: { type: 'string', enum: ['pass', 'fail', 'defer', 'blocked'] },
        comparisonCommit: { type: 'string' },
        reason: { type: 'string' },
        evidence: { type: 'array', items: { type: 'string' }, description: 'Repo-relative evidence paths.' },
        durableDelta: { type: 'array', items: { type: 'string' }, description: 'Durable-delta entries for terminal Stage 7.' },
        noDurableDeltaReason: { type: 'string', description: 'Explicit reason when there is no durable delta.' },
        environment: { type: 'string' },
      },
      required: ['verdict', 'comparisonCommit', 'reason'],
      additionalProperties: false,
    },
    async execute(args, _exec, { packageDir, scriptsRoot, python }) {
      const argv = [
        join(scriptsRoot, 'impl_package_state.py'), '--package', packageDir, 'gate', str(args.verdict, 'verdict'),
        '--comparison-commit', str(args.comparisonCommit, 'comparisonCommit'),
        '--reason', str(args.reason, 'reason'),
      ]
      for (const item of strList(args.evidence, 'evidence')) argv.push('--evidence', item)
      for (const item of strList(args.durableDelta, 'durableDelta')) argv.push('--durable-delta', item)
      if (args.noDurableDeltaReason !== undefined && args.noDurableDeltaReason !== '') argv.push('--no-durable-delta-reason', args.noDurableDeltaReason)
      if (args.environment !== undefined && args.environment !== '') argv.push('--environment', args.environment)
      return runCli(ctx, python, argv, packageDir)
    },
  })

  registerTool(ctx, cfg, stateFileName, {
    name: 'impl_trail_append',
    description: 'Append one manual trail event (append-only). payload is a JSON object WITHOUT v/seq/ts/head (the CLI fills them). Kinds: escape {subject, deviation, reason}; fact {subject, key (must be a known fact key), value}; dispatch {subject, worker, outcome:"RUNNING", returned:false, situation_digest (12-hex, from impl_situation_render), review fields}; worker-return {subject, outcome}.',
    parameters: {
      type: 'object',
      properties: {
        package: { type: 'string', description: 'Package directory; default: resolved from the session cwd.' },
        kind: { type: 'string', enum: ['escape', 'fact', 'dispatch', 'worker-return'] },
        payload: { type: 'string', description: 'JSON object string with the event fields (no common fields).' },
      },
      required: ['kind', 'payload'],
      additionalProperties: false,
    },
    async execute(args, _exec, { packageDir, scriptsRoot, python }) {
      let event
      try {
        event = JSON.parse(str(args.payload, 'payload'))
      } catch (error) {
        throw new Error(`impl-tools: trail payload is invalid JSON: ${error instanceof Error ? error.message : String(error)}`)
      }
      if (typeof event !== 'object' || event === null || Array.isArray(event)) {
        throw new Error('impl-tools: trail payload must be a JSON object')
      }
      event.kind = str(args.kind, 'kind')
      const argv = [join(scriptsRoot, 'impl_package_state.py'), '--package', packageDir, 'trail', 'append']
      return runCli(ctx, python, argv, packageDir, undefined, JSON.stringify(event))
    },
  })
}
