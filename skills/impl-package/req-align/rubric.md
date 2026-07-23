---
target: skills/impl-package/req-align
updated: 2026-07-23
---
## 原则

- [待验证] Spec Gate 仍保护实质 contract；只有明确请求或高不确定性/高风险信号才附加 Grill，对清晰局部 delta 不增加对抗审查。（证据: R1）
- [待验证] 会改变 Decision、Spec、authority、delivery path 或 Acceptance Semantics 的未知项，在 Decision Gate 通过前必须由允许的 investigation 关闭；不得降级为 plan risk。（证据: R2）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-15

- 采纳「风险驱动 Grill」— 用户明确要求已有批准 contract 复用，Grill 仅用于高不确定性/高风险或明确请求，拒绝每次 Spec Gate 自动加一道 review。

### R2 · 2026-07-23

- 采纳「blocking decision uncertainty」— feasibility / architecture-fit 的未知项只要反向答案会改变合同，就在 Decision Gate 关闭；read-only 调查直接执行，需授权或副作用的调查则持久化 BLOCKED。D/S gate 与已记录下游证据只推导 handoff 展示状态，不升级 schema。
