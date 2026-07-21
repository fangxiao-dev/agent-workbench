# Decision Policy

## 两级 Finding

Candidate 只记录 `claim`、初步 `evidence/reasoning` 和 `risk`。它用于探索，不写入安全 ledger，也不要求 severity、alternatives 或完整依赖。

Formal finding 必须包含：

```yaml
id: ENG-A1
section: scope | architecture | code_quality | tests | performance
severity: P0 | P1 | P2 | P3
confidence: 同轮可比较的数值、等级或自然语言理由
claim: 可证伪的结论
evidence: 可核验引用或有界 absence-proof
evidence_dependencies: 实际支撑结论的 file/tree identity 与 hash
risk: 具体失败或维护成本
recommendation: 一个可执行改动
owner_gate: required | not_required
resolution: pending | accepted | rejected | deferred
```

只在真实存在时添加 `depends_on`、`blocks`、`alternatives` 或 `reversible`。不要制造伪选择或用 1–10 数字掩盖不确定性。

## Evidence Gate

直接事实引用文件、行号和必要原文。计划缺少 rollback、distribution、auth boundary、failure handling 等内容时，允许使用有界 `absence-proof`：记录搜索范围、预期 contract、实际观察和可使结论失效的 tree dependency。主要依赖推断且无法核验的观察不要晋升为 formal finding。

证据优先级通常是当前实现或权威 contract、可执行测试/运行结果、目标 plan 的声明、最后才是推断；发现冲突时报告冲突而不是挑选方便的来源。Framework、ORM、codegen 或 descriptor 创建的 symbol 必须检查生成它的 schema、migration、decorator、Meta/config 或生成定义，不能仅因 class body 没有字面量就判定缺失。Confidence 用于同轮校准，不得替代证据或把猜测升级为事实。

## Severity 语义

- `P0`：可信的灾难性、不可逆或立即安全风险；消除风险或由 owner 改变目标边界前不得称为 cleared 或执行 Apply。
- `P1`：很可能导致 material correctness、data、security、contract、recovery 或交付失败；必须接受修复，或由 owner 明确拒绝/延期并承担风险。
- `P2`：有界但实质性的可维护性、运营、性能、测试或兼容缺口；进入 manifest 并获得可见 disposition。
- `P3`：不阻塞交付的改进或观察；不得用它稀释 P0–P2，只有确实有后续价值时保留。

## 决策边界

产品意图、外部 contract、风险容忍度和不可逆操作必须 `owner_gate: required`。证据完整、局部、可逆且不改变 contract 的工程事实可以由 agent 推荐接受，但仍必须进入 manifest，并由 owner 的 manifest-hash Apply 授权最终把关。

## Batch Decision Protocol

只预问无法绑定目标或开始审查的问题。继续独立分支，把 owner 决定按依赖分为少量 waves；同波决定彼此独立。只有决定冻结多个 material branches、使大量结论失效或涉及不可逆 contract 时 early flush。校验漏答和冲突，只重问受影响项。

每个 wave 为每个决定展示稳定编号和字母到完整选项文本的唯一映射，例如 `1A 2B 3A`；只接受当前 wave 仍有效的编号与选项。允许空格、逗号、分号、换行或清楚的自然语言等价表达，不要求 owner 学习严格 parser 语法，也不跨尚未展示的 wave 猜测答案。

未知编号或选项只回显该项的有效映射；同一编号出现冲突答案时只重问该项；漏答不使已明确答案失效；上游选择使下游答案失效时说明依赖原因并只重问受影响下游。不要因一个格式错误重放整波，也不要为此建立持久 parsing 状态机。

Owner 对展示过的 canonical manifest hash 明确要求 Apply，即同时完成 ratification 和写入授权。任何受保护状态变化都使旧授权失效。
