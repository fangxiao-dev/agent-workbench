---
target: plugin-marketplace/plugins/impl-package/skills/monitor-progress
updated: 2026-09-04
---
## 原则

- [已确认] 正式 Ticket 与 Gate 状态以 implementation package 的 machine-owned state 为准，会话文本只解释实际执行进展。
- [已确认] 一个 Observation topic 只承载一个可被未来消息独立修改的决策轴；不同轴分别维护。
- [已确认] Observation 用一个 kind 字段区分 one-time 与 pattern；Owner 明示的具体 Ticket、session、本次动作或一次性决策优先判为 one-time，只有未明示实例边界时才使用替换测试；不为此新增独立 directive runtime 或 sidecar。
- [已确认] 每个实际发送的 automation 报告都显式展示模拟纠偏状态；无触发时写“模拟纠偏：无”，但不因此单独通知。
- [已确认] 不新增“当前问题”字段；必须处理的 blocker、finding、失败测试和验收缺口归入 progress，improvements 只放不影响当前收口的可选建议。
- [已确认] 真实兜底的 blocker 范围由当前 confirmed observation 决定；automation 模板不得缩窄为授权问题等固定类别。
- [已确认] steer 必须先理解相邻对话；状态型 idle/notLoaded 不足以触发，Owner 正在讨论或目标正在等待回复时保持静默。
- [已确认] Owner 通知中的 Ticket 状态与 Renderer 四态一致；“开发中/调研中”是展示状态，正式 PENDING/SATISFIED 仍单独保留。

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-09-04
- 采纳 package state 与 canonical target updates 的混合事实源，避免把已 SATISFIED 的 Ticket 继续写成处理中。
- 采纳拆分过宽 Observation，并在更新报告中显示 before/after。
- 采纳 NOTIFY 报告显式显示空模拟纠偏，同时保留无变化静默。

### R2 · 2026-09-04
- 采纳 one-time/pattern 最小分类：只增加 kind 和实例替换测试，否决 activeDirectives、自动退休与额外 lifecycle。
- pattern 使用通用条件、行为与边界；one-time 保留具体对象和动作。

### R3 · 2026-09-04
- 采纳保持四字段 schema；实际开放问题归入 progress，improvements 仅承载可选建议。
- 否决为问题另增字段，避免 sidecar、Renderer 和兼容迁移扩张。

### R4 · 2026-09-04
- 纠正 one-time/pattern 判断顺序：TKT-10 Owner 一次性决策不得因正文可被泛化而标为 pattern。
- 明示范围优先于实例替换测试；替换测试只处理范围未明的输入。

### R5 · 2026-09-04
- 将 kind 值 specific 重命名为 one-time，使字段名称直接表达一次性边界。
