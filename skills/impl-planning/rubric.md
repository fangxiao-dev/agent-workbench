---
target: skills/impl-planning
updated: 2026-07-12
---

## 原则

- 每次 attempt 独立决定 Composition；不得从 spec、历史 plan 或原 package 的拓扑继承 tickets/dag。
- design 保存选择与 rationale，spec 保存长期 contract，plan 只保存本 attempt 的策略、具体 migration、验证选择与过程证据。
- 简单 no-DAG attempt 不建立 task checklist；需要恢复时按触发条件创建 progress ledger。
- Planned Verification 只引用权威 policy 并选择本次检查；Execution Record append-only 记录实际命令、结果与证据。
- gate 只保存 newest-first append-only 判决摘要与 Durable Deltas；完整验证过程留在 plan Execution Record。
- terminal gate 冻结对应 plan；后续工作创建新 patch attempt，不能回写旧 attempt 记录。

## 决策记录（滚动，最近 ≤5 轮）

### R4 · 2026-07-12（Artifact lifecycle 与 append-only gate）

- Composition 从 spec 移到每次 attempt plan；活动期间只通过 P revision 修订。
- 撤销 R3 的 no-DAG patch executable checklist；no-DAG 不制造 task 状态，恢复由 progress ledger 承担。
- interface、seam、compatibility、约束与 Acceptance Semantics 归 spec；plan 只保留执行与验证过程。
- gate.md 成为 package 唯一 ledger；旧 evaluation entry 不修改，blocked→pass 用 Supersedes 新增 entry。

### R3 · 2026-07-12（已由 R4 取代）

- 保留“patch 不继承原 package 拓扑”的结论。
- “简单 patch 使用 executable checklist”的结论撤销；当前规则见 R4。

### R2 · 2026-07-11（已由 R4 的 attempt lifecycle 取代）

- req-align 为 design/spec owner；task/ticket runtime state 不回流 plan。
- 原 plan 双分支与 Package Engineering Contract 结构已被当前 artifact role 分工取代。
