# [实施名称] 任务 DAG

> 仅当 `Composition: ..., dag=true` 时创建本产物。字段语义、就绪规则与校验要求由共享的 [Impl-Package Composition Contract](../../../skills/impl-package/references/impl-package-composition-contract.md) 定义。

状态：[PENDING / READY / RUNNING / NEEDS_SEAM / BLOCKED / FAILED / NEEDS-REVALIDATION / DONE / WAIVED / SUPERSEDED / RETIRED]
创建日期：[YYYY-MM-DD]
执行尝试 ID（Attempt ID）：
计划修订（Plan Revision）：P<n>
<!-- plan 升级到更新的 P 号后，本 DAG 若仍标着旧 P 号，视为 NEEDS-REVALIDATION。先按 P delta 定位受影响节点；未受影响节点可批量确认后机械更新本字段，不重画整张 DAG。 -->
规格：[spec.md](spec.md)
计划：[当前执行尝试计划](<plan-path>)
发现记录：[findings.md](findings.md)
门禁：[gate.md](gate.md)

`dag.md` 仅在 DAG 确实 earned 时作为 task contract、依赖与 ownership 的规范来源；task/ticket current state 与最后一次 evidence pointer 的机器事实源是 `.impl-package/runtime-state.json`。如果同时 earned tickets，下文状态只能是 machine-owned 只读投影。

## 合同引用

- 共享组合合同：[impl-package-composition-contract.md](../../../skills/impl-package/references/impl-package-composition-contract.md)
- Spec 修订与 seam ID：
- [DTO / route prop / 外部 smoke 协议来源]

## 任务记录

### T1：[任务标题]

- 依赖：[Tn / 无]
- 文档顺序：[数字]
- Owner：[主会话 / 具名 owner]
- 运行时状态与证据：见下方 machine-owned DAG 看板。
- 完成条件：[具体证据]
- 贡献目标（contributes-to）：[<ticket-id>:<AC-id> / spec:<AC-id>]
- 解锁目标（enables）：[<acceptance-target> / 无]
- 执行 seam：[无 / <seam-id>]
- seam 执行 owner：[主会话 / 具名 owner；仅当 seam 为无时可填 `none`]
- 进度账本：[tasks/T1-progress.md / N/A]

`contributes-to`、`enables` 和 seam 字段必须按共享合同校验；不要在此复制 spec 中的 seam 合同或验收 owner。

## DAG 看板

<!-- impl-package:projection runtime-state begin -->
| Task | State | Evidence |
| --- | --- | --- |
| T1 | PENDING | dag.md#T1 |
<!-- impl-package:projection runtime-state end -->

## Ticket 状态投影（仅 tickets=true）

> 这里只做投影。ticket 文件保存 Acceptance Semantics，current state/evidence 由 `.impl-package/runtime-state.json` 维护并投影，禁止手工在本表或 ticket marker 中改状态。

| Ticket | 验收来源 | 执行视图投影 | 最后检查时间 |
| --- | --- | --- | --- |
| [ticket-id] | [tickets/<ticket>.md](tickets/<ticket>.md) | [状态] | [YYYY-MM-DD] |

## 验证门（Verification Gates）

<!-- 只记录 task/DAG 特有的前置条件与到 plan Planned Verification 的指针；不要复制通用 policy checklist。 -->

- Plan 验证来源：[当前执行尝试计划](<plan-path>#planned-verification)
- Task/DAG 特有前置条件或外部门禁：

## 校验与最后更新

- [ ] 所有 `Depends on` 引用均可解析，且任务图无环。
- [ ] 每个任务验收目标都能解析到 ticket/spec AC。
- [ ] 每个 execution seam 都有对应的 spec seam 合同和执行 owner。
- [YYYY-MM-DD] [有意义的状态/证据/重新校验变化]
