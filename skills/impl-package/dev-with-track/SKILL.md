---
name: dev-with-track
description: >
  当已批准 implementation attempt 需要恢复执行、选择下一 actionable unit、记录 verification
  evidence、处理返工失效、分流 execution findings 或评估 append-only gate ledger 时使用；不拥有
  decision/spec/plan/ticket/DAG 定义。
---

# Dev With Track

执行并恢复项目约定 implementations root 下 `<package-id>/` 中的当前 attempt。共享 artifact lifecycle、Composition、readiness 与 gate 语义只引用 `../references/impl-package-composition-contract.md`；结构化字段与 CLI 只引用 `../references/impl-package-state-schema.md`。

## Ownership

- req-align 拥有活动 decision/spec SoT 与 D/S Gate。
- impl-planning 拥有当前 attempt plan、P revision、Composition、Planned Verification 与 Execution Record 结构。
- to-tickets 拥有 ticket definition/publication；create-task-dag 拥有 DAG contract；两者在执行前必须作为同一计划拆解 bundle 通过联合 review。
- 本 skill 通过结构化状态 CLI 维护 earned ticket/DAG runtime state、artifact hash chain 与 finalized gate index，同时维护条件化 Task progress、`execution-findings.md` 分流、plan Execution Record 证据叙述和 gate.md entry 正文。

本 skill 不重写长期 contract，不从历史 Composition 推断当前 attempt，也不修改旧 gate entry。

## Task execution and review routing

本 skill 选择 actionable unit、维护其 runtime state，并拥有 Ticket acceptance 的最终入口；它不自行代替 task worker。存在有界且委派收益明确的 Task 时，调用同体系的 `subagent-driven-development`；普通 Task 只派发目标、primary ownership、禁改范围、已知依赖、贡献 Ticket、局部验证与 `BLOCKED` 返回格式。单 owner、机械、局部可逆且委派成本更高的 delta 由 Working Branch owner 直接完成。Task 的局部证据可记入条件化 progress/handoff 或当前 Ticket evidence，但不构成独立正式 review。

Task 是横向执行拆分，Ticket 是纵向验收单元；二者以多对多 `contributes-to` coverage 关联，不建立默认父子层级。Task `DONE` 只说明产出与局部证据可交给 Working Branch owner 集成，不能自动更新 Ticket acceptance status。Working Branch owner 在并行 Task 返回、出现 `BLOCKED` 或 Ticket 最终验收前完成 integration step：合并产出、处理实际 seam/冲突、运行共享验证和正式 review、将证据映射回 Ticket AC，并据此决定 Ticket 是否可验收。

当 ticket 或 no-ticket attempt 达到验收候选，先固定 comparison point，再按实际 diff 与 contract impact 运行正式 review；不能仅凭 package 曾经有 tickets/DAG 推导本次 review：

- `code-review`：任何 implementation 恒必做。
- `module-review`：当前 diff 或本次 S/P delta 涉及 interface、状态机、模块边界、跨模块行为或 seam 时必做。tickets/DAG 的存在本身不是触发信号。
- `safety-review`：diff 或 spec/plan/DAG 出现 auth、permission、payment、webhook、migration、外部 mutation、数据完整性、并发安全，或 evidence authority / published-state / compatibility-projection / proof-equality 信号时必做。后四类是条件化风险信号，不假定所有项目存在 provider、schema、archive、CLI 或 `current` 指针。

正式 review 的 findings 必须修复并以 closure verification 复核，才可把 ticket Runtime Acceptance Status 记为已满足或进入 gate。

如果当前 spec 激活了 conditional evidence-integrity contract，任务只有在相关 false-PASS 反例和适用的副作用后失败/失效路径已有证据时才能 dependency-release；绿色正向测试本身不能释放该依赖。证据仍写入既有 task/ticket/Execution Record，不创建新的 runtime artifact。

## Completion claim gate

适用的正式 review、execution findings 分流和 Stage 7 准备完成后，在写入 terminal `pass` entry 前必须调用同体系的 `verification-before-completion`，用拟声明的 pass、当前 revision/worktree/environment 和 plan ER/review/smoke evidence 做 claim-to-evidence 审计。它不是 DAG task，不按 ticket 或 task 重复运行，也不替代既有 review 与验证。

证据完整且仍新鲜时可以复用，不机械重跑全部检查；证据 stale、跨 revision/environment、冲突或不足时，只补跑受影响检查。审计未通过时不得写 pass 或宣称 closed，应报告 `implemented, not verified` 或具体 pending gate。

