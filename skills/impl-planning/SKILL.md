---
name: impl-planning
description: >
  Impl-Package 体系的 attempt planning 阶段：当已通过所需 Design/Spec Gate 的变更需要初始 plan、patch plan、Composition、执行策略或验证计划时使用。不维护长期行为合同，也不维护 task runtime status。
---

# Impl Planning

为一个 implementation attempt 创建可追溯的过程计划。design/spec 是活动变更的当前 SoT；plan 只消费它们，并决定本次 attempt 的 tickets/DAG 形态、执行顺序与验证路径。

共享 artifact lifecycle、Composition、gate 与 Stage 7 语义只引用 ../impl-package/references/impl-package-composition-contract.md。

## 输出

~~~text
docs/implementations/<package-id>/
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

Composition 是当前 plan 的事实，不从 spec 或历史 attempt 继承。

## 边界

- 不创建或重写 design/spec。发现行为或设计 drift 时路由 req-align，等待所需 gate 通过。
- 不把 interface、seam contract、compatibility、全局约束或 Acceptance Semantics 复制进 plan；这些属于 spec。选择 rationale 属于 design。
- 不在 plan 保存 task checklist、task/ticket runtime status、worker ownership 或通用验证模板副本。
- 实际验证过程可 append 到 Execution Record；terminal gate verdict 后 plan 冻结。
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

可接受 S/M/L/D shorthand，但只展开成本 attempt 的 tickets/dag；earn condition 冲突时修正 shorthand。

plan 活动期间发现 Composition 判断错误时：

1. 升级 Plan Revision。
2. 记录 previous/new、原因、artifact relocation 与引用校验。
3. 创建或退休当前 attempt 的 ticket/DAG 状态来源。
4. 不修改 D/S revision，除非同时发现 contract drift。
5. 不保留两个可写 execution-state source。

## Plan 内容

### Execution Strategy

只记录本 attempt 的实施顺序、具体迁移操作、集成动作与回滚操作。稳定 interface、seam、compatibility 与约束必须先进入 spec。

### Planned Verification

- 引用权威 test/review policy。
- 选择本次要运行的检查、预期结果和 evidence owner。
- 不复制 Data Safety、UI Evidence、Real Route Safety 等通用 checklist。

### Execution Record

- 每次实际检查追加一个稳定 entry anchor，例如 ER-1、ER-2。
- 记录 D/S/P revision、时间、命令或检查、结果、证据路径和残余风险。
- 旧 entry 不回改；补证新增 entry。
- 这不是 task runtime status，也不替代 ticket/DAG/progress。

### Revision History

记录 plan strategy、Composition 或 verification selection 的修订。terminal gate 后不得再改；后续变化创建新 patch attempt。

## Workflow

1. 读取当前 design/spec revision、gate ledger 最新 entry、module knowledge/code 对账结果与仓库验证政策。
2. 确认需要的 Design/Spec Gate 已通过；实现-only drift 允许复用现有 D/S。
3. 分配 Attempt ID 与 P1，独立决定 Composition。
4. 写 Execution Strategy、Planned Verification、rollout/rollback 与依赖的 policy 链接。
5. tickets=true 时调用 to-tickets draft；dag=true 时在必要输入齐备后调用 create-task-dag。
6. 交叉检查 ticket/DAG 暴露的 contract 缺口；规范性缺口回 req-align，过程策略缺口升级 P revision。
7. 执行期间只 append Execution Record；状态由对应 artifact 维护。
8. gate evaluation 由 dev-with-track 在 gate.md 顶部插入摘要，并链接对应 Execution Record。

## Review Checklist

- Attempt ID、D/S/P revision 与 Composition 唯一且可解析。
- plan 未复制 design/spec contract、ticket 正文、task 状态或通用 checklist。
- 每个长期 seam/interface/constraint 都能在 spec 找到。
- Planned Verification 引用权威 policy；Execution Record 使用稳定 anchor 且 append-only。
- Composition 与当前 attempt earned artifacts 一致，无双重状态来源。
- terminal gate 后 plan 已冻结。

## Output Contract

返回 package-id、Attempt ID、D/S/P revision、Composition、plan 路径、tickets/DAG 路由、选定 verification policy、剩余 owner decision，以及是否可进入 execution。
