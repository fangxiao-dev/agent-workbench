/**
 * impl-situation-hook — agent/pre-step situation injection for Impl-Package.
 *
 * Before every agent step it:
 *   1. resolves the active package (nearest ancestor-or-self containing
 *      `.impl-package/state.json`; fallback: `docs/implementations/<topic>/`
 *      under the git root; explicit `packagePath` config override wins);
 *   2. resolves the impl-package scripts root (explicit `implScriptsRoot`
 *      config, else the nearest ancestor tree carrying
 *      `plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py`);
 *   3. runs `impl_package_state.py package validate` and
 *      `situation.py render --json` (through the host subprocess seam);
 *   4. injects a compact `[impl-package 处境]` user message with the digest,
 *      selected situation, and legal actions — only when the digest changed
 *      (no per-step noise) and never when no package/Python is found.
 *
 * Judgment stays with the model: the injection is navigation, not a gate.
 * The escape trail (kind=escape) remains a model-written judgment event.
 *
 * Loaded as a preset-local plugin (`name: ./situation-hook.mjs`); the preset
 * dir must also be the only place these files need to exist, so this module
 * uses only node: builtins plus the injected subprocess service.
 */

import { existsSync, readdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'

export const name = 'impl-situation-hook'
export const inject = ['subprocess']

export const DEFAULT_CONFIG = {
  stateFileName: '.impl-package/state.json',
  packagePath: '',
  implScriptsRoot: '',
  python: 'python',
  maxRenderSeconds: 20,
  throttleMs: 2000,
  humanLabel: '[impl-package 处境]',
}

const MAX_OUTPUT_BYTES = 1 << 20 // 1 MiB

/** Whether `dir` contains the package state file. */
export function hasState(dir, stateFileName) {
  return existsSync(join(dir, stateFileName))
}

/** Walk up from `cwd` looking for a `.git` entry. */
export function findGitRoot(cwd, maxDepth = 16) {
  let cur = cwd
  for (let i = 0; i < maxDepth && cur; i += 1) {
    if (existsSync(join(cur, '.git'))) return cur
    const parent = dirname(cur)
    if (parent === cur) break
    cur = parent
  }
  return undefined
}

/**
 * Resolve the active package directory.
 * Order: explicit `packagePath` (absolute or cwd-relative) → nearest
 * ancestor-or-self holding the state file → `docs/implementations/<topic>/`
 * under the git root.
 */
export function resolvePackageDir(cwd, stateFileName, packagePath = '') {
  if (packagePath !== '') {
    const candidate = resolve(cwd, packagePath)
    if (hasState(candidate, stateFileName)) return candidate
  }
  let cur = cwd
  for (let i = 0; i < 16 && cur; i += 1) {
    if (hasState(cur, stateFileName)) return cur
    const parent = dirname(cur)
    if (parent === cur) break
    cur = parent
  }
  const repoRoot = findGitRoot(cwd)
  if (repoRoot !== undefined) {
    const implDir = join(repoRoot, 'docs', 'implementations')
    if (existsSync(implDir)) {
      for (const entry of readdirSync(implDir, { withFileTypes: true })) {
        if (!entry.isDirectory()) continue
        const candidate = join(implDir, entry.name)
        if (hasState(candidate, stateFileName)) return candidate
      }
    }
  }
  return undefined
}

/**
 * Resolve the impl-package scripts root (where impl_package_state.py and
 * situation.py live). Explicit config wins; otherwise walk up from the
 * package dir for `plugin-marketplace/plugins/impl-package/scripts`.
 */
export function resolveImplScripts(packageDir, implScriptsRoot = '') {
  if (implScriptsRoot !== '') {
    const candidate = resolve(packageDir, implScriptsRoot)
    if (existsSync(join(candidate, 'impl_package_state.py'))) return candidate
  }
  let cur = packageDir
  for (let i = 0; i < 16 && cur; i += 1) {
    const candidate = join(cur, 'plugin-marketplace', 'plugins', 'impl-package', 'scripts')
    if (existsSync(join(candidate, 'impl_package_state.py'))) return candidate
    const parent = dirname(cur)
    if (parent === cur) break
    cur = parent
  }
  return undefined
}

/** Count helper for render fields that may be arrays or counts. */
export function countOf(value) {
  if (Array.isArray(value)) return value.length
  if (typeof value === 'number') return value
  return '?'
}

/** Compose the compact situation text from a `situation.py render --json` result. */
export function composeSituationMessage(render, drift, label, protocol) {
  const selected = render?.selected ?? {}
  const actions = Array.isArray(selected.actions) ? selected.actions : []
  const lines = [
    `${label} digest=${String(render?.digest ?? '?')}`,
    `选中: ${String(selected.slug ?? '（无）')} · basis=${String(selected.basis ?? '?')} · judgment=${String(selected.judgment ?? '?')}`,
  ]
  if (actions.length > 0) {
    lines.push('动作:')
    for (const action of actions) {
      const marker = action?.default ? '（默认）' : ''
      lines.push(`  - ${String(action?.id ?? '?')}${marker}: ${String(action?.do ?? '')} — ${String(action?.effect ?? '')}`)
    }
  }
  lines.push(
    `并列匹配: ${countOf(render?.parallel_matches)} | 未判定: ${countOf(render?.undetermined)} | 未匹配: ${countOf(render?.unmatched)}`,
  )
  lines.push(`验证: package validate ${drift ? '失败（projection_drift=true）' : '通过'}`)
  if (typeof protocol === 'string' && protocol.trim() !== '') {
    lines.push(`协议: ${protocol.trim()}`)
  }
  return lines.join('\n')
}

/** Run one CLI command; resolves undefined on spawn failure or timeout. */
async function runCli(ctx, python, argv, cwd, signal, timeoutMs) {
  let handle
  try {
    handle = ctx.subprocess.spawn({
      argv: [python, ...argv],
      cwd,
      stdio: { stdin: 'ignore', stdout: { maxBytes: MAX_OUTPUT_BYTES }, stderr: { maxBytes: MAX_OUTPUT_BYTES } },
      ...(signal !== undefined ? { signal } : {}),
      graceMs: 3000,
    })
  } catch (error) {
    ctx.logger?.warn?.(`impl-situation-hook: spawn failed (${python}): ${error instanceof Error ? error.message : String(error)}`)
    return undefined
  }
  const done = handle.done.then(
    (outcome) => outcome,
    (error) => ({ error: error instanceof Error ? error.message : String(error) }),
  )
  const timer = new Promise((resolveTimer) => {
    setTimeout(() => resolveTimer({ timedOut: true }), timeoutMs)
  })
  const outcome = await Promise.race([done, timer])
  if (outcome.timedOut === true) {
    ctx.logger?.warn?.(`impl-situation-hook: command timed out after ${timeoutMs}ms`)
    return undefined
  }
  if (outcome.error !== undefined) return undefined
  let stdout = ''
  let stderr = ''
  try {
    stdout = handle.collected.stdout.readFrom(0).text
    stderr = handle.collected.stderr.readFrom(0).text
  } catch {
    // collected readers may be unavailable on some backends
  }
  return { code: outcome.exitCode, text: [stdout, stderr].filter((part) => part.length > 0).join('\n') }
}

/** Run validate + situation render; undefined when the chain cannot run. */
export async function refreshSituation(ctx, { packageDir, scriptsRoot, python, signal, maxRenderSeconds }) {
  const stateScript = join(scriptsRoot, 'impl_package_state.py')
  const situationScript = join(scriptsRoot, 'situation.py')
  const validate = await runCli(ctx, python, [stateScript, '--no-situation', '--package', packageDir, 'package', 'validate'], packageDir, signal, maxRenderSeconds * 1000)
  if (validate === undefined) return undefined
  const drift = validate.code !== 0
  const validationArg = JSON.stringify({ projection_drift: drift, source: 'package validate' })
  // NOTE — compaction pressure is deliberately NOT passed to the renderer.
  // `attempt.compaction_pressure_high` (fed by `--compaction-pressure`) drives
  // the Codex-oriented `attempt.record.handoff-due` situation: handoff exists
  // because Codex sessions die on context exhaustion and need an explicit
  // checkpoint handoff to a fresh thread. DSH sessions survive compaction in
  // place (the same session resumes; `impl-anchor` re-anchors after
  // compaction/end), so the handoff recommendation would be WRONG advice
  // here. Do not wire dsh-compaction pressure into this call — if DSH ever
  // needs compaction awareness, it belongs to impl-anchor's fallback logic
  // (re-inject the refreshed situation), not to handoff-due. Omitting the
  // parameter keeps `compaction_pressure_high` undetermined (never false),
  // so the situation table simply never selects the handoff rows on DSH.
  const rendered = await runCli(
    ctx,
    python,
    [situationScript, 'render', '--package', packageDir, '--validation-result', validationArg, '--json'],
    packageDir,
    signal,
    maxRenderSeconds * 1000,
  )
  if (rendered === undefined) return undefined
  let render
  try {
    render = JSON.parse(rendered.text)
  } catch {
    ctx.logger?.warn?.('impl-situation-hook: situation render produced invalid JSON')
    return undefined
  }
  return { render, drift }
}

/** Build the injected user message (mirrors the official hook message shape). */
export function buildSituationMessage(text, digest) {
  return {
    id: crypto.randomUUID(),
    role: 'user',
    content: [{ type: 'text', text }],
    source: { kind: 'impl-package-situation', digest: String(digest ?? '') },
  }
}

export function apply(ctx, config) {
  const cfg = {
    ...DEFAULT_CONFIG,
    ...(config ?? {}),
  }
  const stateFileName = String(cfg.stateFileName || DEFAULT_CONFIG.stateFileName)
  const throttleMs = Number.isFinite(cfg.throttleMs) && cfg.throttleMs > 0 ? cfg.throttleMs : DEFAULT_CONFIG.throttleMs
  const maxRenderSeconds = Number.isFinite(cfg.maxRenderSeconds) && cfg.maxRenderSeconds > 0 ? cfg.maxRenderSeconds : DEFAULT_CONFIG.maxRenderSeconds
  const python = String(cfg.python || DEFAULT_CONFIG.python)

  /** Per-session { lastDigest, lastRenderAt }; memory resets on restart →
   *  the first step after a resume re-injects the full situation. */
  const perSession = new Map()

  ctx.on('agent/pre-step', async (payload, next) => {
    const decision = await next()
    try {
      const agent = payload?.agent
      if (agent === undefined || decision?.kind !== 'enter') return decision
      const session = agent.session
      if (session === undefined) return decision
      // Review leaves and other delegated agents inherit this preset's
      // composition; skip situation injection for them (delegationDepth >= 1)
      // so their context stays scoped to the dispatched brief.
      if (session?.header?.delegationDepth !== undefined && session.header.delegationDepth > 0) return decision
      const cwd = session?.header?.cwd
      if (typeof cwd !== 'string' || cwd.length === 0) return decision

      const packageDir = resolvePackageDir(cwd, stateFileName, cfg.packagePath)
      if (packageDir === undefined) return decision
      const scriptsRoot = resolveImplScripts(packageDir, cfg.implScriptsRoot)
      if (scriptsRoot === undefined) return decision

      const now = Date.now()
      const state = perSession.get(session) ?? { lastDigest: undefined, lastRenderAt: 0 }
      if (now - state.lastRenderAt < throttleMs) return decision
      perSession.set(session, { ...state, lastRenderAt: now })

      const fresh = await refreshSituation(ctx, { packageDir, scriptsRoot, python, signal: payload.signal, maxRenderSeconds })
      if (fresh === undefined) return decision
      const digest = String(fresh.render?.digest ?? '')
      if (digest !== '' && digest === state.lastDigest) return decision // unchanged → no noise

      const protocol = fresh.render?.selected?.protocol
      const text = composeSituationMessage(fresh.render, fresh.drift, cfg.humanLabel, protocol)
      perSession.set(session, { ...state, lastDigest: digest, lastRenderAt: now })
      const message = buildSituationMessage(text, digest)
      const lastClaimedIndex = (decision.messages ?? []).findLastIndex((m) => (payload.messages ?? []).includes(m))
      return {
        kind: 'enter',
        messages: lastClaimedIndex >= 0
          ? decision.messages.toSpliced(lastClaimedIndex + 1, 0, message)
          : [...decision.messages, message],
      }
    } catch (error) {
      ctx.logger?.warn?.(`impl-situation-hook: ${error instanceof Error ? error.message : String(error)}`)
      return decision
    }
  })
}
