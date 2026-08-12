---
target: plugin-marketplace/plugins/impl-package/skills/dispatch-bounded-task
updated: 2026-08-12
---
## 原则

- [已确认] Task 已由 plan、Ticket 或 DAG 设计完成时，派发 skill 保持最小 dispatch / return 契约，不重复决定调度、开发、验收或 gate 方法。
- [待验证] Implementer 与 Fixer 使用同一选择顺序和复杂度判据，再按角色映射普通首选、executor fallback 与复杂任务 worker；Verifier 保持调用者/宿主适配。（证据: R7, R8, R10）
- [待验证] Fixer 只消费已确认且已边界化的 review finding；其 `DONE` 不表示 finding closure，正式 closure verification 仍由执行 owner 负责。（证据: R10）
- [待验证] dispatch 边界把原生 executor 结果映射为 `DONE | BLOCKED | INCOMPLETE`；只有 cleanup 完成且 residue 可归因的 `INCOMPLETE` 可进行一次 fresh fallback，业务 `BLOCKED` 不 fallback。（证据: R10-R12）
- [待验证] scheduling contract 和 `BLOCKED` 返回语义各保留一个权威定义；dispatch 与 worker 模板只引用或透传，不重复枚举字段。（证据: R8）
- [待验证] worker instance 选择消费 SDD lifecycle：没有显式 `reuse` 时新建 subagent，避免跨 source unit 累积私有上下文。（证据: R9）
- [待验证] native terminal status 只在 recovery adapter 解释，主派发路径不枚举事故类型。（证据: R12）

## 决策记录（滚动，最近 ≤5 轮）

### R8 · 2026-08-11（二次降载审计）

- 采纳删除 dispatch 输入门、派发步骤和 worker 模板对 mode/batch/resource/cleanup 的重复枚举，改为原样消费一个 scheduling contract。
- 采纳把多处 `BLOCKED` 说明合并为一个返回合同，并把 dispatch 主体压回最小输入资格、角色/worker 选择、模板指针与回收语义。

### R9 · 2026-08-11（fresh worker 默认值）

- 采纳 dispatch 只解释 SDD scheduling contract 的 lifecycle：缺少 `reuse` 就新建 subagent，存在 `reuse` 才沿用指定的同一 source unit 和 agent — 用户确认：同意，GO。

### R10 · 2026-08-12（Fixer 与统一 worker profile）

- 新增 Fixer，限定为已确认且已边界化的 review finding 修复；普通 Fixer 固定使用 `call-grok` 的 `grok-4.5/high`，不限制 Grok 使用内部 subagent，executor 失败 fallback 到 `luna-worker`，复杂任务直接使用 default subagent。
- 采纳角色无关的选择顺序与共享复杂度判据：Implementer 普通使用 `luna-worker`，其失败或复杂任务使用 default subagent；Verifier 保持调用者指定或宿主适配。fallback 不吞掉业务 `BLOCKED`，finding closure 仍归执行/review owner。

### R11 · 2026-08-12（失败恢复与一次 fallback）

- 采纳保留 Grok 15 分钟上限并依赖 heartbeat/liveness；executor incomplete 后先确认 cleanup 与 residue，再最多进行一次既定 fallback。未证实替代解释不能撤销已确认修复 — 用户批准 0.2.7 闭环修复计划。

### R12 · 2026-08-12（三态 WorkerOutcome）

- 采纳在 dispatch 边界统一 `DONE | BLOCKED | INCOMPLETE`，让 recovery 只消费语义结果；executor 的 timeout、disconnect、partial 等原生状态不再逐项渗透主路径或 eval。
