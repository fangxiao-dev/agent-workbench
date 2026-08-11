---
target: plugin-marketplace/plugins/impl-package/skills/dispatch-bounded-task
updated: 2026-08-11
---
## 原则

- [已确认] Task 已由 plan、Ticket 或 DAG 设计完成时，派发 skill 保持最小 dispatch / return 契约，不重复决定调度、开发、验收或 gate 方法。
- [待验证] Implementer 的具体 worker 选择属于派发适配器；`luna-worker` 适配且可用时默认使用，fallback 记录原因。（证据: R7, R8）
- [待验证] scheduling contract 和 `BLOCKED` 返回语义各保留一个权威定义；dispatch 与 worker 模板只引用或透传，不重复枚举字段。（证据: R8）

## 决策记录（滚动，最近 ≤5 轮）

### R4 · 2026-07-26（保持通用 executor）

- 否决让 executor 携带并治理 plan-specific Verification/case ID 完备性的方案 — 用户原话：这个 skill 更像是 executor 而不是调度者，应该偏通用。

### R5 · 2026-08-04（改名并打薄）

- 采纳将 `subagent-driven-development` 改名为 `dispatch-bounded-task`，并把运行正文压缩为最小派发与返回契约 — 用户原话：名字“太 general”；Ticket 和 Task 已设计好，“没必要专门再教 agent 怎么开发”。

### R6 · 2026-08-04（删除单消费者 reference）

- 采纳把 implementer 模板内联并删除 `references/prompts.md` — 用户判断：单消费者 reference 可以删除；目标是让该 skill 保持 80 行内且运行契约自足。

### R7 · 2026-08-11（三层正交化）

- 采纳 dispatch 只消费已释放单元与 SDD scheduling contract，选择 Implementer/Verifier 和具体 worker 并回收 `DONE/BLOCKED`；不再反向决定 mode、batch、ownership 或资源顺序。
- 采纳 Implementer 在适配且可用时默认使用 `luna-worker`，fallback 记录原因 — 用户明确同意三层降载与配置分流方案。

### R8 · 2026-08-11（二次降载审计）

- 采纳删除 dispatch 输入门、派发步骤和 worker 模板对 mode/batch/resource/cleanup 的重复枚举，改为原样消费一个 scheduling contract。
- 采纳把多处 `BLOCKED` 说明合并为一个返回合同，并把 dispatch 主体压回最小输入资格、角色/worker 选择、模板指针与回收语义。
