---
name: impl-planning
description: >
  当已有批准的 Design/Spec 输入，需要创建 initial plan、patch plan、Composition decision、
  execution strategy 或 verification plan 时使用；不维护长期 behavior contract 或 task runtime status。
---

# Impl Planning

为一个 implementation attempt 创建可追溯的过程计划。design/spec 是活动变更的当前 SoT；plan 只消费它们，并决定本次 attempt 的 tickets/DAG 形态、执行顺序与验证路径。

共享 artifact lifecycle、Composition、gate 与 Stage 7 语义只引用 `../references/impl-package-composition-contract.md`。

## 输出

~~~text
docs/implementations/<package-id>/
  .impl-package/revision-bindings.json        # internal machine sidecar; not an owner-facing deliverable
  plan.md                                    # initial attempt
  YYYYMMDD-HHMM-<patch-topic>.patch-plan.md  # post-gate patch attempt
~~~

每个 plan 必须声明：

~~~text
Attempt ID: <initial | patch-id>
Design Revision: D<n>
Spec Revision: S<n>
Plan Revision: P<n>
Composition: tickets=<true|false>, dag=<true|false>
~~~

Composition 是当前 plan 的事实，不从 spec 或历史 attempt 继承。plan header 只保存 revision alias；批准当前 plan 时，以 [`../assets/templates/revision-bindings.json`](../assets/templates/revision-bindings.json) 为形状，在内部 sidecar 选择 current attempt 并绑定最终 plan blob。sidecar 只供机器校验；plan 与 handoff Markdown 必须直接呈现 owner 所需结论。

## 边界

- 不创建或重写 design/spec。发现行为或设计 drift 时路由 req-align，等待所需 gate 通过。
- 不把 interface、seam contract、compatibility、全局约束或 Acceptance Semantics 复制进 plan；这些属于 spec。选择 rationale 属于 design。
- 不把 plan 写成逐行实现脚本：不复制完整 production code、不要求 2–5 分钟微步骤，也不内嵌每一步 commit 指令。plan 应约束实施方向和可验证边界，同时允许执行者基于当前代码完成局部判断。
- 不在 plan 保存 task checklist、task/ticket runtime status、worker ownership 或通用验证模板副本。
- 实际验证过程可 append 到 Execution Record；terminal gate verdict 后 plan 冻结。
- plan 不保存 `Status`。Draft/Active/Frozen 由内部 sidecar 的 current selection 与 gate ledger 派生。
- tickets 由 to-tickets 拥有，DAG 由 create-task-dag 拥有，progress/findings/gate ledger 由 dev-with-track 拥有。

## Routing

1. package 尚未 terminal：继续当前 attempt，按需修订当前 plan 的 P revision；不要创建 patch plan。
2. package 已有 terminal gate，新需求或修复进入 post-gate patch：复用 package-id，创建新的 Attempt ID 与 patch plan。
3. 重新 patch 前先确认 req-align 已将 package design/spec 与当前 module knowledge/code 对账。
4. 两个 owning package 都合理时暂停并请求 owner 选择，不能另建重复 package。

## Composition

对当前 attempt 独立判断：

- tickets=true：至少两个值得独立跟踪验收结论的 delivery slice。
- dag=true：需要显式依赖图、多个 execution owner、cohort 或 execution seam。
- 两者都 false：不创建 task artifact；简单执行不通过 plan checklist制造状态。需要跨 session 恢复、独立交接或外部 gate 时，由 dev-with-track 按触发条件创建 progress ledger。

用户可主动用 S/M/L/D 指定期望组合。把它记录为 Composition request 并展开成本 attempt 的 tickets/dag；一致时接受。若与 earn conditions 冲突，在增删任何 ticket/DAG 前向 owner 报告请求、实际信号、建议组合和 artifact 影响，并把选择列为 owner decision，不能静默修正。活动 attempt 只有 owner 接受后才升级 P revision 和迁移 artifact。

plan 活动期间发现 Composition 判断错误时：

1. 升级 Plan Revision。
2. 记录 previous/new、原因、artifact relocation 与引用校验。
3. 创建或退休当前 attempt 的 ticket/DAG 状态来源。
4. 不修改 D/S revision，除非同时发现 contract drift。
5. 不保留两个可写 execution-state source。

## Plan 内容

### Coverage And Change Map

- 为 spec 的每项 Acceptance Semantics 指明对应的 Execution Strategy 与 Planned Verification 落点；使用引用或稳定标识，不复制 spec 正文。
- 列出预计创建、修改或移除的模块/文件及其责任，并标明关键依赖顺序和集成点。文件清单是实施地图，不伪造尚未确认的行号或代码细节。
- 标出迁移、兼容、rollout、rollback 和高风险步骤；需要 owner 决策的事项必须在执行前解决，不能用 `TBD`、`TODO` 或“稍后处理”占位。
- plan 中使用的模块名、类型名、路径和术语必须与当前 spec、仓库事实及既有代码一致；发现不一致时先判断是 plan 错误还是 contract drift。

