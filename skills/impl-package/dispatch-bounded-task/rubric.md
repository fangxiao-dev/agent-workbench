---
target: skills/impl-package/dispatch-bounded-task
updated: 2026-08-04
---
## 原则

- [待验证] Task 已由 plan、Ticket 或 DAG 设计完成时，派发 skill 保持单文件、自足的最小 dispatch / return 契约，不重复教授开发、验收或 gate 方法。（证据: R5, R6）

## 决策记录（滚动，最近 ≤5 轮）

### R2 · 2026-07-18（最小 Task 执行）

- **Supersedes R1 的默认机制：**普通 Task 只需要有界派发、局部验证与 BLOCKED 回报；不再默认创建 review basis、双 reviewer 或 closure review。
- 高风险实际 diff 仍按 auth/permission、migration、外部写入、金额、不可逆数据等信号追加必要验证或 review；Ticket 正式 review 与 acceptance 继续由 `dev-with-track` 负责。

### R3 · 2026-07-19（集成委派）

- 采纳「主 session owns integration 不等于亲自编码；用可声明边界、可隔离写入、决策闭合、可复核结果和可回收失败决定是否派发」— 用户原话：希望“当 seam 满足以下条件”更泛化，而非 case-specific；随后明确同意修改。

### R4 · 2026-07-26（保持通用 executor）

- 否决让 executor 携带并治理 plan-specific Verification/case ID 完备性的方案 — 用户原话：这个 skill 更像是 executor 而不是调度者，应该偏通用。

### R5 · 2026-08-04（改名并打薄）

- 采纳将 `subagent-driven-development` 改名为 `dispatch-bounded-task`，并把运行正文压缩为最小派发与返回契约 — 用户原话：名字“太 general”；Ticket 和 Task 已设计好，“没必要专门再教 agent 怎么开发”。

### R6 · 2026-08-04（删除单消费者 reference）

- 采纳把 implementer 模板内联并删除 `references/prompts.md` — 用户判断：单消费者 reference 可以删除；目标是让该 skill 保持 80 行内且运行契约自足。
