---
name: standing-bookkeeper
description: 当一个 Implementation Package thread 遇到证据矛盾、恢复、部分写入补齐、跨 stage 对账或其他异常排查，需要按需调用 standing bookkeeper slow path 时使用；日常结构化写入和 Execution Record judgment 不路由给它。
---

# Standing Bookkeeper

这是 package thread 的异常 slow path 入口，不是日常记账角色。正常结构化写入由主 thread 直接调用现有 CLI，Execution Record judgment 和 findings 分流由主 thread 自己形成；bookkeeper 只在异常场景下恢复上下文、做对账并返回结构化修复建议或证据。它不改变 Impl-Package 的语义 owner、状态机或验收门。

## 触发条件

默认不调用 standing bookkeeper。只有下列异常需要进入 slow path：

- 证据互相矛盾，需要核对 claim、revision、environment、timing 或 artifact pair；
- 跨 session 或 transport 中断后的恢复，需要从 canonical state 重建上下文；
- 一批写入已经部分落盘，需要核对缺口并补齐；
- 跨 stage 的 artifact、state、Progress、checkpoint 或 Gate 需要对账；
- 其他异常排查表明主 thread 无法仅凭现有 state/CLI 安全收口。

evidence、checkpoint、fact、trail、state transition、Gate 等日常结构化写入，以及 Execution Record judgment 和 findings 分流，不触发 bookkeeper；主 thread 直接调用 CLI 或自己写成文结论。

## 角色边界

- 一个 package 不要求常驻或预先初始化 bookkeeper；需要 slow path 时按当前 package/Attempt 按需启动或恢复。
- 主 thread 保留 requirement、architecture、implementation direction、acceptance、finding disposition、Gate verdict、最终复核权，以及 `state.json` 的唯一写入权。
- bookkeeper 只负责异常上下文重建、证据/状态对账、缺口定位和结构化修复建议；不独占 package 物理写入，不直接修改 `state.json`，不替主 thread 形成 judgment 或 disposition。
- bookkeeper 不修改业务实现代码，不服务其他 package，不接管 commit、merge、push、release 或外部 mutation。

## 主 thread 流程

1. 日常路径由主 thread 读取当前 state，并直接调用适用的语义 CLI；没有异常时不要启动或等待 bookkeeper。
2. 发现上述异常时，按需启动或恢复 slow path，并提供 package、Attempt、相关 artifact/state、已知事实、矛盾或缺口、期望收口条件。宿主无法维持可继续对话的 subagent 时，报告 blocker，不扩展成新的协调系统。
3. slow path 返回结构化对账结果、修复建议和 focused validation；主 thread 复核后，直接执行接受的 CLI/文档写入。最小输入可以沿用：

   ```text
   更新：
   结论/事实：<要记录什么>
   依据：<必要时提供>
   依赖：是 | 否
   ```

   不需要为 slow path 建立新的消息协议；package、Attempt、相关 artifact 和命令由主 thread 与 bookkeeper 结合当前状态定位。
4. `依赖：是` 只表示下一动作确实需要 slow-path 结果，主 thread 才等待回执；`依赖：否` 时可以继续推进，稍后消费回执。日常 CLI 写入不因 bookkeeper 的依赖语义停顿。
5. 检查回执中的理解、对账结果、修复建议和 focused validation；内容不对时发送 correction event，仍由 slow path 修正。主 thread 负责执行最终接受的物理写入。
6. 每次 slow-path 回执由 bookkeeper 追加一行到 `<package>/execution/<attempt>/bookkeeper-receipts.jsonl`。正常 CLI 写入不追加该文件；主 thread 需要回顾异常处理历史时读它，不依赖聊天记录。

## 物理写入边界

- Decision、Spec、`contract-design.md`、Plan、Ticket、Progress、Execution Record、active checkpoint、execution findings 和 Gate 的日常物理写入由对应 owning stage 的主 thread 执行；slow path 只提供异常对账和修复输入，不成为第二个 state writer。
- runtime state 继续优先通过现有 `impl_package_state.py` 语义命令更新。bookkeeper 不复制 state schema、另建 ledger 或引入并发协调设施。
- stable-doc backfill 继续由 `/impl-package:backfill-stable-docs` 的 owning workflow 管理，不纳入日常 package 簿记。

## 角色参考

绑定的 standing subagent 只在需要执行写入、验证和回执时读取 [`references/role.md`](references/role.md)。主 thread 只需保留本页的事件、依赖和回执边界。

## 完成条件

一次 slow-path 更新只有在 bookkeeper 已完成异常对账、返回结构化修复输入、运行适用的 focused validation，且主 thread 已复核并执行接受的写入后，才可被采信；回执失败或信息不足时保持未完成并报告具体 blocker。
