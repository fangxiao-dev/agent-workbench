/**
 * impl-anchor — recovery anchoring for Impl-Package sessions (cold start /
 * resume / package switch).
 *
 * Two-phase gate inspired by the liangshen (anchored-standard) kernel, but
 * with a different anchor target: instead of locking to Minimal's two tools
 * to anchor a reasoning trajectory, this locks STATE-WRITE tools to force the
 * model to first rebuild the package mental model (the injected situation)
 * before it may mutate state.json.
 *
 *   Phase 1 (recovery anchor): tools narrowed to a read-only whitelist
 *     (read/grep/glob/skill + impl_package_validate + impl_situation_render +
 *     subagent investigation + ask_user_question). Write tools (ticket /
 *     evidence / recovery / gate / trail / write / edit / bash / pwsh) are
 *     hidden; the situation injection still flows (it IS the anchor).
 *   Gate: the first assistant message references the injected digest or slug
 *     → promote. `maxAnchorSteps` is the fail-safe fallback.
 *   Phase 2: full native catalog restored; per-step situation injection
 *     continues as usual.
 *   Compaction fallback: after compaction/end the session re-anchors (the
 *     durable `next` scan pointer is kept so pre-boundary events never
 *     re-promote).
 *   Transparency (critical): a session with NO situation injection (not an
 *     Impl-Package task) is never locked — it promotes immediately.
 *
 * Loaded as a preset-local plugin (`name: ./impl-anchor.mjs`); uses only
 * node: builtins plus the injected systemPrompt service.
 */

export const name = 'impl-anchor'
export const inject = ['systemPrompt']

export const DEFAULT_ANCHOR_TOOLS = [
  'read',
  'grep',
  'glob',
  'skill',
  'impl_package_validate',
  'impl_situation_render',
  'subagent',
  'subagent_fork',
  'ask_user_question',
]

export const DEFAULT_ANCHOR_PROMPT =
  '恢复锚定：开始前先引用注入的 `[impl-package 处境]` 的 digest 或选中处境（例如 digest=xxxxxxxxxxxx），' +
  '确认你已理解当前 package 处境与合法动作后再动手。未确认前只开放只读工具与调查派发；' +
  '确认后写工具（ticket/evidence/recovery/gate/trail）自动放开。'

/* ── Pure helpers (exported for tests) ───────────────────────────────────── */

/** Extract { digest, slug } from a situation injection message. */
export function extractAnchor(message) {
  const source = message?.source
  const digest = typeof source?.digest === 'string' && source.digest !== '' ? source.digest : undefined
  let slug
  const blocks = Array.isArray(message?.content) ? message.content : []
  for (const block of blocks) {
    if (block?.type !== 'text' || typeof block.text !== 'string') continue
    const match = /选中:\s*([A-Za-z0-9._-]+)/.exec(block.text)
    if (match !== null) slug = match[1]
  }
  return digest === undefined && slug === undefined ? undefined : { digest, slug }
}

/** Whether assistant text references the anchor (digest or slug). */
export function referencesAnchor(text, anchor) {
  const value = typeof text === 'string' ? text : ''
  if (anchor?.digest !== undefined && anchor.digest !== '' && value.includes(anchor.digest)) return true
  if (anchor?.slug !== undefined && anchor.slug !== '' && value.includes(anchor.slug)) return true
  return false
}

/** Narrow a tool list to the anchor whitelist (tools are { name } objects). */
export function filterAnchorTools(tools, anchorTools) {
  const allowed = new Set(anchorTools)
  return (Array.isArray(tools) ? tools : []).filter((tool) => allowed.has(tool?.name))
}

/** Extract concatenated text from a message's content blocks. */
export function textOf(message) {
  const blocks = Array.isArray(message?.content) ? message.content : []
  return blocks
    .filter((block) => block?.type === 'text' && typeof block.text === 'string')
    .map((block) => block.text)
    .join('\n')
}

/** Promotion decision. Transparency: no situation anchor → never locked. */
export function decidePromotion(state, policy) {
  if (state.hasSituation === false) return true
  if (state.anchored === true) return true
  if (state.steps >= policy.maxAnchorSteps) return true
  return false
}

/** New per-session state. */
export function newState() {
  return {
    next: 0,
    promoted: false,
    hasSituation: false,
    anchorDigest: undefined,
    anchorSlug: undefined,
    anchored: false,
    steps: 0,
    hasCompacted: false,
    anchorSectionDisposer: undefined,
  }
}

