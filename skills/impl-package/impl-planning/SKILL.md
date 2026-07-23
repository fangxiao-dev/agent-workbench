---
name: impl-planning
description: >
  当已有批准的 Decision/Spec 输入，需要创建 initial plan、patch plan、Composition decision、
  execution strategy 或 verification plan 时使用；不维护长期 behavior contract 或 task runtime status。
---

# Impl Planning

为一个 implementation attempt 创建可追溯的过程计划。decision/spec 是活动变更的当前 SoT；plan 只消费它们，并决定本次 attempt 的 tickets/DAG 形态、计划拆解顺序与验证路径。Ticket 与 DAG 是同一计划拆解 bundle 的两个职责产物，不是两个独立审批阶段。

共享 artifact lifecycle、Composition、gate 与 Stage 7 语义只引用 `../references/impl-package-composition-contract.md`。

## 输出

~~~text
<project implementations root>/<package-id>/
  .impl-package/revision-bindings.json        # internal machine sidecar; not an owner-facing deliverable
  .impl-package/runtime-state.json            # earned runtime/artifact/gate machine state
  plan.md                                    # initial attempt
  YYYYMMDD-HHMM-<patch-topic>.patch-plan.md  # post-gate patch attempt
~~~

每个 plan 必须声明：

~~~markdown
执行尝试 ID（Attempt ID）：<initial | patch-id>
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D<n>
规格修订（Spec Revision）：S<n>
计划修订（Plan Revision）：P<n>
<!-- impl-package:projection revision-set end -->
执行组合（Composition）：tickets=<true|false>, dag=<true|false>
~~~

Composition 是当前 plan 的事实，不从 spec 或历史 attempt 继承。plan 的唯一 D/S/P 声明是 machine-owned `revision-set` projection；不得在 marker 外再写旧式 revision header。批准当前 plan 时通过结构化状态 CLI 选择 current attempt、绑定最终 plan blob 并刷新 projection。sidecar 只供机器校验；plan 与 handoff Markdown 必须直接呈现 owner 所需结论。schema 与命令引用 [`../references/impl-package-state-schema.md`](../references/impl-package-state-schema.md)，本 skill 不复制字段定义。

## 边界

- 不创建或重写 decision/spec。发现行为或设计 drift 时路由 req-align，等待所需 gate 通过。
- 不把 interface、seam contract、compatibility、全局约束或 Acceptance Semantics 复制进 plan；这些属于 spec。选择 rationale 属于 decision。
- 不把 plan 写成逐行实现脚本：不复制完整 production code、不要求 2–5 分钟微步骤，也不内嵌每一步 commit 指令。plan 应约束实施方向和可验证边界，同时允许执行者基于当前代码完成局部判断。
- 不在 plan 保存 task checklist、task/ticket runtime status、worker ownership 或通用验证模板副本。
- 实际验证过程可 append 到 Execution Record；terminal gate verdict 后 plan 冻结。
- plan 不保存 `Status`。Draft/Active/Frozen 由内部 sidecar 的 current selection 与 gate ledger 派生。
- tickets 由 to-tickets 拥有，DAG 由 create-task-dag 拥有；impl-planning 只拥有两者的拆解顺序、Composition 和联合就绪判断。progress/execution-findings/gate ledger 由 dev-with-track 拥有。

## Routing

1. package 尚未 terminal：继续当前 attempt，按需修订当前 plan 的 P revision；不要创建 patch plan。
2. package 已有 terminal gate，新需求或修复进入 post-gate patch：复用 package-id，创建新的 Attempt ID 与 patch plan。
3. 重新 patch 前先确认 req-align 已将 package decision/spec 与当前 module knowledge/code 对账。
4. 两个 owning package 都合理时暂停并请求 owner 选择，不能另建重复 package。

先区分“plan-owned 语义变化”和“实施证据/投影变化”。只有 Execution Strategy、Composition、Planned Verification、integration/rollback strategy 或其他非 ER plan contract 改变时才升级 P revision。执行记录追加、hash/binding 复核，以及发生在 plan 外部 owner artifact 中的证据路径、分类、引用修正或不改变策略的纯减法不升级 P；若确实修改 plan 的非 ER 正文，仍按 `plan-contract-v1` 发布新 P。四个 impact signals 只在无法由 diff 重建时写入最小摘要，不扩展 sidecar schema。

## Composition

对当前 attempt 独立判断：

- tickets=true：至少两个值得独立跟踪验收结论的 delivery slice。
- dag=true：需要显式依赖图、多个 execution owner、cohort 或 execution seam。
- 两者都 false：不创建 task artifact；简单执行不通过 plan checklist 或 progress ledger 制造状态。跨 session 恢复、独立交接或外部 gate 的事实写入现有 Execution Record 或 handoff。

