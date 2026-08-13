---
target: plugin-marketplace/plugins/impl-package/skills/subagent-driven-development
updated: 2026-08-13
---
## 原则

- [待验证] 委派热路径只保留一个 activation boundary；调查与执行可以作为 mode 保持逻辑正交，但 scheduling、role 与 worker selection 必须在同一入口内完成，不能只输出 route 后依赖第二个方法论 skill。（证据: R6）
- [已确认] 统一编排合同直接使用 `mode`、`worker` 与 conditional review strategy，不输出 downstream `route`；调查和实现可以沿用逻辑 worker，但每个已确认 finding 都启动 fresh fixer，复杂任务用独立 reviewer 的 checkpoint/closure gate 收口。（证据: R7, R11）
- [待验证] `worker` 字段是多态逻辑引用，可取 `$skill`、`@agent`、直接 model/profile 或 prompt-backed worker；SDD 不解释实现机制，只要求 resolver 满足统一输入、结果与生命周期合同。（证据: R8）
- [待验证] scheduling contract 使用条件化最小输出；共享资源字段只在实际存在时出现，不为所有调度建立固定七字段协议。（证据: R2）
- [待验证] 默认 worker 为 `$grok-worker`，安全 executor fallback 为一次 fresh `@luna-worker`；不回退到 main session，业务 `BLOCKED` 不触发 fallback。（证据: R9）
- [待验证] 每个 bounded unit 默认使用 fresh subagent；只有同一 source unit 的不可转移连续状态或显式 standing role 才记录并复用 worker identity。（证据: R3）
- [待验证] scheduling 只有 `LOCAL | SERIAL | PARALLEL | BLOCKED`：单个委派单元为 `SERIAL`，`LOCAL` 只用于有事实理由的原子、紧耦合或不可隔离操作。（证据: R4, R5）
- [待验证] `$grok-worker`、`@luna-worker`、direct model/profile、prompt-backed worker 和 `main-session` 通过同一 resolver contract 表达；解析失败在启动前 `BLOCKED`，不引入第二个 registry。（证据: R10）
- [待验证] `WorkerOutcome` 保持三态，`review_state` 单独表达 `PENDING_REVIEW`、`PASSED`、`FINDING` 和 `BLOCKED`，避免把 reviewer gate 混入 executor 状态。（证据: R10）

## 决策记录（滚动，最近 ≤5 轮）

### R4 · 2026-08-12（default-long 与 LOCAL 不变量）

- 采纳 `default-long ⇒ SERIAL/PARALLEL` 与 `LOCAL ⇒ ordinary + reason`，消除长任务模式与本地执行形态混用造成的执行归属歧义 — 用户批准 0.2.7 闭环修复计划。

### R5 · 2026-08-12（单轴 Scheduling）

- 采纳删除 `default-long | ordinary` mode 轴，把委派、本地、并行与阻塞压缩为唯一 scheduling 决定；保留历史记录中的旧术语，但活跃合同和调用方不再复制 mode。

### R6 · 2026-08-13（单一激活边界）

- 修正此前把调查、调度和派发拆为多个 activation boundary 的方向；这些职责继续逻辑正交，但应在一个入口 skill 中通过 mode 完成。
- worker 选择必须成为入口的显式输出，不能仅输出 downstream route 后依赖 agent 再次加载 worker 派发 skill。

### R7 · 2026-08-13（统一 worker 与 reviewer gate）

- 修正按复杂度切换 Implementer worker 的方向；调查和实现可以沿用调用者策略指定的逻辑 worker，但已确认 finding 必须启动 fresh fixer。
- 复杂度只决定实现后是否进入独立 `reviewer` gate；复杂任务可增加 checkpoint，最终使用 closure；编排合同直接携带 `mode`、`worker` 和 review strategy，删除 `route`。

### R8 · 2026-08-13（多态 worker 引用）

- 修正把 worker 等同于 agent profile 的假设；`worker` 是统一代号，可以引用 `$grok-worker`、`@luna-worker`、`gpt-5.6-terra/xhigh` 或 prompt-backed profile。
- SDD 只传递和校验统一 worker contract；具体解析与执行由对应 Skill、agent、model/profile 或 prompt resolver 负责。

### R9 · 2026-08-13（fallback 与渐进披露）

- 采纳默认 `$grok-worker → @luna-worker` 的一次 fresh fallback，不回退到主会话；业务 `BLOCKED` 不 fallback。
- 采纳 `SKILL.md` 正文不超过 180 行，原则与流程内联，mode-specific 细节下沉 references。
- 采纳旧 route/handoff 随 legacy 生命周期自然退休，不新增恢复协议；`call-grok` 物理目录暂不改名。

### R10 · 2026-08-13（resolver 与 review 状态）

- 根据独立审阅补齐 `$grok-worker` 与 `@luna-worker` 的解析落点、显式 fail-closed 条件和一次 fallback 状态机；不增加运行时 registry。
- 将 `PENDING_REVIEW` 定义为 `review_state`，保留 `WorkerOutcome` 三态，确保复杂 worker DONE 在 reviewer PASS 前不可收口。

### R11 · 2026-08-13（reviewer 路由与 fresh fixer）

- 采纳用常用的 `reviewer` 统一命名独立审查与验证角色；复杂任务可在 implementer 切片后使用 `checkpoint`，最终使用 `closure`。
- 采纳 main session 或 reviewer 发现 finding 都可直接路由到 fresh fixer；fixer 不复用旧 invocation，优先使用新的 `@luna-worker` 或 `$grok-worker`。
