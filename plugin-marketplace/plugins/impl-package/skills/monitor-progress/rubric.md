---
target: plugin-marketplace/plugins/impl-package/skills/monitor-progress
updated: 2026-09-05
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
- [已确认] automation 最终报告由 CLI 确定性生成并逐字输出；Skill、policy 和 prompt 不维护第二份排版模板。
- [已确认] 用户纠偏是 package 级连续合同：heartbeat 跨 automation/Attempt 读取累计全集；Renderer 恢复浮窗并用独立 Attempt 下拉框查看冻结历史，不受 Ticket 视图影响。

## 决策记录（滚动，最近 ≤5 轮）

### R4 · 2026-09-04
- 纠正 one-time/pattern 判断顺序：TKT-10 Owner 一次性决策不得因正文可被泛化而标为 pattern。
- 明示范围优先于实例替换测试；替换测试只处理范围未明的输入。

### R5 · 2026-09-04
- 将 kind 值 specific 重命名为 one-time，使字段名称直接表达一次性边界。

### R6 · 2026-09-05
- 采纳 CLI 单一格式化来源：`write-cycle` 生成完整报告，heartbeat 只逐字输出，避免模型自由排版造成格式漂移。
- 工具调用 commentary 与最终通知合同分离；确定性格式只约束最终通知正文。

### R7 · 2026-09-05
- 当前 Attempt 默认展示、历史 Attempt 主动切换；旧 Ticket 使用冻结快照，不混入当前 readyTickets。
- 用户纠偏属于 package 级，切换 patch plan 后继续保留。

### R8 · 2026-09-05
- 纠正 R7 的 UI 解释：用户纠偏恢复原浮窗，浮窗内使用独立 Attempt 下拉框查看历史快照。
- heartbeat 读取 package 累积全集；UI 的 Attempt 选择只改变展示，不改变监控合同。
