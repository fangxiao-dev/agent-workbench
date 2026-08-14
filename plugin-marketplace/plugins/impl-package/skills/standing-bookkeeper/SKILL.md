---
name: standing-bookkeeper
description: 当一个 Implementation Package thread 需要初始化或恢复与其一一绑定的 standing bookkeeper，或把主 thread 已作出的事实/结论交给它写入 package artifact、更新运行状态并验证时使用；触及 Decision/Spec/Plan/Ticket、Progress、Execution Record、checkpoint 或 Gate 的物理写入时优先使用。
---

# Standing Bookkeeper

这是 package thread 的薄入口。它把已作出的判断和已发生的事实交给绑定的 standing bookkeeper 执行物理写入；它不改变 Impl-Package 的语义 owner、状态机或验收门。

## 绑定关系

- 一个 package 绑定一个主 thread 和一个 standing bookkeeper。
- 主 thread 保留 requirement、architecture、implementation direction、acceptance、finding disposition、Gate verdict 和最终复核权。
- standing bookkeeper 独占该 package 文档与状态的物理写入，并按 owning stage 规则定位 artifact、写入和验证。
- bookkeeper 不修改业务实现代码，不服务其他 package，不接管 commit、merge、push、release 或外部 mutation。

## 主 thread 流程

1. 在 package thread 开始或第一次需要 package 写入时，确认是否已有绑定的 bookkeeper；恢复时让它从 package canonical state 和当前规则重新建立上下文。宿主无法维持可继续对话的 subagent 时，报告 blocker，不扩展成新的协调系统。
2. 用普通自然语言报告已经发生的事实或已经作出的结论。最小信息为：

   ```text
   更新：
   结论/事实：<要记录什么>
   依据：<必要时提供>
   依赖：是 | 否
   ```

   不需要为 bookkeeper 建立独立消息协议；package、Attempt、目标 artifact 和命令由绑定角色结合当前状态定位。
3. `依赖：是` 时，下一动作需要本次写入结果，等待 bookkeeper 回执；`依赖：否` 时，主 thread 可以继续推进，稍后消费回执。不要把这两个选项扩展成预先固定的依赖判定表。
4. 检查回执中的理解、实际写入和 focused validation。内容不对时继续发送 correction event，仍由 bookkeeper 修正；主 thread 不直接编辑当前 package artifact。

## 物理写入边界

- Decision、Spec、`contract-design.md`、Plan、Ticket、Progress、Execution Record、active checkpoint、execution findings 和 Gate 的物理写入由 bookkeeper 执行；语义结论仍由对应 owning stage 和主 thread 持有。
- runtime state 优先通过现有 `impl_package_state.py` 语义命令更新。bookkeeper 不复制 state schema、另建 ledger 或引入并发协调设施。
- stable-doc backfill 继续由 `/impl-package:backfill-stable-docs` 的 owning workflow 管理，不纳入日常 package 簿记。

## 角色参考

绑定的 standing subagent 只在需要执行写入、验证和回执时读取 [`references/role.md`](references/role.md)。主 thread 只需保留本页的事件、依赖和回执边界。

## 完成条件

一次更新只有在 bookkeeper 已定位正确 artifact、完成授权范围内的物理写入、运行适用的 focused validation 并返回简短回执后，才可被主 thread 采信；回执失败或信息不足时保持未完成并报告具体 blocker。
