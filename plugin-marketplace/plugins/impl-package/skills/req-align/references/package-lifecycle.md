# Package Lifecycle

1. **Aligning**：Decision/Spec 尚在收敛；创建不可变、带日期前缀的 package ID，但不创建运行状态。
2. **Planned**：当前 attempt 的 plan 与 Composition 已批准。
3. **Active**：`.impl-package/state.json` 已初始化并有下一动作。
4. **Gate open**：实施/验证仍未形成 terminal verdict。
5. **Terminal**：`gate.md` 为 `pass | fail | defer`。
6. **Backfilled/retired**：durable delta 已处理，且 package 不再提供未消费的稳定知识。

生命周期从当前 artifact 和状态派生，不保存独立 Status/version registry。`blocked` 是可恢复状态，不是 terminal。terminal 后继续实现必须创建 patch attempt。

D/S/P 只是可选的可读别名；普通编辑不要求升级。Git commit 是跨 session 比较和历史审计的唯一版本锚点。

`contract-design.md` 是当前 `spec.md` 按复杂度 earned 的从属 artifact：与 `spec.md` 共用 Status、审批与 Spec Gate，没有独立 alias、revision、状态或生命周期。它存在时属于同一个 Spec contract ensemble；移除时先把仍有效的合同吸收回 `spec.md`，Git 负责保存历史。

## 影响路由

- implementation-only：沿用当前文档，进入当前 plan 或 terminal 后的新 patch plan。
- behavior-contract：更新当前 Spec，重跑受影响 Spec Gate；不维护手工 revision。
- decision-direction：先更新当前 Decision 并通过 Decision Gate，再更新当前 Spec 并通过 Spec Gate。
- editorial/projection-only：验证实际 diff 未改变行为、authority 或 acceptance。

只有实际受影响的 Plan/Ticket/Task/验证结果失效。未受影响范围保留；不得以“版本变化”为由机械清空全部执行状态。

## Module knowledge baseline

对齐时记录实际读取的稳定知识路径和 Git commit；不保存文件内容身份。发现当前 code/tests 与稳定知识冲突时，先判断权威来源与 durable delta，不把陈旧说明当作现役合同。
