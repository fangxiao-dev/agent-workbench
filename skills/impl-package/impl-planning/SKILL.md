---
name: impl-planning
description: >
  当已有批准的 Decision/Spec 输入，需要创建 initial plan、patch plan、Composition decision、
  execution strategy 或 verification plan 时使用；不维护长期 behavior contract 或 task runtime status。
---

# Impl Planning

为一个 implementation attempt 创建可追溯的过程计划。decision/spec 是活动变更的当前 SoT；plan 只消费它们，并决定本次 attempt 的 tickets/DAG 形态、计划拆解顺序与验证路径。Ticket 与 DAG 是同一计划拆解 bundle 的两个职责产物，不是两个独立审批阶段。

共享 artifact lifecycle、Composition、gate 与 Stage 7 语义只引用 `../references/impl-package-composition-contract.md`。
当 Planned Verification 需要为 material seam 或昂贵系统验证选择渐进式证据时，读取 [`../references/progressive-system-evidence.md`](../references/progressive-system-evidence.md)。它只帮助选择证据，不改变 Decision/Spec、P revision、Composition 或 ER ownership。

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
- 实际验证过程由 `dev-with-track` 主 session 通过 `er-add` append 到 Attempt Execution Record；terminal gate verdict 后对应 ledger 冻结。
- plan 不保存 `Status`。Draft/Active/Frozen 由内部 sidecar 的 current selection 与 gate ledger 派生。
- tickets 由 to-tickets 拥有，DAG 由 create-task-dag 拥有；impl-planning 只拥有两者的拆解顺序、Composition 和联合就绪判断。Attempt `progress.md`、Execution Record、execution-findings/gate ledger 由 dev-with-track 拥有。

## Routing

1. package 尚未 terminal：继续当前 attempt，按需修订当前 plan 的 P revision；不要创建 patch plan。
2. package 已有 terminal gate，新需求或修复进入 post-gate patch：复用 package-id，创建新的 Attempt ID 与 patch plan。
3. 重新 patch 前先确认 req-align 已将 package decision/spec 与当前 module knowledge/code 对账。
4. 两个 owning package 都合理时暂停并请求 owner 选择，不能另建重复 package。

先区分“plan-owned 语义变化”和“实施证据/投影变化”。只有 Execution Strategy、Composition、Planned Verification、integration/rollback strategy 或其他非 ER plan contract 改变时才升级 P revision。执行记录追加、hash/binding 复核，以及发生在 plan 外部 owner artifact 中的证据路径、分类、引用修正或不改变策略的纯减法不升级 P；若确实修改 plan 的非 ER 正文，仍按 `plan-contract-v1` 发布新 P。消费 material D/S delta 时，先合并其相关的计划、Ticket/DAG 与验证影响，再发布一个 P revision；这不是额外 gate，只避免同一闭环被拆成连续补丁。四个 impact signals 只在无法由 diff 重建时写入最小摘要，不扩展 sidecar schema。

## Composition

对当前 attempt 独立判断，并以 `references/impl-package-composition-contract.md` 的 Composition triage 为唯一规则源。默认是 `tickets=true, dag=false`：Ticket 承载交付/验收切片；DAG 只在额外协调价值已被证明时才 earned。

- `tickets=true`：默认采用；只有单一、局部且一次验收即可收口的变更才选 `tickets=false`。
- `dag=true`：必须同时证明至少两项工作可安全独立启动，且删去 DAG 会丢失真实 blocker、跨 owner/跨 session handoff 或 primary ownership 边界的调度信息。自然实现顺序、多个文件或多个 Ticket 都不是 DAG 依据。
- `tickets=true, dag=true`：Ticket/Task 接近一对一（例如 5 个 Ticket 对 6 个 Task）是反证信号；若 Task 只重复 Ticket 的实现顺序，保持 `tickets=true, dag=false`。
- 两者都 false：不创建 task artifact；简单执行不通过 task checklist 制造状态。跨 session 恢复由根 `progress.md` 投影，独立交接或外部 gate 的事实写入 Attempt ER 或 handoff。