### Execution Strategy

只记录本 attempt 的实施顺序、模块/文件责任、具体迁移操作、集成动作与回滚操作。执行单元应足以独立交付或验证，但不展开成机械微步骤。稳定 interface、seam、compatibility 与约束必须先进入 spec。

默认声明 `gate-before-merge`。若 owner 明确要求先合入再完成 gate，记录 target branch、`owner-approved pre-gate integration` 与决策证据；这只授权 integration order，不把 attempt 标为 closed。目标分支包含 comparison point 且尚无 terminal gate 时，对外状态派生为 `Integrated, gate open`，最终 pass/closed verification 必须在目标分支完成。

### Planned Verification

- 引用权威 test/review policy。
- 将 Acceptance Semantics 映射到本次要运行的检查、预期结果和 evidence owner；命令只有在仓库中可确认时才写成精确命令。
- 不复制 Data Safety、UI Evidence、Real Route Safety 等通用 checklist。

### Execution Record

- 每次实际检查追加一个稳定 entry anchor，例如 ER-1、ER-2。
- 记录 D/S/P revision、时间、命令或检查、结果、证据路径和残余风险。
- 旧 entry 不回改；补证新增 entry。
- 这不是 task runtime status，也不替代 ticket/DAG/progress。

### Revision History

记录 plan strategy、Composition 或 verification selection 的修订。每次 P revision 发布时在内部 sidecar 追加新的 plan blob binding，旧 binding 保留。terminal gate 后不得再改；后续变化创建新 patch attempt。

## Workflow

1. 读取当前 design/spec revision、gate ledger 最新 entry、module knowledge/code 对账结果与仓库验证政策。
2. 确认需要的 Design/Spec Gate 已通过；实现-only drift 允许复用现有 D/S。
3. 分配 Attempt ID 与 P1，独立决定 Composition；plan 尚未被 registry 的 `current.attempt` 选中时，其 lifecycle 派生为 Draft。
4. 建立 spec coverage 与 change map，写 Execution Strategy、integration order、Planned Verification、rollout/rollback 与依赖的 policy 链接；清除 blocker placeholder，核对术语、模块与路径一致性。
5. tickets=true 时调用 to-tickets draft；dag=true 时在必要输入齐备后调用 create-task-dag。
6. 交叉检查 ticket/DAG 暴露的 contract 缺口；规范性缺口回 req-align，过程策略缺口升级 P revision。
7. owner 批准 plan 后，计算最终 plan Git blob OID，在内部 revision-binding sidecar 以 `plan-contract-v1` 追加 baseline binding并选择 `current.attempt`；commit 后复核 baseline。后续只允许 ER append，不因此升级 P revision；此时且无 terminal gate 时 lifecycle 派生为 Active。
8. 执行期间只 append Execution Record；状态由对应 artifact 维护。
9. gate evaluation 由 dev-with-track 在 gate.md 顶部插入摘要，并链接对应 Execution Record；terminal verdict 使 lifecycle 派生为 Frozen。

## Review Checklist

- Attempt ID、D/S/P revision 与 Composition 唯一且可解析。
- 内部 revision-binding sidecar 对 current plan 的 alias/path/blob 绑定唯一且可机械复核；plan 自身不记录自身 hash，且不要求 owner 打开 sidecar 才能理解当前状态。
- 每项 Acceptance Semantics 都能定位到 Execution Strategy 与 Planned Verification；不存在覆盖缺口或 `TBD`/`TODO` blocker。
- change map 给出预计模块/文件责任、依赖顺序和集成点，且没有伪造行号、复制完整实现代码或机械微步骤。
- plan 中的模块名、类型名、路径和术语与当前 spec 及仓库事实一致。
- plan 未复制 design/spec contract、ticket 正文、task 状态或通用 checklist。
- 每个长期 seam/interface/constraint 都能在 spec 找到。
- Planned Verification 引用权威 policy；Execution Record 使用稳定 anchor 且 append-only。
- Composition 与当前 attempt earned artifacts 一致，无双重状态来源。
- plan 无手工 `Status`；Draft/Active/Frozen 与 `Integrated, gate open` 均能从 registry、gate 和 target branch 事实派生。
- terminal gate 后 plan 已冻结。

## Output Contract

向 owner 汇报时使用 `talk-to-boss`：说明本次实现范围、计划阶段是否完成、为何需要或不需要交付切片/执行图、剩余决策，以及能否进入执行。若用户主动指定 S/M/L/D，先用人话说明是否接受及任何冲突。

随后附 canonical handoff：package-id、Attempt ID、D/S/P revision set、binding validation 结论、派生 lifecycle、Composition、plan 路径、integration order、tickets/DAG 路由、选定 verification policy 与剩余 owner decision。正文不得要求 owner 打开 JSON；内部 sidecar 路径只可放 machine audit metadata。
