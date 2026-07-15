---
name: dev-with-track
description: >
  当已批准 implementation attempt 需要恢复执行、选择下一 actionable unit、记录 verification
  evidence、处理返工失效、分流 findings 或评估 append-only gate ledger 时使用；不拥有
  design/spec/plan/ticket/DAG 定义。
---

# Dev With Track

执行并恢复 docs/implementations/<package-id>/ 中的当前 attempt。共享 artifact lifecycle、Composition、readiness 与 gate 语义只引用 `../references/impl-package-composition-contract.md`。

## Ownership

- req-align 拥有活动 design/spec SoT 与 D/S Gate。
- impl-planning 拥有当前 attempt plan、P revision、Composition、Planned Verification 与 Execution Record 结构。
- to-tickets 拥有 ticket definition/publication；create-task-dag 拥有 DAG contract。
- 本 skill 维护 ticket/DAG/progress runtime state、findings 分流、plan Execution Record 的证据追加，以及 gate.md 的 newest-first entry。

本 skill 不重写长期 contract，不从历史 Composition 推断当前 attempt，也不修改旧 gate entry。

## Task execution and review routing

本 skill 选择 actionable unit、维护其 runtime state，并拥有 ticket acceptance 的最终入口；它不自行代替 task worker。存在有界且可委派的 implementation task 时，必须调用同体系的 `subagent-driven-development`：该 skill 负责 implementer delegation 和非实现者执行的 task spec-compliance / code-quality review。task review evidence 进入对应 progress/handoff 或当前 ticket evidence，再由本 skill 汇总。

当 ticket 达到验收候选，先固定 comparison point，再自动按以下信号运行正式 review；不能等待 owner 显式点名：

- `code-review`：任何 implementation 恒必做。
- `module-review`：当前 attempt 有 tickets 或 DAG 时必做；无两者但 diff/spec 涉及 interface、状态机、模块边界或 seam 时同样必做。其 Standards 与 Spec 两轴都必须完成。
- `safety-review`：diff 或 spec/plan/DAG 出现 auth、permission、payment、webhook、migration、外部 mutation、数据完整性、并发安全，或 evidence authority / published-state / compatibility-projection / proof-equality 信号时必做。后四类是条件化风险信号，不假定所有项目存在 provider、schema、archive、CLI 或 `current` 指针。

正式 review 的 findings 必须修复并以 closure verification 复核，才可把 ticket Runtime Acceptance Status 记为已满足或进入 gate。

如果当前 spec 激活了 conditional evidence-integrity contract，任务只有在相关 false-PASS 反例和适用的副作用后失败/失效路径已有证据时才能 dependency-release；绿色正向测试本身不能释放该依赖。证据仍写入既有 task/ticket/Execution Record，不创建新的 runtime artifact。

## Completion claim gate

适用的正式 review、findings 分流和 Stage 7 准备完成后，在写入 terminal `pass` entry 前必须调用同体系的 `verification-before-completion`，用拟声明的 pass、当前 revision/worktree/environment 和 plan ER/review/smoke evidence 做 claim-to-evidence 审计。它不是 DAG task，不按 ticket 或 task 重复运行，也不替代既有 review 与验证。

证据完整且仍新鲜时可以复用，不机械重跑全部检查；证据 stale、跨 revision/environment、冲突或不足时，只补跑受影响检查。审计未通过时不得写 pass 或宣称 closed，应报告 `implemented, not verified` 或具体 pending gate。

terminal metadata 后若又发生 commit、合入目标分支或相关环境变化，在对外宣称 complete、closed、merge-ready 或 release-ready 前再次调用 `verification-before-completion`，核对变化是否使既有证据失效。纯 metadata delta 不自动使行为测试失效，但必须验证最终 HEAD、工作树状态和声明所依赖的 metadata/proof。

## Restore