用户可主动用 S/M/L/D 指定期望组合。把它记录为 Composition request 并展开成本 attempt 的 tickets/dag；一致时接受。若与 earn conditions 冲突，在增删任何 ticket/DAG 前向 owner 报告请求、实际信号、建议组合和 artifact 影响，并把选择列为 owner decision，不能静默修正。活动 attempt 只有 owner 接受后才升级 P revision 和迁移 artifact。

plan 活动期间发现 Composition 判断错误时：

1. 升级 Plan Revision。
2. 记录 previous/new、原因、artifact relocation 与引用校验。
3. 创建或退休当前 attempt 的 ticket/DAG 状态来源。
4. 不修改 D/S revision，除非同时发现 contract drift。
5. 不保留两个可写 execution-state source。

## 计划拆解 bundle

当前 plan 的 Composition 决定 bundle 中必须出现哪些 artifact：tickets=true 时必须有完整 Ticket 集合，dag=true 时必须有当前 attempt DAG，未 earned 的 artifact 不创建。审查对象始终是同一 revision 的 candidate bundle：candidate plan、earned Ticket/DAG、candidate projection、必要 D/S contract 与联合校验证据；已登记 current projection 只作历史事实，不能用来判定 candidate drift 或设计风险。先起草完整 Ticket 集合，再在需要时基于 Draft Ticket 集合生成 DAG，随后联合校验覆盖、typed dependency、Task ownership/contribution、AC evidence feasibility、gate 边界和 D/S/P binding。

bundle 的派生汇报状态为 `drafting`、`ready-for-review`、`approved`。`ready-for-review` 表示 candidate bundle 齐备且联合校验通过；`approved` 表示 owner 已批准该 Attempt、P revision 和完整 artifact 集合。它们不是新的 sidecar 状态源，也不替代 Attempt、Task 或 Ticket runtime state。纯引用、格式、分类或 machine projection 修正不触发重新审批；其余会改变 Ticket acceptance boundary、typed edge、planned evidence、Task contribution、ownership、执行顺序或 gate 的变化使旧 approval 失效。

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
- 对分页/cursor、并发/锁、权限范围、持久化或外部 mutation、single-use/replay/recovery 等 material 高风险边界，在同一 Planned Verification 中给出执行者可直接落实的最小证据链：引用 spec 行为边界，选择能区分正确与错误实现的正常流及关键负向/竞态场景，注明测试层级或入口、可观察 oracle 与 ER evidence owner。优先复用现有 AC anchor、场景名或测试名；只有跨 Task/session 会产生歧义时才增加稳定 ID，不为格式对齐创建 invariant matrix、新文档或新阶段。
- 对 `material seam` 或真实 E2E/provider/browser/native-tool 验证，在既有 Planned Verification 行中简短说明：正在证明的 system assumption；排除不忠实边界后选定的忠实边界与 oracle；多个忠实候选时按总证据成本选择、成本接近才优先更早反馈；昂贵验证独有的剩余风险和必要 checkpoint/readiness。探索运行还说明候选假设、决定性 artifact 与结果分流；重复运行必须有新假设、环境/修复 delta 或观测能力。已知确定性内部前置缺证据时默认先补便宜且忠实的证据，但未知或真实环境独有风险可以有目的运行 E2E；这不是 E2E admission gate，也不要求每项 AC 跑完整证据阶梯。
- 不复制 Data Safety、UI Evidence、Real Route Safety 等通用 checklist。
- 当 spec 已激活 conditional evidence-integrity contract 时，在既有 Planned Verification 表中选择最小的 fault-injection matrix，而不是创建新文档或新阶段：对每个主断言至少选择一个会导致 false PASS 的反例，以及相关的副作用后失败、补偿或失效失败、投影/兼容输入漂移、公共输出跨状态漂移、预期失败输出等场景。示例按当前风险裁剪，不假定项目具有 provider、schema、archive、CLI 或 `current` 指针；每个选中的场景要写明预期的可观察 fail-closed 结果和 evidence owner。

