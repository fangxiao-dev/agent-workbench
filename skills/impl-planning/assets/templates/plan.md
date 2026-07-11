# [主题] Implementation Plan

状态：draft | owner-approved
创建：
Spec：[spec.md](spec.md)
Routing：new implementation | post-gate patch/follow-up
来源：
Composition: tickets=<true|false>, dag=<true|false>（从已过门 spec 只读）
Plan form：no-ticket executable checklist | no-ticket DAG contract | tickets-only acceptance | tickets+dag cross-slice contract
Granularity：repo-local executable checklist | micro-step fallback | N/A — task decomposition outside plan
原因：<仅 tickets=false, dag=false 填写；其他 Composition 填 N/A>

> `Composition:` 的事实源仅为 `spec.md`。本文件记录其消费结果，不得独立改写或
> 作为第二个可写 composition/state 来源。适用的共享规则见
> [Impl-Package Composition Contract](../../skill-design/references/impl-package-composition-contract.md)。

## Summary

## Inputs Used

- Spec（含修订版本与两道 PASSED gate）：
- 稳定文档（PRD / design / ARD）：
- 既有实现上下文（design.md、既往 plan、handoff）：
- Code facts：
- 验证文档：

## When tickets=false: Executable Checklist

<!-- 仅当 dag=false 使用本节。dag=true 时删除本节；task decomposition 由 dag.md 承载。 -->

- 不 earn tickets 的理由：

### Existing Plan / Spec Adoption

<!-- 中途接入既有 plan/spec 时填写；全新计划标 N/A。tickets=true 时删除本节。 -->

- 原 plan/spec 来源：
- Adoption 方式：[迁入本文件或 spec.md / 链接为内容来源 / 从 handoff 摘要]
- 旧路径处理：[原地保留 / 已建索引 / 稍后归档]

### Files To Modify Or Create

<!-- 仅无 tickets、无 DAG 的 executable checklist 使用；dag=true 的文件级执行分解归 dag.md。 -->

### T<n>: [任务名]

- contributes-to: spec:AC-<n>
- enables: spec:AC-<n> <!-- 仅基础设施任务；不能只写 enables 而不指向最终 AC -->
- seam: none
- [ ] [test-first / verification-first 步骤，含命令与预期结果]
- [ ] [实现步骤]
- [ ] [聚焦验证命令与预期结果]

<!-- 无 DAG task 不得写 seam execution owner。每个 target 必须存在于 spec 的 Acceptance Semantics。 -->

## When tickets=false and dag=true: DAG Handoff

<!-- 仅当 dag=true 使用本节。plan 不含 task checklist 或 task 状态。 -->

- DAG 必要性（非平凡依赖 / 多 owner / seam 协调）：
- create-task-dag 输入（唯一）：本 plan
- task→AC、execution seam owner 与依赖图的 canonical home：[dag.md](dag.md)
- 无 ticket acceptance 的事实源：spec.md / gate.md：
- 填写下方 Package Engineering Contract；若有 seam，contract、acceptance owner 与
  affected targets 写在 plan，execution owner 仅在 dag.md：

## Package Engineering Contract

<!-- 当且仅当 tickets=true 或 dag=true 时填写；tickets=false, dag=false 时删除本节。
     这是 package 级策略与合同，不能写 task checklist、ticket 正文、worker ownership、
     文件级实现步骤或实时状态。 -->

### Cross-Slice / Execution Strategy

- 适用 Composition：
- delivery / execution 顺序、兼容窗口或 rollout：
- 跨 slice 或执行协调策略：

### Seam Contracts

<!-- plan 是 seam contract 与 acceptance owner 的 home。dag=true 时 execution owner
     只在 dag.md task 中声明；tickets=true, dag=false 时所有 Seam 必须为 none 或 N/A。 -->

| Seam ID（或 none / N/A） | Contract owner | Interface / compatibility contract | Integration and rollback contract | Acceptance owner | Affected acceptance targets | Execution evidence home |
| --- | --- | --- | --- | --- | --- | --- |
| <seam-id / none / N/A> | <plan owner or named owner> |  |  |  |  | `dag.md` task（仅 dag=true）/ N/A |

### Migration / Rollback

- 迁移策略：
- 兼容 / rollback 边界：
- 数据或外部副作用的补偿策略：

### Verification Policy

- 全局验证命令与预期结果：
- 跨 slice / seam 验证证据：
- 每个 acceptance target 的 producer 或人工验证 owner 已在 ticket / dag / spec 中声明：

### Global Constraints

- 不变量、禁止事项、性能 / 安全 / 兼容性边界：
- owner decisions / external gates：

## When tickets=true: Ticketed Plan Branches

<!-- 仅当 tickets=true 使用本节。删除两种 no-ticket 分支。此处不得复制 ticket 正文、AC 清单、worker ownership、文件级实现步骤或实时状态。 -->

### Ticket Composition Decision

- Earn 理由（至少两个可独立验收 slice）：
- Creation order：plan → to-tickets draft → cross-check plan
- Draft 输出：`tickets/`：
- Cross-check 发现及回修：

## When tickets=true, dag=false: Ticket-Only Acceptance

<!-- tickets-only：本分支只保留 ticket AC evidence 与验收状态信息。 -->

- ticket 文件是 AC evidence 与验收状态的事实源：
- 每个 ticket 的 AC-level evidence plan 或命名人工验证 owner：
- ticket 状态更新与关闭证据：
- 填写上述 Package Engineering Contract 的策略、验证、rollback 与 constraints；
  Seam: none | N/A，且不声明 execution seam owner：

## When tickets=true, dag=true: Ticketed DAG Handoff

<!-- tickets+dag：只将相关 approved tickets 子集交给 DAG；plan 保持 task-free。 -->

- create-task-dag 输入（唯一）：本 plan + 相关 approved tickets 子集：

## Composition Migration

<!-- 仅在 req-align 修订 Composition 并重新通过两道 gate 后填写；无升级标 N/A。不得创建 per-ticket patch。 -->

- Previous: tickets=<true|false>, dag=<true|false>
- New: tickets=<true|false>, dag=<true|false>
- Reason and date:
- Content moved to canonical home:
- Relocation pointer left at:
- Fact-source / dependency / AC-coverage verification:

## Patch Delta

<!-- 仅 post-gate patch plan 使用；新 implementation 请删除本节。 -->

- 实现的 spec 修订：
- 相对已实现行为的 delta：
- 原有验收语义的回归检查：
- Package gate closed evidence：