1. 读取仓库规则、内部 `.impl-package/revision-bindings.json` sidecar、所有 attempt plans、gate.md 最新 entry、当前 attempt 的 tickets/DAG/progress、findings 与实际证据。
2. 从 registry 的 `current.attempt` 派生唯一 lifecycle：未被选中的 plan 是 Draft；被选中且没有 terminal gate 的 attempt 是 Active；已有 terminal gate 的 attempt 是 Frozen。若不存在 Active attempt，停止并路由 impl-planning 创建或批准 patch；若 registry/current/gate 组合产生多个 Active attempt，报告 lifecycle violation 并停止，不能按时间猜一个。
3. 从当前 plan 读取 Attempt ID、D/S/P revision 与 Composition，逐项解析 registry binding。design/spec 用 `git rev-parse HEAD:<package-relative-path>` 做 exact-blob 核对；plan 用 binding baseline blob 与 `plan-contract-v1` 比较非 ER 内容，并单独验证 ER append-only。alias/path/mode/blob 不一致、binding 缺失或重复时，按 impl-package-composition-contract.md §2 处理为 P2 capture gap 或未分类 drift，不得把该 revision 当作可信输入。
4. reconcile 状态与证据；evidence 胜过 stale status。逐个比对每个 earned ticket/DAG 声明的 Plan Revision 与当前 plan 的 P 号；不一致的标 NEEDS-REVALIDATION，不当作可用状态。
5. 是新 attempt（尤其重新激活已关闭 package）时，先完成 Module Knowledge Watermark 对账：重新计算 watermark 文件当前 commit SHA，与上一 attempt 记录的 watermark 比对，不符先 diff 确认 design/spec 是否仍成立。
6. 校验 typed ticket edges、DAG Depends on、AC references、显式 cycles 与 readiness satisfiability；若 AC 的 evidence producer task 被同一 ticket acceptance 直接或传递阻塞，按 decomposition/readiness defect 处理。
7. 执行 readiness resolution，按文档顺序选择第一个 actionable unit；不自动派工。

目标分支已包含当前 comparison point、但 attempt 仍为 Active 时，向 owner 报告派生 qualifier `Integrated, gate open`。若 plan 没有 owner-approved pre-gate integration strategy，视为 integration-order violation；即使已有批准，最终 pass/closed evidence 仍必须来自目标分支。

### 计划错误的修复权限

发现 decomposition/readiness defect 时，先判断修正是否改变业务结果。若只涉及 typed edge 分类、task 顺序、evidence producer/owner 投影或 artifact 引用，并保持 D/S、业务范围、AC、Composition、安全约束与外部 mutation authority 不变，则调用 owning skill 完成机械修正、必要的 P revision 与 ticket/DAG revalidation，然后继续当前已批准 attempt；不得把它升级成 owner blocker。

只有修正会新增/删除业务能力、改变 Acceptance Semantics、降低安全或数据约束、扩大外部/不可逆 mutation authority、改变 Composition earned artifacts，或存在多个会产生不同业务结果的合理方案时才请求 owner 决定。请求前先写出选项和各自业务结果；如果差异只存在于内部顺序、状态或 artifact 投影，就由执行者修正。

## Current attempt state

- tickets=false, dag=false：没有 task artifact。需要跨 session 恢复、独立交接、外部 gate、blocker 或大量局部证据时，创建 `tasks/<attempt-id>-progress.md`（Kind=attempt）；不向 plan 加 task checklist或伪造 task/ticket。
- tickets=true, dag=false：ticket Runtime Acceptance Status 是 acceptance state；whole-ticket 恢复/交接触发时才创建 `tasks/<ticket-id>-progress.md`，且不得复制验收结论。
- dag=true：当前 attempt DAG 是 task runtime state；ticketed attempt 的 ticket acceptance 仍在 ticket。
- plan Execution Record 保存实际验证过程，不保存 task/ticket status。

返工上游输出时，将依赖 task/evidence 标为 NEEDS-REVALIDATION。DONE 只有在 Done when 证据记录后才释放依赖；WAIVED/SUPERSEDED 需要替代证据和 impact note。

