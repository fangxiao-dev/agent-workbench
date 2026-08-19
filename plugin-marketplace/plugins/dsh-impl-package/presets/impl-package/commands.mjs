/**
 * impl-commands — native slash commands for Impl-Package stage routing.
 *
 * Replaces "the model reads the routing table" (impl-package/SKILL.md): the
 * user types `/impl-dev-with-track` etc., the command steers a short routing
 * instruction into the agent, and — because commands never enter the model
 * history — the routing costs 0 tokens. The steered message (kind
 * 'impl-package-command') is the authoritative domain record, so
 * `recordInput: false` avoids duplicating the input in command/run.
 *
 * Registered agent-plane (preset row), so only sessions composed from the
 * `impl-package` preset see them.
 *
 * Loaded as a preset-local plugin; uses only node: builtins plus the injected
 * `commands` service (the steer message mirrors createUserMessage's shape).
 */

export const name = 'impl-commands'
export const inject = ['commands']

/** Stage routing table (the /impl-package:* route map from impl-package/SKILL.md). */
export const COMMANDS = [
  { name: 'impl-req-align', stage: 'req-align', description: '进入需求对齐（Decision/Spec/contract-design）阶段。' },
  { name: 'impl-grill-me-smartly', stage: 'grill-me-smartly', description: '在高风险 Spec gate 做 ledger 驱动审问。' },
  { name: 'impl-grilling', stage: 'grilling', description: '对计划/Decision/Spec 做交互式深入质询。' },
  { name: 'impl-impl-planning', stage: 'impl-planning', description: '创建 initial/patch plan、决定 Composition。' },
  { name: 'impl-plan-review', stage: 'plan-review', description: '审查 plan 或完整 Plan/Ticket/DAG bundle。' },
  { name: 'impl-to-tickets', stage: 'to-tickets', description: '创建独立验收切片（Ticket）。' },
  { name: 'impl-create-task-dag', stage: 'create-task-dag', description: '审计或迁移旧 Task/DAG package（legacy read-only）。' },
  { name: 'impl-execution-preflight', stage: 'execution-preflight', description: '执行前确认授权与工作区。' },
  { name: 'impl-standing-bookkeeper', stage: 'standing-bookkeeper', description: '绑定/恢复 standing bookkeeper、消费写入回执（slow path）。' },
  { name: 'impl-subagent-driven-development', stage: 'subagent-driven-development', description: '调查/实现/修复/验证的 worker 编排入口。' },
  { name: 'impl-dev-with-track', stage: 'dev-with-track', description: '恢复执行、推进 Ticket、写 Gate。' },
  { name: 'impl-do-review', stage: 'do-review', description: '编排多 reviewer、聚合 findings、判断收敛。' },
  { name: 'impl-review-code', stage: 'review-code', description: '审查实现正确性和可维护性。' },
  { name: 'impl-review-code-by-standards', stage: 'review-code-by-standards', description: '按仓库规范和模块 interface/depth/locality 审查代码。' },
  { name: 'impl-review-code-by-spec', stage: 'review-code-by-spec', description: '按需求、Spec、Plan 审查代码忠实度。' },
  { name: 'impl-safety-review', stage: 'safety-review', description: '审查安全、数据完整性、并发和外部副作用。' },
  { name: 'impl-verification-before-completion', stage: 'verification-before-completion', description: '声称 complete/merge-ready 前审计证据。' },
  { name: 'impl-backfill-stable-docs', stage: 'backfill-stable-docs', description: '回刷稳定知识或退休 package。' },
]

/** Build the user-role steering message (mirrors createUserMessage shape). */
export function buildRouteMessage(text, command) {
  return {
    id: crypto.randomUUID(),
    role: 'user',
    content: [{ type: 'text', text }],
    source: { kind: 'impl-package-command', command },
  }
}

export function apply(ctx) {
  for (const def of COMMANDS) {
    ctx.commands.register({
      name: def.name,
      description: def.description,
      input: { hint: '可选补充：当前目标/上下文' },
      recordInput: false,
      handler: ({ agent, rawInput }) => {
        const supplement = typeof rawInput === 'string' && rawInput.trim() !== ''
          ? `补充输入：${rawInput.trim()}`
          : ''
        const text = [
          `以 ${def.stage} 阶段处理当前 Impl-Package 任务。`,
          supplement,
          '处境与合法动作由 pre-step 自动注入；机械写入走 impl_* 工具。',
        ].filter(Boolean).join('\n')
        agent.steer(buildRouteMessage(text, def.name))
        return { kind: 'success', text: `已路由至 ${def.stage}` }
      },
    })
  }
}
