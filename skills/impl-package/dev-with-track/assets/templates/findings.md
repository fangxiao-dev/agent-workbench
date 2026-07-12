# [Implementation Name] Findings

状态：[活跃 / 暂停 / 已关闭]
创建：[YYYY-MM-DD]
Spec：[spec.md](spec.md)
对应 gate：[gate.md](gate.md)

本文是发现 inbox。task 局部日志留在 `tasks/` 或 `dag.md`；gate evaluation 前必须把设计决定分流到 design、规范性行为分流到 spec、长期项目知识分流到 gate Durable Deltas / `_pending.md`、验证证据分流到 plan Execution Record。

## [YYYY-MM-DD] [Attempt ID] [Slice / Task / Gate] 发现

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

### 后续候选动作

- [ ] [候选 checklist item]
- [ ] [候选 issue：只有 scope 和验收足够清楚时再升级]
- [ ] [候选 backlog]

## Promotion Rules

- findings 只记录已观察到的事实、判断和候选后续动作。
- 不在这里写详细功能合同、最终验证证据或实现状态；它们分别进入 `spec.md`、plan Execution Record 与 runtime artifact。
- 不提升每个 task 的普通进度；只提升跨 task 或 gate-relevant 发现。
- 若 finding 已转为 issue，在本文件补 issue 编号或链接。