用户可主动用 S/M/L/D 指定期望组合。把它记录为 Composition request 并展开成本 attempt 的 tickets/dag；一致时接受。若与 earn conditions 冲突，在增删任何 ticket/DAG 前向 owner 报告请求、实际信号、建议组合和 artifact 影响，并把选择列为 owner decision，不能静默修正。活动 attempt 只有 owner 接受后才升级 P revision 和迁移 artifact。

plan 活动期间发现 Composition 判断错误时：

1. 升级 Plan Revision。
2. 记录 previous/new、原因、artifact relocation 与引用校验。
3. 创建或退休当前 attempt 的 ticket/DAG 状态来源。
4. 不修改 D/S revision，除非同时发现 contract drift。
5. 不保留两个可写 execution-state source。

## 计划拆解 bundle

当前 plan 的 Composition 决定 bundle 中必须出现哪些 artifact：tickets=true 时必须有完整 Ticket 集合，dag=true 时必须有当前 attempt DAG，未 earned 的 artifact 不创建。计划拆解按以下顺序运行：先起草完整 Ticket 集合，再在需要时基于 Draft Ticket 集合生成 DAG，随后联合校验覆盖、typed dependency、Task ownership/contribution、AC evidence feasibility、gate 边界和 D/S/P binding。

bundle 的派生汇报状态为 `drafting`、`ready-for-review`、`approved`。`ready-for-review` 只表示当前 Composition earned 的 artifact 齐备且联合校验通过；它必须先经过一次由 fresh subagent 执行的 `plan-review mode=bundle-admission`，才可请求 owner approval。`approved` 表示 owner 已批准该 Attempt、P revision 和完整 artifact 集合。它们不是新的 sidecar 状态源，也不替代 Attempt、Task 或 Ticket runtime state。

只有 bundle admission、必要时通过 `verify-clearance` 的完整 plan review 与 owner approval 完成后，才调用 Ticket publish（如 tickets=true）并进入 execution preflight/dev-with-track。DAG 不设置独立 approval 门；它必须在 review 前存在且与当前 Ticket 集合、Attempt 和 P revision 对齐。

批准后若 Ticket 的 acceptance boundary、typed edge、planned evidence、Task contribution、ownership、执行顺序或 gate 影响发生实质变化，旧 bundle approval 失效；按 impact-scoped 规则修订受影响 Ticket/DAG subset，完成联合校验并重新 review。纯引用、格式、分类或 machine projection 修正不触发重新审批。

## Plan 内容

### Coverage And Change Map

- 为 spec 的每项 Acceptance Semantics 指明对应的 Execution Strategy 与 Planned Verification 落点；使用引用或稳定标识，不复制 spec 正文。
- 列出预计创建、修改或移除的模块/文件及其责任，并标明关键依赖顺序和集成点。文件清单是实施地图，不伪造尚未确认的行号或代码细节。
- 标出迁移、兼容、rollout、rollback 和高风险步骤；需要 owner 决策的事项必须在执行前解决，不能用 `TBD`、`TODO` 或“稍后处理”占位。
- plan 中使用的模块名、类型名、路径和术语必须与当前 spec、仓库事实及既有代码一致；发现不一致时先判断是 plan 错误还是 contract drift。

### Execution Strategy

只记录本 attempt 的实施顺序、模块/文件责任、具体迁移操作、集成动作与回滚操作。执行单元应足以独立交付或验证，但不展开成机械微步骤。稳定 interface、seam、compatibility 与约束必须先进入 spec。

默认声明 `gate-before-merge`。在该默认路径中，只有当前 attempt 的 finalized `pass` gate entry 才允许 merge；`blocked`、`fail`、`defer` 或没有 `gate.md` 都不满足该前提。`gate.md` 不在 plan 创建时预建：首次 gate evaluation 由 dev-with-track 创建；此前缺文件只表示尚无 verdict，不能被写成链接或通过校验伪装为 gate evidence。

若 owner 明确要求先合入再完成 gate，plan 必须在实际 integration 前记录 target branch、`owner-approved pre-gate integration` 与可定位的决策证据。此授权只改变 integration order，不把 attempt 标为 closed；目标分支包含 comparison point 且尚无 terminal gate 时，对外状态派生为 `Integrated, gate open`，最终 pass/closed verification 必须在目标分支完成。若已合入却没有这条预先记录的授权，不得事后补写成已授权；报告 process violation，保持 gate open，并请求 owner 决定补救路径。

当 owner 只授权 spec 的一个可独立验收子切片时，必须在 merge 前把该子切片的 acceptance boundary 反映到当前 Decision/Spec/Plan，或创建独立 attempt/package。不得让同一 attempt 一面保留未实现 AC、一面把该子切片描述为整个 package 的 merge/gate completion。

