---
name: dev-with-track
description: >
  Impl-Package 体系的执行与 gate 阶段：当已批准 attempt 需要恢复执行现场、判定下一可执行单元、记录验证证据、处理返工失效、分流 findings 或写入 append-only gate ledger 时使用。不拥有 design/spec/plan/ticket/DAG 的定义。
---

# Dev With Track

执行并恢复 docs/implementations/<package-id>/ 中的当前 attempt。共享 artifact lifecycle、Composition、readiness 与 gate 语义只引用 `../references/impl-package-composition-contract.md`。

## Ownership

- req-align 拥有活动 design/spec SoT 与 D/S Gate。
- impl-planning 拥有当前 attempt plan、P revision、Composition、Planned Verification 与 Execution Record 结构。
- to-tickets 拥有 ticket definition/publication；create-task-dag 拥有 DAG contract。
- 本 skill 维护 ticket/DAG/progress runtime state、findings 分流、plan Execution Record 的证据追加，以及 gate.md 的 newest-first entry。

本 skill 不重写长期 contract，不从历史 Composition 推断当前 attempt，也不修改旧 gate entry。

## Restore

1. 读取仓库规则、当前 design/spec revision、所有 attempt plans、gate.md 最新 entry、当前 attempt 的 tickets/DAG/progress、findings 与实际证据。
2. 选择唯一未被 terminal gate 冻结的 attempt；若不存在 active attempt，停止并路由 impl-planning 创建 patch；若同时存在多个 active attempt，报告 lifecycle violation 并停止，不能按时间猜一个。
3. 从当前 plan 读取 Attempt ID、D/S/P revision 与 Composition，校验 artifact 一致。对 design.md/spec.md/plan.md 各自重新计算 `git log -1 --format=%H -- <path>`，与正文头部声明的 revision 绑定的 commit SHA 比对；不符时该 revision 号已和内容脱节，按 impl-package-composition-contract.md §2 处理为未分类 drift，不得当作可信 revision 继续读取。
4. reconcile 状态与证据；evidence 胜过 stale status。逐个比对每个 earned ticket/DAG 声明的 Plan Revision 与当前 plan 的 P 号；不一致的标 NEEDS-REVALIDATION，不当作可用状态。
5. 是新 attempt（尤其重新激活已关闭 package）时，先完成 Module Knowledge Watermark 对账：重新计算 watermark 文件当前 commit SHA，与上一 attempt 记录的 watermark 比对，不符先 diff 确认 design/spec 是否仍成立。
6. 校验 typed ticket edges、DAG Depends on、AC references 与 cycles。
7. 执行 readiness resolution，按文档顺序选择第一个 actionable unit；不自动派工。

## Current attempt state

- tickets=false, dag=false：没有 task artifact。需要跨 session 恢复、独立交接、外部 gate、blocker 或大量局部证据时，创建 `tasks/<attempt-id>-progress.md`（Kind=attempt）；不向 plan 加 task checklist或伪造 task/ticket。
- tickets=true, dag=false：ticket Runtime Acceptance Status 是 acceptance state；whole-ticket 恢复/交接触发时才创建 `tasks/<ticket-id>-progress.md`，且不得复制验收结论。
- dag=true：当前 attempt DAG 是 task runtime state；ticketed attempt 的 ticket acceptance 仍在 ticket。
- plan Execution Record 保存实际验证过程，不保存 task/ticket status。

返工上游输出时，将依赖 task/evidence 标为 NEEDS-REVALIDATION。DONE 只有在 Done when 证据记录后才释放依赖；WAIVED/SUPERSEDED 需要替代证据和 impact note。

## Verification record

按 plan Planned Verification 和权威 policy 执行检查。每次实际检查在当前 plan 的 Execution Record 末尾追加稳定 ER-n entry，记录 D/S/P revision、时间、命令/检查、结果、证据路径与残余风险。不得修改旧 ER entry，也不得把通用 checklist 复制到 plan。

