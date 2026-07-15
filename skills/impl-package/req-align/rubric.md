---
target: skills/impl-package/req-align
updated: 2026-07-15
---
## 原则

- [待验证] Spec Gate 仍保护实质 contract；只有明确请求或高不确定性/高风险信号才附加 Grill，对清晰局部 delta 不增加对抗审查。（证据: R1）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-15

- 采纳「风险驱动 Grill」— 用户明确要求已有批准 contract 复用，Grill 仅用于高不确定性/高风险或明确请求，拒绝每次 Spec Gate 自动加一道 review。