### Planned Verification

- 引用权威 test/review policy。
- 将 Acceptance Semantics 映射到本次要运行的检查、预期结果和 evidence owner；命令只有在仓库中可确认时才写成精确命令。
- 不复制 Data Safety、UI Evidence、Real Route Safety 等通用 checklist。
- 当 spec 已激活 conditional evidence-integrity contract 时，在既有 Planned Verification 表中选择最小的 fault-injection matrix，而不是创建新文档或新阶段：对每个主断言至少选择一个会导致 false PASS 的反例，以及相关的副作用后失败、补偿或失效失败、投影/兼容输入漂移、公共输出跨状态漂移、预期失败输出等场景。示例按当前风险裁剪，不假定项目具有 provider、schema、archive、CLI 或 `current` 指针；每个选中的场景要写明预期的可观察 fail-closed 结果和 evidence owner。

### Execution Record

- 每次实际检查追加一个稳定 entry anchor，例如 ER-1、ER-2。
- 记录 D/S/P revision、时间、命令或检查、结果、证据路径和残余风险。
- 旧 entry 不回改；补证新增 entry。
- 这不是 task runtime status，也不替代 ticket/DAG/progress。

### Revision History

记录 plan strategy、Composition 或 verification selection 的修订，并用一句 impact summary 标出真正受影响的 ticket/DAG/evidence subset。每次 P revision 发布时在内部 sidecar 追加新的 plan blob binding，旧 binding 保留。terminal gate 后不得再改；后续变化创建新 patch attempt。不得为了记录容易推理的局部 delta 而升级 P。

## Workflow

1. 读取当前 decision/spec revision、gate ledger 最新 entry、module knowledge/code 对账结果与仓库验证政策。
2. 确认需要的 Decision/Spec Gate 已通过；实现-only drift 允许复用现有 D/S。
3. 分配 Attempt ID 与 P1，独立决定 Composition；plan 尚未被 registry 的 `current.attempt` 选中时，其 lifecycle 派生为 Draft。
4. 建立 spec coverage 与 change map，写 Execution Strategy、integration order、Planned Verification、rollout/rollback 与依赖的 policy 链接；清除 blocker placeholder，核对术语、模块与路径一致性。
5. 当 tickets=true 时调用 to-tickets draft 形成完整集合；当 dag=true 时在 Ticket 集合为 Draft 且输入齐备后调用 create-task-dag，形成当前 attempt DAG。
6. 联合校验 Ticket/DAG 的覆盖、依赖、ownership/contribution、acceptance evidence、gate 边界和 revision binding；校验未通过时保持 `drafting`，修订受影响 artifact 后重跑，不进入单独 Ticket approval。
7. 交叉检查 bundle 暴露的 contract 缺口；规范性缺口回 req-align，真正改变 plan-owned 语义的过程策略缺口升级 P revision。仅证据、引用、分类或机械顺序投影错误由 owning skill 局部修正。
8. 联合校验通过后，以确切名称在 fresh subagent 中编排 `$plan-review mode=bundle-admission`。输入仅含当前 plan、earned Ticket/DAG、必要 D/S contract、Composition 与联合校验结论，不发送本 session 的预设 verdict。开始与结果交接都要报告 admission 配置、full-review trigger scan 和实际路由；这是非阻塞的人类说明，不新增状态 artifact。`ready` 返回后，主 session 仍必须按 `plan-review` 的固有 escalation signals 做一次保守扫描：存在跨边界 contract、权限/租户/财务或持久化 mutation、single-use/replay/partial success/recovery、或 mock 遮蔽真实边界等信号时，必须升级为 `full review`。`ready` 且主 session 扫描仍为 none 时，才把结论、简短理由和下一动作写入 Admission handoff 并请求 owner approval；`full review` 时必须解析并按确切仓库路径 `skills/plan-review/SKILL.md` 启动正常 workflow，路径不可读或不可调用即 `BLOCKED`，不得用普通 reviewer 替代。正常 review 只以 `--target` 绑定可写 plan；全部 earned Ticket、DAG（如有）、联合校验证据和必要 D/S contract 都以重复 `--baseline` 绑定，进入完整评价与 Apply 后漂移复验，但不成为 Apply 写入对象。完成后只接收其 runtime handoff 的 ledger 绝对路径。`revise` 时回到对应 owning skill 修订后重新 admission，修订完成不消除固有高风险信号；`unavailable` 时重试、暂停或取消 approval。主 session 不能把其余三种结论改写成 `ready`，owner 也不能 waiver 无独立结论的 approval。
9. 新 package 必须先运行一次 `init --package-id <id>` 建立两份 current-contract sidecar。生成 complete bundle 后，AGENT 可随时调用 `preflight-register`；它只读地以正式登记同一 candidate builder 检查 revision selection、Task/Ticket grammar、attempt binding、seed records 与 projection marker，不创建流程门。材料性 review/owner 授权仍仅在语义或安全边界变化时需要；机械 ID、projection、seed 或 binding 修正复用既有有效 clearance/authorization 证据即可。实际 `register-revision` / `register-revisions` 内部再次执行同一预检，并在成功时一起选择 attempt、seed earned runtime records 与刷新投影；失败不得留下部分登记。commit 后运行 `validate --committed`。后续 ER append 不升级 P revision；ER 写入前再次 committed validate，此时且无 terminal gate 时 lifecycle 派生为 Active。
10. 执行期间只 append Execution Record；状态由对应 artifact 维护。
11. gate evaluation 由 dev-with-track 首次创建 gate.md，并在顶部插入 content-bound entry、链接对应 Execution Record；terminal verdict 使 lifecycle 派生为 Frozen。默认 merge 前，确认该 entry 已 finalized 为 current attempt 的 `pass`；pre-gate integration 只接受 plan 中已存在的 owner authorization，不得事后推定。

