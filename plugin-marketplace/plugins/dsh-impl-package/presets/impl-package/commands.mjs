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

/** Stage routing table: the native entry column of impl-package/SKILL.md
 *  (re-aligned 2026-09). Entries merged or retired upstream are gone here:
 *  execution-preflight/verification-before-completion → execution-boundaries;
 *  subagent-driven-development → dispatcher; standing-bookkeeper → dispatcher
 *  admission; grilling and create-task-dag stay reachable via the skill
 *  catalog (not impl-package stage routes). */
export const COMMANDS = [
  { name: 'impl-req-align', stage: 'req-align', description: '需求/Decision/Spec 对齐。' },
  { name: 'impl-grill-me-smartly', stage: 'grill-me-smartly', description: '在高风险 Spec gate 做 ledger 驱动审问。' },
  { name: 'impl-impl-planning', stage: 'impl-planning', description: '创建 initial/patch plan、决定 Composition。' },
  { name: 'impl-plan-review', stage: 'plan-review', description: '审查 plan 或完整 Plan/Ticket/DAG bundle。' },
  { name: 'impl-to-tickets', stage: 'to-tickets', description: '创建独立验收切片（impl-planning 的 Ticket-split）。' },
  { name: 'impl-execution-boundaries', stage: 'execution-boundaries', description: '执行前授权、异常对账、完成前 evidence gate。' },
  {
    name: 'impl-dispatcher',
    stage: 'dispatcher',
    description: '候选选择、bounded brief、dependency/resource admission、dispatch/return/review 与 idle。',
    text: '按 $dispatcher skill 处理当前 Impl-Package 任务：候选选择、bounded brief、dependency/resource admission、dispatch/return/review 与 idle；进入执行阶段先读其「执行原则」四行。trail dispatch 记录 dispatch_id/candidate_id/subject/mode/chosen/resource_keys/receipt；worker return 用 of 指回 dispatch 并带唯一 return_id。',
  },
  { name: 'impl-dev-with-track', stage: 'dev-with-track', description: '恢复执行、确定业务重点与候选范围、消费 Dispatcher 结果、推进 Ticket 与写 Gate。' },
  { name: 'impl-monitor-progress', stage: 'monitor-progress', description: '打开实时进度页面，并可选创建只读主控监控 automation。' },
  { name: 'impl-do-review', stage: 'do-review', description: '多 reviewer 编排、fail-closed 聚合 findings 并判断收敛。' },
  { name: 'impl-review-code', stage: 'review-code', description: '审查实现正确性和可维护性。' },
  { name: 'impl-review-code-by-standards', stage: 'review-code-by-standards', description: '按仓库规范和模块 interface/depth/locality 审查代码。' },
  { name: 'impl-review-code-by-spec', stage: 'review-code-by-spec', description: '按需求、Spec、Plan 审查代码忠实度。' },
  { name: 'impl-safety-review', stage: 'safety-review', description: '审查安全、数据完整性、并发和外部副作用。' },
  { name: 'impl-backfill-stable-docs', stage: 'backfill-stable-docs', description: '回刷稳定知识或退休 package。' },
  { name: 'call-codex', stage: 'call-codex', description: 'Codex CLI 协作模式（resume 续接/流式隔离/及时调整 prompt/小步纪律/降级探针/review 回投修复）。', text: '按 call-codex 协作模式处理当前 Codex 协作任务（resume 续接、流式隔离、发现不对及时改 prompt、小步纪律、降级探针、review 回投原 implementer 会话修复）。加载 skill：call-codex（agent-workbench/skills/call-codex/SKILL.md），按其中模式执行；wrapper 仅用于需要程序化 envelope 的一次性调用。' },
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
        const text = def.text !== undefined
          ? [def.text, supplement].filter(Boolean).join('\n')
          : [
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
