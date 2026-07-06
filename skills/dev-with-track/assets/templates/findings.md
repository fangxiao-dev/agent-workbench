# [Implementation Name] Findings

状态：[活跃 / 暂停 / 已关闭]
创建：[YYYY-MM-DD]
Spec：[spec.md](spec.md)
Plan：[plan.md](plan.md)
DAG：[dag.md](dag.md)
对应 gate：[gate.md](gate.md)

本文记录跨 task 的发现、风险和后续候选动作。task 局部日志留在 `tasks/` 或 `dag.md`；只有影响 plan、DAG、gate 或后续 implementation 的内容才提升到这里。稳定可复用的经验成熟后，再提升到项目知识库或团队规范。

## [YYYY-MM-DD] [Slice / Task / Gate] 发现

### 方法层发现

- [例如：preview route 需要等待 hydration 后再截图。]
- [例如：fixture 必须避免真实 backend reads。]

### UI 层发现

- [例如：某个 action column 在 desktop 下过窄。]
- [例如：某个表格在 390px 下不可读。]
- [例如：某个 disabled 能力容易被误解为已实现。]

### 业务 / 边界发现

- [例如：某真实 action 尚未接通，必须保持 disabled。]
- [例如：某真实 route 吸收时必须保留 auth / i18n / mutation availability。]

### 后续候选动作

- [ ] [候选 checklist item]
- [ ] [候选 issue：只有 scope 和验收足够清楚时再升级]
- [ ] [候选 backlog]

## Promotion Rules

- findings 只记录已观察到的事实、判断和候选后续动作。
- 不在这里写详细功能合同或实现步骤；功能合同进入 `spec.md`，实现步骤进入 `plan.md`、`dag.md`、task ledger、issue 或 PR。
- 不提升每个 task 的普通进度；只提升跨 task 或 gate-relevant 发现。
- 若 finding 已转为 issue，在本文件补 issue 编号或链接。