## Review Checklist

- Attempt ID、D/S/P revision 与 Composition 唯一且可解析。
- 内部 revision-binding sidecar 对 current plan 的 alias/path/blob 绑定唯一且可机械复核；plan 自身不记录自身 hash，且不要求 owner 打开 sidecar 才能理解当前状态。
- 每项 Acceptance Semantics 都能定位到 Execution Strategy 与 Planned Verification；不存在覆盖缺口或 `TBD`/`TODO` blocker。
- change map 给出预计模块/文件责任、依赖顺序和集成点，且没有伪造行号、复制完整实现代码或机械微步骤。
- plan 中的模块名、类型名、路径和术语与当前 spec 及仓库事实一致。
- plan 未复制 decision/spec contract、ticket 正文、task 状态或通用 checklist。
- 每个长期 seam/interface/constraint 都能在 spec 找到。
- Planned Verification 引用权威 policy；Execution Record 使用稳定 anchor 且 append-only。
- 已激活 conditional evidence-integrity contract 时，Planned Verification 为每个主断言选择了相关 false-PASS 反例和可观察 fail-closed 结果，没有把示例技术或不适用场景伪装成通用要求。
- Composition 与当前 attempt earned artifacts 一致，无双重状态来源。
- 当前 Composition earned 的 Ticket/DAG 已组成一个 bundle；联合校验通过后才进入 `ready-for-review`，没有 Ticket-only approval 或 DAG-pending 中间门。
- `ready-for-review` 后已经由 fresh subagent 执行一次明确编排的 bundle-admission；`ready` 或由 `verify-clearance --ledger <absolute-path>` 证明有效的完整 plan review 才能请求 owner approval，`full review`、`revise` 与 `unavailable` 都不能被主 session 或 owner 降级为通过。
- admission 配置与 trigger scan 已向 owner 报告；固有高风险 signal 不因计划已有缓解措施而消失，主 session 已对 reviewer 的 `ready` 执行保守升级检查。
- bundle approval 绑定当前 Attempt、P revision、完整 artifact 集合和联合校验证据；实质变化会使旧 approval 失效并触发 scoped re-review。
- plan 无手工 `Status`；Draft/Active/Frozen 与 `Integrated, gate open` 均能从 registry、gate 和 target branch 事实派生。
- 初始 plan 不链接不存在的 gate.md；首次 gate evaluation 前缺 gate.md 只能表示 open/no-verdict，不是成功或异常 evidence。
- 默认 `gate-before-merge` 已把 finalized current-attempt `pass` 设为 merge 前提；任何 pre-gate integration 都有 plan 中预先记录的 owner 决策证据。未授权先合入按 process violation 报告，不得事后补写授权。
- 如果只交付 spec 的子切片，当前 attempt 的 AC/范围或 package 边界已经同步收窄；不存在“未实现 AC 与整体完成声明”并存的状态。
- terminal gate 后 plan 已冻结。

## Output Contract

向 owner 汇报时使用 `talk-to-boss`：说明本次实现范围、计划阶段是否完成、为何需要或不需要交付切片/执行图、剩余决策，以及能否进入执行。若用户主动指定 S/M/L/D，先用人话说明是否接受及任何冲突。

随后附 canonical handoff：package-id、Attempt ID、D/S/P revision set、binding validation 结论、派生 lifecycle、Composition、计划拆解 bundle 状态、Ticket/DAG 联合校验证据、计划审查结论及下一动作、plan 路径、integration order、tickets/DAG 路由、选定 verification policy 与剩余 owner decision。正文不得要求 owner 打开 JSON；内部 sidecar 路径只可放 machine audit metadata。
