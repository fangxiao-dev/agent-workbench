---
target: skills/impl-package/subagent-driven-development
updated: 2026-07-26
---
## 原则

- [待验证] 复审机制应从可泛化的风险与契约覆盖方法出发，避免把单一事故或技术形态固化成所有 task 的必经步骤。（证据: R1）
- [待验证] 本 skill 保持通用 executor：消费调用方给出的目标、边界与局部验证要求，但不治理 plan-specific Verification/case ID 或判断计划合同是否完备。（证据: R4）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-17

- 采纳「以 review basis、风险信号和 closure review 组织 task review」— 用户原话：改，但不要用这一个 case-specific 而是从方法论上优化。

### R2 · 2026-07-18（最小 Task 执行）

- **Supersedes R1 的默认机制：**普通 Task 只需要有界派发、局部验证与 BLOCKED 回报；不再默认创建 review basis、双 reviewer 或 closure review。
- 高风险实际 diff 仍按 auth/permission、migration、外部写入、金额、不可逆数据等信号追加必要验证或 review；Ticket 正式 review 与 acceptance 继续由 `dev-with-track` 负责。

### R3 · 2026-07-19（集成委派）

- 采纳「主 session owns integration 不等于亲自编码；用可声明边界、可隔离写入、决策闭合、可复核结果和可回收失败决定是否派发」— 用户原话：希望“当 seam 满足以下条件”更泛化，而非 case-specific；随后明确同意修改。

### R4 · 2026-07-26（保持通用 executor）

- 否决让 executor 携带并治理 plan-specific Verification/case ID 完备性的方案 — 用户原话：这个 skill 更像是 executor 而不是调度者，应该偏通用。
