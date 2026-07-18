# Task DAG

> 仅当 `Composition: ..., dag=true` 时创建。本文件是计划拆解 bundle 的 DAG 部分，描述 Task 的执行依赖；Ticket 仍是独立、纵向验收单位。它不设置独立 approval 门，必须与当前 earned Ticket 集合（如有）联合校验和 review。字段语义与 runtime state 见 [Impl-Package Composition Contract](../../../references/impl-package-composition-contract.md)。

Integration responsibility: Working Branch owner

创建日期：[YYYY-MM-DD]
执行尝试 ID（Attempt ID）：
计划修订（Plan Revision）：P<n>
规格：[spec.md](spec.md)
计划：[当前执行尝试计划](<plan-path>)

Plan Revision 前进后，仍声明旧 P 号的 DAG 为 `NEEDS-REVALIDATION`；先按实际 delta 判断受影响节点，定向修订或验证，未受影响节点可批量确认并机械更新引用，不默认重建整张图。

## Task graph

| Task | Primary ownership | Known depends on | Contributes to tickets | Known seam / risk |
| --- | --- | --- | --- | --- |
| T1 | [模块、目录或共享 seam] | none | [TKT-01] | [已知风险或 none] |

只记录已知且确定的依赖。Task 可以贡献多个 Ticket，一个 Ticket 也可由多个 Task 支撑；这不是父子关系。不要预先列尽文件、consumer、失败模式或完整合同。实际出现共享 seam 时，在相关 Task 的 blocker/progress 中记录，或新增/调整普通 Task；不新增状态或实体。

## Runtime projection

`PENDING`、`RUNNING`、`DONE`、`BLOCKED` 是日常 Task 状态。`DONE` 仅表示产出与局部证据可交给 Working Branch owner 集成，不表示 Ticket accepted。`BLOCKED` 必须有一句原因和受影响 Ticket（如有）。`WAIVED` / `SUPERSEDED` 仅在 package 最终收口时，凭已有批准的理由和影响说明使用。

<!-- impl-package:projection runtime-state begin -->
| 任务 | 状态 | 证据 |
| --- | --- | --- |
| T1 | PENDING | dag.md#task-graph |
<!-- impl-package:projection runtime-state end -->

## Joint decomposition review and integration

Ticket 与 DAG 在此 attempt、P revision 和完整 earned artifact 集合上联合 review。联合校验至少覆盖 Ticket/Spec coverage、typed dependency 与 Task dependency、primary ownership/contribution、AC evidence feasibility、gate/preflight 边界和 revision binding；校验未通过时保持计划拆解 `drafting`，不进入 Ticket publish 或 execution。

实质修改 Ticket acceptance boundary、typed edge、planned evidence、Task contribution、ownership、执行顺序或 gate 后，当前 bundle approval 失效，按影响范围修订 Ticket/DAG 并重新 review。纯引用、格式、分类或 machine projection 修正不触发重新审批。

## Integration and acceptance

Working Branch owner 在并行 Task 返回、发生 `BLOCKED` 或 Ticket 最终验收前：合并 Task 产出，处理已出现的 seam/冲突，运行共享验证和正式 review，将证据映射回 Ticket AC，并决定 Ticket 是否可验收。

Ticket 最终验收前只扫描贡献该 Ticket 的 `BLOCKED` Task。若 blocker 影响其 AC、已声明行为或风险边界，该 Ticket 不可通过；若影响扩大，先更新 contribution mapping。最终 package review 前，全局确认没有 `BLOCKED`，且所有 Task 为 `DONE` 或有批准理由的 `WAIVED` / `SUPERSEDED`。