## Findings curation

gate evaluation 前逐项分流 findings：

- 设计选择/rationale → req-align 更新 design revision；
- 行为、接口、失败恢复、约束或 Acceptance Semantics → req-align 更新 spec revision；
- 长期项目知识 → 当前 gate entry Durable Deltas 与 _pending.md；
- 验证证据 → plan Execution Record；
- 其余已验证调查事实/风险 → 保留 findings。

存在未完成的规范性分流时不能写任何 terminal entry（pass/fail/defer，不只 pass）；blocked entry 不受此约束。

## Append-only gate ledger

package 只使用 gate.md。每次 evaluation 在 # Gate Ledger 标题之后插入最新 entry；旧 entry 不修改。

entry ID 为 <attempt-id>-G<n>，同 attempt 从 G1 取已有最大编号加一且不复用。entry 必须包含 Attempt ID、Supersedes、evaluated time、D/S/P revision（各带 commit SHA）、Composition、comparison point、一个或多个 plan ER anchor、blocker/deferred item、verdict reason 与 Durable Deltas。

- blocked 后补证：保留旧 blocked entry，新增 G<n+1> 并 Supersedes 旧 entry。
- pass/fail/defer：terminal，冻结对应 plan。
- blocked：不冻结 plan；后续策略/证据变化升级 P revision并 append ER/gate entry。
- D/S revision 改变后，旧 gate entry 仍只证明旧 revision；新 evaluation 必须引用新 revision。
- Git 提供 provenance；发现旧 block 被改动时报告 contract violation，不静默接受。

## Stage 7

每个 gate entry 的 Durable Deltas 是唯一 capture surface。有 delta 时，terminal verdict（pass/fail/defer）entry 写入前完成：

1. gate entry 写完整 delta fields；
2. _pending.md 使用 <destination>|<delta-id> 注册；
3. 受影响 module spec 写 Pending deltas truth pointer；
4. 缺失 target module spec 时先建 stub。

无 durable delta 时写 none 和理由。写入 terminal entry 时先保留 G id、固定 comparison point/ER anchor、完成 Stage 7，再一次性插入不可变 entry；blocked capture gap 通过后续 entry 补齐，不回改旧 entry。gate 关闭后，module knowledge 与 `_pending.md` truth pointer 共同表达当前长期真相和待压实增量。

terminal gate 关闭后提示 owner 可以按需使用 `backfill-stable-docs`，但不自动调用、不阻塞当前交付，也不把它列为本次任务的剩余 blocker。report/apply 可以延期；只有用户明确要求、已有维护计划或进入周期维护流程时才执行，apply 仍需 owner 批准具体 report item。

## Execution checklist

1. Restore 当前 attempt 与 revisions。
2. 校验 Composition/artifacts、dependency graph 与 AC references。
3. 选择并执行 actionable unit；状态只写对应 runtime artifact。
4. append plan Execution Record。
5. 分流 findings；必要时回 req-align 并重新过相应 gate。
6. 运行 review/verification，固定 comparison point。
7. 保留下一个 G id；terminal verdict 先完成 Stage 7，再在 gate.md 顶部一次性插入新 entry。
8. terminal 时冻结 plan；blocked 时保留 attempt active。

## Output

先遵循 [Owner-Facing Reporting Contract](../references/owner-facing-reporting.md)：首段说明本次功能范围、实施/验证/gate 各自完成到哪、剩余 blocker 数量、整体是否 closed，以及当前需要 owner 决定什么。主体按功能 slice 说明已经支持和仍未证明的行为。

随后附 canonical handoff：package/Attempt ID、D/S/P revision、Composition、当前状态源、execution evidence、findings 分流、最新 gate entry/verdict、Supersedes 链与 Stage 7。terminal gate 已关闭时，另以非阻塞 follow-up 提示可选 backfill；不要把提示写成未完成 gate。
