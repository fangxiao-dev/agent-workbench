/**
 * dispatch-scan-hook — agent/pre-step checklist injection for the
 * parallel-dispatch habit.
 *
 * Before every agent step it injects a compact dispatch-scan checklist so
 * "waiting turns into scanning" becomes a forced habit rather than a
 * model-memory convention. The injection is unconditional (no throttle, no
 * state): the checklist costs one short user message per step and the agent
 * filters non-waiting steps itself (the message is phrased conditionally:
 * "if this step is about to wait/poll/block…").
 *
 * Design decisions:
 * - Delegated agents (review leaves, workers) are skipped (delegationDepth
 *   >= 1): their context stays scoped to the dispatched brief, and the main
 *   controller is the only dispatcher.
 * - No persistence, no trail: the hook only reminds; judgment stays with the
 *   model. If a scan later needs auditing, add a trail writer separately.
 *
 * Loaded as a preset-local plugin (`name: ./scan-hook.mjs`); the preset dir
 * must also be the only place this file needs to exist, so this module uses
 * only node: builtins.
 */

import { randomUUID } from 'node:crypto'

export const name = 'dispatch-scan-hook'

export const DEFAULT_CONFIG = {
  humanLabel: '[dispatch-scan]',
}

const CHECKLIST = [
  '1. 已提交未 review 的 fix → 派只读 recheck',
  '2. 改动域回归（兄弟 spec / 集成层 / 与组件测试互补的 UI 冒烟）',
  '3. 零依赖落盘：progress / evidence / 文档',
  '4. 只读预研（后续 ticket investigations）或环境预热',
  '纪律：只读与写分离；后台任务带 liveness + kill 规则；派发前确认结果消费者',
]

/** Build the injected user message (mirrors the official hook message shape). */
export function buildDispatchScanMessage(text, label = DEFAULT_CONFIG.humanLabel) {
  return {
    id: randomUUID(),
    role: 'user',
    content: [{ type: 'text', text }],
    source: { kind: 'dispatch-scan', label },
  }
}

export function composeDispatchScanText(label = DEFAULT_CONFIG.humanLabel) {
  return [
    `${label} 若本轮将进入等待/轮询/阻塞，先扫可并行派发项：`,
    ...CHECKLIST.map((line) => `  ${line}`),
  ].join('\n')
}

export function apply(ctx, config = {}) {
  const label = String(config.humanLabel || DEFAULT_CONFIG.humanLabel)
  const text = composeDispatchScanText(label)

  ctx.on('agent/pre-step', async (payload, next) => {
    const decision = await next()
    try {
      if (decision?.kind !== 'enter') return decision
      const session = payload?.agent?.session
      if (session === undefined) return decision
      // Review leaves and other delegated agents inherit this preset's
      // composition; skip injection for them so their context stays scoped.
      const depth = session?.header?.delegationDepth
      if (depth !== undefined && depth > 0) return decision

      const message = buildDispatchScanMessage(text, label)
      const lastClaimedIndex = (decision.messages ?? []).findLastIndex((m) =>
        (payload.messages ?? []).includes(m)
      )
      return {
        kind: 'enter',
        messages:
          lastClaimedIndex >= 0
            ? decision.messages.toSpliced(lastClaimedIndex + 1, 0, message)
            : [...decision.messages, message],
      }
    } catch (error) {
      ctx.logger?.warn?.(`dispatch-scan-hook: ${error instanceof Error ? error.message : String(error)}`)
      return decision
    }
  })
}