/** Reset to Phase 1 after compaction; keeps `next` so old events never re-promote. */
export function resetToControlled(state) {
  if (typeof state.anchorSectionDisposer === 'function') {
    try {
      state.anchorSectionDisposer()
    } catch {
      // a failed section reset must never break the session
    }
    state.anchorSectionDisposer = undefined
  }
  state.promoted = false
  state.hasSituation = false
  state.anchorDigest = undefined
  state.anchorSlug = undefined
  state.anchored = false
  state.steps = 0
  state.hasCompacted = true
}

/** Scan appended session events and update the anchor state. */
export function scanEvents(state, events) {
  for (; state.next < events.length; state.next += 1) {
    const event = events[state.next]
    if (event === undefined) continue
    if (event.type === 'compaction/end') {
      resetToControlled(state)
    } else if (event.type === 'user/message') {
      const message = event.data?.message
      if (message?.source?.kind === 'impl-package-situation') {
        state.hasSituation = true
        const anchor = extractAnchor(message)
        if (anchor !== undefined) {
          state.anchorDigest = anchor.digest
          state.anchorSlug = anchor.slug
        }
      }
    } else if (event.type === 'assistant/message') {
      if (!state.anchored) {
        state.anchored = referencesAnchor(textOf(event.data?.message), {
          digest: state.anchorDigest,
          slug: state.anchorSlug,
        })
      }
    } else if (event.type === 'step/start') {
      state.steps += 1
    }
  }
  return state
}

/* ── Plugin ──────────────────────────────────────────────────────────────── */

export function apply(ctx, config) {
  const cfg = config ?? {}
  const anchorTools = Array.isArray(cfg.anchorTools) && cfg.anchorTools.every((item) => typeof item === 'string' && item !== '')
    ? [...new Set(cfg.anchorTools)]
    : [...DEFAULT_ANCHOR_TOOLS]
  const maxAnchorSteps = Number.isInteger(cfg.maxAnchorSteps) && cfg.maxAnchorSteps >= 1
    ? cfg.maxAnchorSteps
    : 3
  const anchorPrompt = typeof cfg.anchorPrompt === 'string' && cfg.anchorPrompt.trim() !== ''
    ? cfg.anchorPrompt
    : DEFAULT_ANCHOR_PROMPT

  const states = new WeakMap()
  const agentBySession = new WeakMap()
  let warned = false
  const warnOnce = (message) => {
    if (warned) return
    warned = true
    try {
      ctx.logger?.warn?.(message)
    } catch {
      // logger unavailable — the guard only avoids spamming
    }
  }

  const refresh = (agent) => {
    const session = agent?.session
    if (session === undefined) return undefined
    let state = states.get(session)
    if (state === undefined) {
      state = newState()
      states.set(session, state)
    }
    agentBySession.set(session, agent)
    if (!state.promoted) {
      scanEvents(state, session.events)
      if (decidePromotion(state, { maxAnchorSteps })) state.promoted = true
    }
    // Anchor prompt section: registered during Phase 1, disposed on promotion.
    if (state.promoted && typeof state.anchorSectionDisposer === 'function') {
      state.anchorSectionDisposer()
      state.anchorSectionDisposer = undefined
    } else if (!state.promoted && state.anchorSectionDisposer === undefined) {
      try {
        state.anchorSectionDisposer = ctx.systemPrompt.section({
          name: 'plugin:impl-anchor',
          order: 155,
          text: anchorPrompt,
        })
      } catch {
        // section registration may be unavailable on some compositions
      }
    }
    return state
  }

  ctx.on('system-prompt/assemble', async (assembly, context, next) => {
    const agent = context?.agent
    if (agent === undefined) return next()
    const state = refresh(agent)
    if (state === undefined || state.promoted) return next()
    const narrowed = filterAnchorTools(assembly.tools, anchorTools)
    if (narrowed.length === 0) {
      // Drift: the whitelist matched nothing (impl-tools not mounted?) —
      // degrade to the full catalog once, never lock the session.
      warnOnce('impl-anchor: anchor whitelist matched no tools; degrading to full catalog')
      return next()
    }
    return {
      ...assembly,
      tools: narrowed,
    }
  })

  ctx.on('session/event', (session, event) => {
    if (event?.type !== 'step/end' && event?.type !== 'turn/end' && event?.type !== 'compaction/end') return
    const agent = agentBySession.get(session)
    if (agent === undefined) return
    refresh(agent)
  })
}
