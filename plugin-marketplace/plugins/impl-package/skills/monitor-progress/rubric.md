---
target: plugin-marketplace/plugins/impl-package/skills/monitor-progress
updated: 2026-09-04
---
## 原则

- [已确认] 正式 Ticket 与 Gate 状态以 implementation package 的 machine-owned state 为准，会话文本只解释实际执行进展。
- [已确认] 一个 Observation topic 只承载一个可被未来消息独立修改的决策轴；不同轴分别维护。
- [已确认] Observation 用一个 kind 字段区分 specific 与 pattern；用实例替换后是否仍约束后续同类场景作为唯一判断标准，不为此新增独立 directive runtime 或 sidecar。
- [已确认] 每个实际发送的 automation 报告都显式展示模拟纠偏状态；无触发时写“模拟纠偏：无”，但不因此单独通知。

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-09-04
- 采纳 package state 与 canonical target updates 的混合事实源，避免把已 SATISFIED 的 Ticket 继续写成处理中。
- 采纳拆分过宽 Observation，并在更新报告中显示 before/after。
- 采纳 NOTIFY 报告显式显示空模拟纠偏，同时保留无变化静默。

### R2 · 2026-09-04
- 采纳 specific/pattern 最小分类：只增加 kind 和实例替换测试，否决 activeDirectives、自动退休与额外 lifecycle。
- pattern 使用通用条件、行为与边界；specific 保留具体对象和动作。