### Execution Record

- plan 只保留到 `progress.md` 与 `execution-records/index.md` 的稳定链接，不再保存 ER 正文。
- 实际检查、checkpoint、判断与 failure learning 由 `dev-with-track` 主 session 调用 `er-add` 写入当前 Attempt ledger。
- ER ID、文件名、supersede 关系、sealed hash、index 与 progress projection 均由 state CLI 生成；agent 不手工查找或编辑。
- 这不是 Task runtime status，也不替代 Ticket/DAG；ER 是 package/Attempt 公共历史层。

### Revision History

记录 plan strategy、Composition 或 verification selection 的修订，并用一句 impact summary 标出真正受影响的 ticket/DAG/evidence subset。每次 P revision 发布时在内部 sidecar 追加新的 plan blob binding，旧 binding 保留。terminal gate 后不得再改；后续变化创建新 patch attempt。不得为了记录容易推理的局部 delta 而升级 P。

## Workflow

1. 读取当前 decision/spec revision、gate ledger 最新 entry、module knowledge/code 对账结果与仓库验证政策。
2. 确认需要的 Decision/Spec Gate 已通过；实现-only drift 允许复用现有 D/S。
3. 分配 Attempt ID 与 P1，独立决定 Composition；plan 尚未被 registry 的 `current.attempt` 选中时，其 lifecycle 派生为 Draft。
4. 建立 spec coverage 与 change map，写 Execution Strategy、integration order、Planned Verification、rollout/rollback 与依赖的 policy 链接；对 material 高风险边界确认验证已可直接执行并能落到后续 ER。material seam 或昂贵系统验证按渐进式系统证据写明 assumption、忠实边界/oracle、必要 checkpoint 和真实环境独有风险；低风险局部路径不增加这一 ceremony。清除 blocker placeholder，核对术语、模块与路径一致性。
5. 形成 candidate bundle：`tickets=true` 时调用 `to-tickets` draft 形成完整集合；`dag=true` 时在 Draft Ticket 集合与输入齐备后调用 `create-task-dag`，无 Tickets 时直接消费 plan 形成当前 attempt DAG。随后补齐 candidate projection，并联合校验覆盖、依赖、ownership/contribution、acceptance evidence、gate 边界和 revision binding。缺口由 owning skill 修正；候选缺 projection、证据、引用、分类或机械顺序问题不晋升为 owner decision。
6. 对同一 candidate bundle 做一次适用的 `plan-review`：首次或范围已变化的 candidate，命中固有高风险 signal 时直接 full review，否则 fresh `$plan-review mode=bundle-admission`。正常 full review 的真实材料性选择必须先完成一次完整 closure sweep，再将全部已知 findings、owner decisions、影响链与证据合成有限 closure brief；若后续 candidate 只实现该 batch 且未扩大 D/S/P、authority 或 public-contract 边界，改由 fresh `$plan-review mode=focused-closure-verification` 逐项验证，不重新开放问题搜索。该模式 `closure-verified` 后仍须取得正常 ledger 的 `verify-clearance` 成功；`reopen-full-review` 将升级理由与既有 brief 合并为新的 closure batch 后回到 normal full review；`blocked` 补齐输入后重验。`revise` 回 owning skill，`unavailable` 重试、暂停或取消本次 checkpoint，不能降级为通过。
7. review 收敛后请求**一次**完整 bundle approval。获批即自动执行 register/publish/preflight：新 package 先 `init --package-id`，`preflight-register` 只作只读校验，`register-revision` / `register-revisions` 原子选择 attempt、seed runtime records 并刷新 projection，随后 `validate --committed`；不再为 ledger、登记、Ticket/DAG 或下游路由单独请示。
8. 进入 execution 后只通过 `er-add` append Attempt Execution Record；runtime state、progress projection 与 gate evaluation 交由 dev-with-track。