terminal metadata 后若又发生 commit、合入目标分支或相关环境变化，在对外宣称 complete、closed、merge-ready 或 release-ready 前再次调用 `verification-before-completion`，核对变化是否使既有证据失效。纯 metadata delta 不自动使行为测试失效，但必须验证最终 HEAD、工作树状态和声明所依赖的 metadata/proof。

## Restore

1. 采用 delta-first restore：先读取仓库规则、`.impl-package/` 两个 sidecar、current attempt plan、gate.md 最新 entry、最近可靠 comparison point/ER anchor，以及自该点后的实际 diff。只在 current 选择冲突、provenance 缺口或 delta 无法解释时读取历史 plans 和完整 ledger；不要每次恢复都重扫全部历史 artifact。
2. 从 registry 的 `current.attempt` 与 canonical Gate resolver 派生唯一 lifecycle：未被选中的 plan 是 Draft；被选中且没有适用于当前 D/S/P 的 terminal gate 的 attempt 是 Active；只有 content-bound terminal entry 与当前 D/S/P 一致时才是 Frozen。合法历史 entry 仍保留为 `indexed` evidence，但不冻结新 revision。若不存在 Active attempt，停止并路由 impl-planning 创建或批准 patch；若 registry/current/gate 组合产生多个 Active attempt，报告 lifecycle violation 并停止，不能按时间猜一个。
3. 运行 `impl_package_state.py --package <path> validate --committed`，由它以 `git rev-parse HEAD:<package-relative-path>` 现场复核 current D/S/P，并统一检查 exact-blob/plan-contract-v1、ER append-only、earned record bijection、projection 与 finalized gate binding。失败按结构化错误报告处理 P2 capture gap/drift，不得手工模拟算法后宣称可信。
4. 校验计划拆解 bundle 已达到 `approved`：当前 Composition earned 的 Ticket 集合已完整发布（如 tickets=true），当前 DAG 已存在且与 Attempt/P revision 对齐（如 dag=true），并且 canonical handoff 记录了同一完整集合的联合 review/approval 证据。缺任一条件时停止，不把 Ticket-only approval 或存在 DAG 文件误判为 bundle approval。
5. reconcile 状态与证据；evidence 胜过 stale status。比对 earned ticket/DAG 的 Plan Revision 与当前 P 号；不一致的先标 `NEEDS-REVALIDATION`，再按 P delta 计算受影响 subset。受影响内容定向复核；未受影响内容批量确认并机械更新引用，不逐个重跑验收或重建 artifact。
6. 是新 attempt（尤其重新激活已关闭 package）时，先完成 Module Knowledge Watermark 对账：重新计算 watermark 文件当前 commit SHA，与上一 attempt 记录的 watermark 比对，不符先 diff 确认 decision/spec 是否仍成立。
7. 校验 typed ticket edges、DAG Depends on、Task-to-Ticket contribution mapping 与显式 cycles；DAG 只表达 Task execution dependency，不把 Task state 或 mapping 当作 Ticket AC acceptance 的自动结论。
8. 执行 readiness resolution，按文档顺序选择第一个 actionable unit；不自动派工。

目标分支已包含当前 comparison point、但 attempt 仍为 Active 时，向 owner 报告派生 qualifier `Integrated, gate open`。若 plan 没有 owner-approved pre-gate integration strategy，视为 integration-order violation；即使已有批准，最终 pass/closed evidence 仍必须来自目标分支。

### 计划错误的修复权限

发现 decomposition/readiness defect 时，先判断修正是否改变业务结果。若只涉及 typed edge 分类、Task 顺序、contribution mapping 或 artifact 引用，并保持 D/S、业务范围、AC、Composition、安全约束、plan-owned strategy 与外部 mutation authority 不变，则调用 owning skill 完成机械修正和受影响 subset 的定向验证，然后继续当前已批准 attempt；此类变化通常不需要 P revision，也不得升级成 owner blocker。

若修正影响 Ticket acceptance boundary、typed edge、planned evidence、Task contribution、ownership、执行顺序或 gate，当前 bundle approval 立即失效；先回到计划拆解 bundle 的 `drafting`/`ready-for-review` 路径，完成受影响 subset 的联合校验和重新 review，不得继续执行旧结构。

只有修正会新增/删除业务能力、改变 Acceptance Semantics、降低安全或数据约束、扩大外部/不可逆 mutation authority、改变 Composition earned artifacts，或存在多个会产生不同业务结果的合理方案时才请求 owner 决定。请求前先写出选项和各自业务结果；如果差异只存在于内部顺序、状态或 artifact 投影，就由执行者修正。

## Current attempt state

