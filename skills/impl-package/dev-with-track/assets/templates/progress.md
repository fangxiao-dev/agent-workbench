# [执行尝试 ID | 任务 ID | Ticket ID] 进度账本

> 这是按需创建的恢复账本，不是第二个状态源或验收事实源。规则见 [Impl-Package Composition Contract](../../../skills/impl-package/references/impl-package-composition-contract.md)。

类型：[attempt / task / ticket]
创建日期：[YYYY-MM-DD]
执行尝试 ID（Attempt ID）：
规范执行来源：[本执行尝试恢复账本 / dag.md / patch DAG / tickets/<ticket>.md]
验收来源：[tickets/<ticket>.md / spec.md + plan Execution Record + gate.md]

仅当 tickets=false、dag=false 的 attempt 因中断、独立交接、外部门禁或 blocker 而需要恢复状态时，才创建 `tasks/<attempt-id>-progress.md` 并设置 `Kind: attempt`。任务账本使用 `tasks/Tn-progress.md`；只有在 whole-ticket 恢复/移交触发时才创建 `tasks/<ticket-id>-progress.md`。attempt 账本不得虚构 T<n>、复制 plan 验证内容或充当验收结论。

## 恢复上下文

- Owner / 交接目标：
- 最近一次有意义的更新：
- 恢复时的规范状态：
- 已对账证据：
- 未满足的前置条件 / 外部门禁：

## 证据

- [命令 / 观察结果 / smoke 标记 / 记录 ID / 清理结果]

## 重新校验

- 上游返工或重新打开的输入：
- 受影响的下游证据：
- 依赖释放前必须重查的内容：

## 下一步

1. [下一步动作]
