---
target: skills/do-review
updated: 2026-07-20
---

## 原则

- [已确认] `do-review` 是唯一 orchestrator；默认三个并列 leaf track 为 code、standards 与 spec。
- [已确认] 同一完整 diff 与 fixed comparison point 只由主会话确定一次；三轨同轮独立，第二轮起只接收 canonical ledger。
- [已确认] 本轮只调整 Ownership 与拓扑；不重写 `code-review` 或三个 reviewer 的内部审查设计。
- [已确认] 涉及计划包时，审查范围覆盖整个计划包的 commits，不只审查最后一个实现 commit。

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-20
- 采纳「默认 A/B/C 三轨」：`code-review`、`standards-review`、`spec-review`。
- 采纳「所有 dispatched reviewer 均为 leaf」：禁止调用 `do-review`、调度 subagent 或重新推导 topology/capacity。
- 采纳「默认 topology 与 canonical path 由 registry 驱动」：Python 不维护另一份默认 reviewer 名单。