- 默认不创建 progress 文件。仅当某个 DAG Task 实际 `BLOCKED`、跨 session handoff、需要重试，或主 session 分发并行 subagent 时，才创建或更新 `tasks/<task-id>-progress.md`；它只记录当前 blocker/原因、已做证据、下一可执行动作和影响 Ticket。
- `tickets=false, dag=false` 与 `tickets=true, dag=false` 不创建 attempt 或 ticket progress，也不以 progress 复制 Ticket AC、acceptance status 或第二套 Ticket 状态。
- dag=true：runtime-state task record 是机器 SoT，当前 attempt DAG Runtime State 表是投影；ticketed attempt 的 Ticket acceptance 同样由 ticket record 投影到 ticket。
- plan Execution Record 保存实际验证过程，不保存 task/ticket status。

状态变化运行 `set-state ... --attempt <id> --expect <previous> --evidence <pointer>`；命令同时刷新投影并用 CAS-lite 拒绝 stale transition。返工上游输出时，将依赖 task/evidence 标为 NEEDS-REVALIDATION。DONE 只有在 Done when 证据记录后才释放依赖；WAIVED/SUPERSEDED 需要替代证据和 impact note。

## Verification record

按 plan Planned Verification 和权威 policy 执行检查。追加 ER 前先运行 committed validate；每次实际检查在当前 plan 的 Execution Record 末尾追加稳定 ER-n entry，Revision set 表示写入时 current D/S/P，并记录时间、命令/检查、结果、证据路径与残余风险。不得修改旧 ER entry，也不得把通用 checklist 复制到 plan。外部交付物通过 `record-artifact` / `supersede-artifact` 维护 hash identity；ER 只写 delta 与 runtime-state pointer，不重复完整 hash 清单，path 只作可能跨机器失效的 provenance hint。

### Manual acceptance readiness

Planned Verification 存在 manual owner、且准备交给人验收时，在等待前生成轻量 readiness packet。使用 [`assets/templates/manual-acceptance-readiness.md`](assets/templates/manual-acceptance-readiness.md)：始终填写“必须”四项，只从 Optional 中选择当前场景真正需要的字段，省略不适用项，不输出 `N/A` 列表。

默认把 packet 追加到最新 ER 或 canonical handoff，不单独创建 package artifact。它用于让 manual owner 能立即开始并判断 pass/fail，不替代实际 acceptance evidence，也不要求没有人工验收的 attempt 增加流程。

## Execution findings curation

`execution-findings.md` 记录执行过程中确认的重要发现、风险、方法性经验和跨 task 发现，可由整个 package 与后续 attempt 共同使用并作为 package-local provenance 保留。它不是第二份行为合同，也不是临时待办队列；没有实质发现时不创建空文件。

gate evaluation 前逐项分流 execution findings：

- 决策/rationale → req-align 更新 decision revision；
- 行为、接口、失败恢复、约束或 Acceptance Semantics → req-align 更新 spec revision；
- 长期项目知识 → 当前 gate entry Durable Deltas 与 _pending.md；
- 验证证据 → plan Execution Record；
- 其余已确认的重要发现、风险、方法性经验与跨 task 发现 → 保留在 `execution-findings.md`。

原始 ideas、调查过程、候选假设、实验材料和参考笔记可在真正产生材料时写入 `investigations/<topic>.md`；不得创建空 `investigations/` 目录。investigation 默认无 authority，可不完整、冲突或过期，不进入 runtime state、不绑定 revision、不设 machine projection。`decision.md`、`spec.md` 或 `plan.md` 可按需单向链接 investigation，但 investigation 不维护 backlink 或采用状态，且 `decision.md` 与 `spec.md` 必须脱离 investigation 仍能自足表达当前决定与合同。

存在未完成的规范性分流时不能写任何 terminal entry（pass/fail/defer，不只 pass）；blocked entry 不受此约束。

执行期 finding 触发 D/S revision 升级时，req-align 返回后由本 skill 先运行 `refresh-projections`，再按 impact-scoped routing reconcile current P、earned ticket/DAG 引用与 runtime records；committed validate 重新通过后才继续 append ER。机械引用刷新不升级 P，marker 外 diff 则退回 owning skill 判断。

## Append-only gate ledger

package 只使用 gate.md。顶部状态一览是 `gate-status` machine-owned projection，正文判断只能来自 finalized entry；旧 entry 不修改。初始 attempt 不要求预建 gate.md：不存在只表示 open/no-verdict。创建 evaluation 时运行 `new-gate-entry --attempt <id> --operation-id <stable-id>` 分配 G id/scaffold，不手算或保存 counter。