## Review Checklist

- Attempt ID、D/S/P revision 与 Composition 唯一且可解析。
- 内部 revision-binding sidecar 对 current plan 的 alias/path/blob 绑定唯一且可机械复核；plan 自身不记录自身 hash，且不要求 owner 打开 sidecar 才能理解当前状态。
- 每项 Acceptance Semantics 都能定位到 Execution Strategy 与 Planned Verification；不存在覆盖缺口或 `TBD`/`TODO` blocker。
- change map 给出预计模块/文件责任、依赖顺序和集成点，且没有伪造行号、复制完整实现代码或机械微步骤。
- plan 中的模块名、类型名、路径和术语与当前 spec 及仓库事实一致。
- plan 未复制 decision/spec contract、ticket 正文、task 状态或通用 checklist。
- 每个长期 seam/interface/constraint 都能在 spec 找到。
- Planned Verification 引用权威 policy；Attempt Execution Record 使用稳定 anchor、sealed hash 且 append-only，plan 不再承载正文。
- material 高风险边界已由 spec anchor 贯通到可执行场景、测试层级/入口、可观察 oracle 与 ER evidence owner；链路可语义定位即可，不要求统一 ID 或固定表格。
- material seam 或昂贵系统验证已在既有 Planned Verification 中说明 system assumption、忠实边界/oracle、总证据成本判断、必要 checkpoint 与真实环境独有风险；探索 E2E 有明确诊断目的而非隐性 admission gate，低风险局部改动未被机械升级。
- 已激活 conditional evidence-integrity contract 时，Planned Verification 为每个主断言选择了相关 false-PASS 反例和可观察 fail-closed 结果，没有把示例技术或不适用场景伪装成通用要求。
- Composition 与当前 attempt earned artifacts 一致，无双重状态来源。
- Candidate bundle 仅比较同一 P revision 的 plan、earned Ticket/DAG、candidate projection、必要 contract 与联合校验证据；current registry projection 不是 candidate drift 依据。
- 当前 Composition earned 的 Ticket/DAG 已组成一个 bundle，联合校验通过后才进入 `ready-for-review`；没有 Ticket-only approval 或 DAG-pending 中间门。
- candidate → 一次适用 review → 一次完整 bundle approval → 自动 register/route 是计划阶段唯一 checkpoint 路径；decision wave 只处理材料性选择，内部 ledger/manifest/topology 不进入 owner gate。
- plan 无手工 `Status`；Draft/Active/Frozen 与 `Integrated, gate open` 均能从 registry、gate 和 target branch 事实派生。
- 初始 plan 不链接不存在的 gate.md；首次 gate evaluation 前缺 gate.md 只能表示 open/no-verdict，不是成功或异常 evidence。
- 默认 `gate-before-merge` 已把 finalized current-attempt `pass` 设为 merge 前提；任何 pre-gate integration 都有 plan 中预先记录的 owner 决策证据。未授权先合入按 process violation 报告，不得事后补写授权。
- 如果只交付 spec 的子切片，当前 attempt 的 AC/范围或 package 边界已经同步收窄；不存在“未实现 AC 与整体完成声明”并存的状态。
- terminal gate verdict 后 plan 冻结；对应 Attempt Execution Record 同步冻结。

## Output Contract

向 owner 汇报时使用 `talk-to-boss`：说明本次实现范围、计划阶段是否完成、为何需要或不需要交付切片/执行图、剩余决策，以及能否进入执行。若用户主动指定 S/M/L/D，先用人话说明是否接受及任何冲突。

随后附 canonical handoff：package-id、Attempt ID、D/S/P revision set、binding validation 结论、派生 lifecycle、Composition、计划拆解 bundle 状态、Ticket/DAG 联合校验证据、计划审查结论及下一动作、plan 路径、integration order、tickets/DAG 路由、选定 verification policy 与唯一剩余 owner decision。正文不得要求 owner 打开 JSON；ledger 路径仅保留在内部 runtime handoff。
