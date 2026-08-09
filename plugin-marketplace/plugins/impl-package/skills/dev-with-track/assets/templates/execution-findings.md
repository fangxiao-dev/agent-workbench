# [实施名称] 执行发现

状态：[活跃 / 暂停 / 已关闭]
创建日期：[YYYY-MM-DD]
规格：[spec.md](spec.md)
对应门禁：[gate.md](gate.md)

本文记录执行过程中确认的重要发现、风险、方法性经验与跨 task 发现，可供整个任务包及后续 attempt 使用，并作为 package-local provenance 保留。它不是第二份行为合同，也不是临时待办队列。Task 局部交接留在 `execution/<attempt>/task-handoffs/<task-id>-handoff.md`；gate evaluation 前必须把决策与 rationale 分流到 `decision.md`、规范性行为分流到 `spec.md`、长期项目知识分流到 gate Durable Deltas / `_pending.md`、验证证据与判断分流到当前 Attempt 的 `execution-record.md`。

## [YYYY-MM-DD] [执行尝试 ID] [Slice / Task / Gate] 发现

### 方法层发现

- [例如：某类验证必须等待异步状态稳定后再取证。]
- [例如：测试数据必须与真实后端读写隔离。]

### UI 层发现

- [例如：某列在 desktop 下过窄。]
- [例如：某表格在窄 viewport 下不可读。]
- [例如：某 disabled 能力容易被误解为已实现。]

### 业务 / 边界发现

- [例如：某真实操作尚未接通，必须保持 disabled。]
- [例如：吸收真实入口时必须保留 auth / i18n / mutation 可用性边界。]

## 提升规则（Promotion Rules）

- execution findings 只记录已经确认且值得跨 task 或跨 attempt 保留的事实、风险、判断与方法性经验。
- 不在这里写详细功能合同、最终验证证据或实现状态；它们分别进入 `spec.md`、Attempt ER 与 runtime artifact。
- 不提升每个 task 的普通进度；只提升跨 task 或 gate-relevant 发现。
- 原始 ideas、调查过程、候选假设、实验材料与参考笔记写入按需 earned 的 `investigations/<topic>.md`；不得创建空目录或空文件，也不得把 investigation 当成 authority 或运行状态。