默认 `gate-before-merge` 路径中，在 merge 前确认 current attempt 的 finalized entry 为 `pass`。若计划声明 `owner-approved pre-gate integration`，先核对 target branch 与可定位的 owner evidence，再允许 integration，并只报告 `Integrated, gate open`；不得把 merge 或 schema 子切片的局部证据写成 terminal pass。若 target branch 已有 comparison point、但 plan 没有预先记录该授权，停止 completion/merge-ready claim，记录 process violation 并请求 owner 决定补救；不得事后补写授权来清除该事实。

entry 的可读正文必须包含 Attempt ID、Supersedes、evaluated time、D/S/P revision set、binding validation 结论、Composition、comparison point、一个或多个 plan ER anchor、blocker/deferred item、verdict reason 与 Durable Deltas。正文完成后立即运行 `finalize-gate-entry <G-id>`；它校验 allocation、逐字段反解、完整 entry content binding 与 package-local pointer，再刷新顶部投影。两步之间被消费方识别为 mismatch/manual 是有意 fail-safe，工作流中不得插入无关步骤。

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

无 durable delta 时写 none 和理由。写入 terminal entry 时先分配 G id、固定 comparison point/ER anchor、完成 Stage 7 与必要 claim audit，再 finalize immutable index；blocked capture gap 通过后续 entry 补齐，不回改旧 entry。gate 关闭后，module knowledge 与 `_pending.md` truth pointer 共同表达当前长期真相和待压实增量。

terminal gate 关闭后提示 owner 可以按需使用 `$backfill-stable-docs`，但不自动调用、不阻塞当前交付，也不把它列为本次任务的剩余 blocker。backfill 调用先独立执行 contract preflight：旧包直接按 current contract 改造并校验，失败则停止；校验通过后才进入 audit/apply/verify。三个动作可以延期且分别汇报，只有用户明确要求、已有维护计划或进入周期维护流程时才执行，apply 仍需 owner 批准具体 report item。

## Execution checklist

1. Restore 当前 attempt 与 revisions。
2. 校验 revision bindings、派生 lifecycle、Composition/artifacts、dependency graph 与 AC references。
3. 选择并执行 actionable unit；可委派 Task 使用 `subagent-driven-development` 的最小派发，状态只通过 `set-state` 写入 runtime-state 并刷新投影。普通 Task 不触发完整 contract、独立正式 review 或逐 Task gate；高风险 diff 只按实际风险加严局部验证/审查。
4. committed validate 通过后 append plan Execution Record；外部 artifact hash delta 通过 artifact commands 登记。
5. 有 manual owner 时，在等待验收前输出轻量 readiness packet；没有人工验收时跳过。
6. 分流 execution findings；必要时回 req-align 并重新过相应 gate。
7. Ticket 达到验收候选前，只扫描 `contributes-to` 该 Ticket 的 `BLOCKED` Task：未完成内容若影响其 AC、已声明行为或风险边界，先解除阻塞；若真实影响扩大，先更新 contribution mapping。随后自动路由 code-review、module-review 和适用的 safety-review，固定 comparison point 并闭环 review findings。最终 package review 前全局确认没有 `BLOCKED`，且所有 Task 为 `DONE` 或有明确、已批准理由的 `WAIVED` / `SUPERSEDED`；再确认所有 Ticket AC evidence 和 active Spec 全覆盖。
8. 默认 merge 前，用稳定 operation-id 分配 G id/scaffold，完成当前 attempt 的 pass evaluation；拟写 terminal pass 时先完成 Stage 7 准备，再由 `verification-before-completion` 审计 pass claim。只有 plan 已预先记录的 owner-approved pre-gate integration 可以跳过这一时序。
9. 完成 Markdown entry 后立即 finalize content-bound index；terminal 时由可信 finalized verdict 派生 Frozen，blocked 时保持 Active。
10. terminal metadata commit、目标分支合入或环境变化后，任何 complete / closed / merge-ready / release-ready 声明前重新执行 completion-claim evidence audit。先合入后关 gate 的 attempt 必须以目标分支 evidence 收口。

## Output

向 owner 汇报时使用 `talk-to-boss`：首段说明本次功能范围、实施/验证/gate 各自完成到哪、剩余 blocker 数量、整体是否 closed，以及当前需要 owner 决定什么。主体按功能 slice 说明已经支持和仍未证明的行为。

随后附 canonical handoff：package/Attempt ID、D/S/P revision set、binding validation 结论、派生 lifecycle/integration qualifier、Composition、计划拆解 bundle 状态与联合 review 证据、当前状态源、execution evidence、manual readiness（若适用）、execution findings 分流、最新 gate entry/verdict、Supersedes 链、Stage 7 与 completion-claim evidence audit。正文不得要求 owner 打开 JSON；内部 sidecar 路径只可放 machine audit metadata。terminal gate 已关闭时，另以非阻塞 follow-up 提示可选 backfill；不要把提示写成未完成 gate。
