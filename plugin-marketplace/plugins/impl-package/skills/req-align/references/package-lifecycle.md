# Package Lifecycle

1. **Aligning**：Decision/Spec 尚在收敛；创建不可变、带日期前缀的 package ID，但不创建运行状态。
2. **Planned**：当前 attempt 的 plan 与 Composition 已批准。
3. **Active**：`.impl-package/state.json` 已初始化并有下一动作。
4. **Gate open**：实施/验证仍未形成 terminal verdict。
5. **Terminal**：`gate.md` 为 `pass | fail | defer`。
6. **Backfilled/retired**：durable delta 已处理，且 package 不再提供未消费的稳定知识。

生命周期从当前 artifact 和状态派生，不保存独立 Status/version registry。`blocked` 是可恢复状态，不是 terminal。terminal 后继续实现必须创建 patch attempt。

D/S/P 只是可选的可读别名；initial Decision/Spec/Plan bundle 只保留一次最终 owner approval，普通编辑和后续 package 更新均直接沿用该 approval。Git commit 是跨 session 比较和历史审计的唯一版本锚点。

`contract-design.md` 是当前 `spec.md` 的从属 artifact：与 `spec.md` 共用 Status、审批与 Spec Gate，没有独立 alias、revision、状态或生命周期。每个新建或被修订的 Spec 都生成该文件；默认 `Disposition: detailed`，精确语义已由 `spec.md` 完整承担时使用 `Disposition: not-required` 并写明理由。未触及的 legacy Spec 到下次 req-align 再补齐。

## 影响路由

- implementation-only：沿用当前文档，进入当前 plan 或 terminal 后的新 patch plan。
- behavior-contract：更新当前 Spec，记录受影响范围并沿用 initial bundle approval。
- decision-direction：更新当前 Decision 与当前 Spec，记录受影响范围并沿用 initial bundle approval。
- editorial/projection-only：验证实际 diff 未改变行为、authority 或 acceptance。

只有实际受影响的 Plan/Ticket/Task/验证结果失效。未受影响范围保留；不得以“版本变化”为由机械清空全部执行状态。

## Module knowledge baseline

对齐时记录实际读取的稳定知识路径和 Git commit；不保存文件内容身份。发现当前 code/tests 与稳定知识冲突时，先判断权威来源与 durable delta，不把陈旧说明当作现役合同。
