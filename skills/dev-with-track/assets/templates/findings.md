# [Project / Slice] Findings

状态：[活跃 / 暂停 / 已关闭]
创建：[YYYY-MM-DD]
对应进度：[process.md](process.md)
对应 gate：[gate.md](gate.md)

本文记录 preview / harness / screenshot / review / verification 中产生的发现、风险和后续候选动作。稳定可复用的经验成熟后，再提升到项目知识库或团队规范。

## [YYYY-MM-DD] [Phase / Slice] 发现

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

## 记录规则

- findings 只记录已观察到的事实、判断和候选后续动作。
- 不在这里写详细实现步骤；实现步骤进入 issue、impl-plan 或 PR。
- 若 finding 已转为 issue，在本文件补 issue 编号或链接。
