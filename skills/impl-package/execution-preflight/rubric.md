---
target: skills/impl-package/execution-preflight
updated: 2026-08-04
---
## 原则

- [待验证] 开工前应尽可能一次性穷举并打包申请当前任务可预见的全部授权，覆盖实现、验证、清理、外部工具与 Git/Issue 收口；不得把计划中已经可见的权限拆成执行途中的连续追问。（证据: R1）
- [待验证] handoff、implementation package、DAG 或长任务默认采用 `default-long`：主 session 仅保留治理/验收/gate 收口，subagent 充分承担可隔离执行切片；普通模式才允许主 session 直接做局部执行。（证据: R2、R4）
- [待验证] handoff 只在 package/HEAD、D/S/P、sidecar digest、runtime/gate、contract-status 与 authorization envelope 全匹配时复用 task-scoped preflight facts；锚点冲突先读对应 control slice，授权边界确有缺失或实质变化时才完整重扫。（证据: R5）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-26
- 采纳「前置一次性授权包」— 用户原话：尽量在开头就一次性要好授权，不要后面专门为了授权停下。

### R2 · 2026-07-26
- 采纳「调度优先、充分利用 subagent」— 用户原话：Execution Preflight 对于主 Session 和 Subagent 的配合模式说得太保守了，我需要 Subagent 可以充分被利用。

### R3 · 2026-07-26
- 采纳「主路径简化、细节按条件外链」— 用户要求在不丢失语义的情况下简化当前 Skill 或外链细节；沿用 global rubric 已确认的渐进披露原则，不在本 Skill 重复建立同名原则。

### R4 · 2026-07-27
- 采纳「两种调度模式」— 用户要求默认/长任务中主 session **只能**承担治理与收口，subagent 应充分承担可隔离工作以降低上下文压力；普通模式才保留主 session 可直接执行局部工作的语义。

### R5 · 2026-08-04
- 采纳「精确锚点恢复」— execution handoff 不替代长期事实源；仅全锚点一致时复用 task-scoped preflight facts，冲突按 control slice 增量核查，避免把 freshness drift 自动扩大为完整授权重扫。
