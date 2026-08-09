---
target: plugin-marketplace/plugins/impl-package/skills/do-review
updated: 2026-07-22
---

## 原则

- [已确认] `do-review` 是唯一 orchestrator；默认三个并列 leaf track 为 code、standards 与 spec。
- [已确认] 同一完整 diff 与 fixed comparison point 只由主会话确定一次；三轨同轮独立，第二轮起只接收 canonical ledger。
- [已确认] 本轮只调整 Ownership 与拓扑；不重写 `code-review` 或三个 reviewer 的内部审查设计。
- [已确认] 涉及计划包时，审查范围覆盖整个计划包的 commits，不只审查最后一个实现 commit。
- [待验证] 审阅编排使用最小必要的自然语言状态来保证轮次、证据和收敛可信，不以刚性 schema 或过度 canonical 字段限制 leaf reviewer 的主动探索。（证据: R2）
- [待验证] reviewer role 用首要审查意图与交接方向引导，不用排他的能力禁令；跨域风险仍可作为 candidate 交给父会话的 canonical ledger 归属与去重。（证据: R3）
- [待验证] 严格可维护性审查使用非穷尽启发式；建议应说明 diff 证据、维护后果和可行方向，但不设固定触发链或替代方案证明门槛。（证据: R3）
- [待验证] leaf reviewer 的 `SKILL.md` 与其参考材料只说明自身审查方法和证据表达；role、track、交接、归属和跨域协作统一由 `do-review` 说明。（证据: R4）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-20
- 采纳「默认 A/B/C 三轨」：`code-review`、`standards-review`、`spec-review`。
- 采纳「所有 dispatched reviewer 均为 leaf」：禁止调用 `do-review`、调度 subagent 或重新推导 topology/capacity。
- 采纳「默认 topology 与 canonical path 由 registry 驱动」：Python 不维护另一份默认 reviewer 名单。

### R2 · 2026-07-21
- 采纳「完整审阅上下文保留自由文本与证据语义」：用户明确要求字段用于兜底流程，而非限制 agent 主观能动性；真实的新风险经验证后应继续 loop。

### R3 · 2026-07-22
- 采纳「role 以审查偏重和交接引导，不以能力禁令限制 reviewer」— 用户确认：同意。
- 采纳「严格可维护性深挖使用启发式，不固定触发链或证据门槛」— 用户确认：同意。

### R4 · 2026-07-22
- 采纳「leaf skill 不描述其他 skill/track 的互动」— 用户原话：每个 skill 专注自己的事，调度层互动属于 `do-review`。