## Verification record

按 plan Planned Verification 和权威 policy 执行检查。每次实际检查在当前 plan 的 Execution Record 末尾追加稳定 ER-n entry，记录 D/S/P revision、时间、命令/检查、结果、证据路径与残余风险。不得修改旧 ER entry，也不得把通用 checklist 复制到 plan。

### Manual acceptance readiness

Planned Verification 存在 manual owner、且准备交给人验收时，在等待前生成轻量 readiness packet。使用 [`assets/templates/manual-acceptance-readiness.md`](assets/templates/manual-acceptance-readiness.md)：始终填写“必须”四项，只从 Optional 中选择当前场景真正需要的字段，省略不适用项，不输出 `N/A` 列表。

默认把 packet 追加到最新 ER 或 canonical handoff，不单独创建 package artifact。它用于让 manual owner 能立即开始并判断 pass/fail，不替代实际 acceptance evidence，也不要求没有人工验收的 attempt 增加流程。

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

entry ID 为 <attempt-id>-G<n>，同 attempt 从 G1 取已有最大编号加一且不复用。entry 的可读正文必须包含 Attempt ID、Supersedes、evaluated time、D/S/P revision set、binding validation 结论、Composition、comparison point、一个或多个 plan ER anchor、blocker/deferred item、verdict reason 与 Durable Deltas。精确 artifact blob OID 与 sidecar 路径只放 HTML comment 形式的 machine audit metadata。

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

terminal gate 关闭后提示 owner 可以按需使用 `$backfill-stable-docs`，但不自动调用、不阻塞当前交付，也不把它列为本次任务的剩余 blocker。audit/apply/verify 可以延期且分别汇报；只有用户明确要求、已有维护计划或进入周期维护流程时才执行，apply 仍需 owner 批准具体 report item。

## Execution checklist

1. Restore 当前 attempt 与 revisions。
2. 校验 revision bindings、派生 lifecycle、Composition/artifacts、dependency graph 与 AC references。
3. 选择并执行 actionable unit；可委派 task 必经 `subagent-driven-development` 的独立 task review，状态只写对应 runtime artifact。
4. append plan Execution Record。
5. 有 manual owner 时，在等待验收前输出轻量 readiness packet；没有人工验收时跳过。
6. 分流 findings；必要时回 req-align 并重新过相应 gate。
7. ticket 达到验收候选时自动路由 code-review、module-review 和适用的 safety-review，固定 comparison point 并闭环 findings。
8. 保留下一个 G id；拟写 terminal pass 时先完成 Stage 7 准备，再由 `verification-before-completion` 审计 pass claim。
9. 审计通过后在 gate.md 顶部一次性插入新 entry；terminal 时由 gate 派生 Frozen，blocked 时保持 Active。
10. terminal metadata commit、目标分支合入或环境变化后，任何 complete / closed / merge-ready / release-ready 声明前重新执行 completion-claim evidence audit。先合入后关 gate 的 attempt 必须以目标分支 evidence 收口。

## Output

向 owner 汇报时使用 `talk-to-boss`：首段说明本次功能范围、实施/验证/gate 各自完成到哪、剩余 blocker 数量、整体是否 closed，以及当前需要 owner 决定什么。主体按功能 slice 说明已经支持和仍未证明的行为。

随后附 canonical handoff：package/Attempt ID、D/S/P revision set、binding validation 结论、派生 lifecycle/integration qualifier、Composition、当前状态源、execution evidence、manual readiness（若适用）、findings 分流、最新 gate entry/verdict、Supersedes 链、Stage 7 与 completion-claim evidence audit。正文不得要求 owner 打开 JSON；内部 sidecar 路径只可放 machine audit metadata。terminal gate 已关闭时，另以非阻塞 follow-up 提示可选 backfill；不要把提示写成未完成 gate。
