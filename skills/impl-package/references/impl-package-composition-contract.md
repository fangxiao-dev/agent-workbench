# Impl-Package Artifact Lifecycle Contract

> **Normative shared contract.** req-align、impl-planning、to-tickets、create-task-dag 与 dev-with-track 必须引用本文件，不得各自重定义 artifact lifecycle、Composition、readiness、gate 或 Stage 7 语义。

## 1. Package identity 与 SoT 生命周期

新 package 放在项目约定的 implementations root（默认 `docs/implementations/`），使用不可变、带日期前缀的 topic slug 作为 package-id；日期位数与分隔格式由项目约定，同名时追加 -02、-03。已有 legacy package-id 不改名，post-gate patch 继续复用 owning package-id。

任务包包含两类文档：

- decision.md 与 spec.md 是活动变更期间的当前需求/决策与行为合同 SoT：decision 拥有聚焦需求定义（Focused PRD）和方案选择/rationale，spec 拥有系统行为、边界、失败恢复与 Acceptance Semantics。它们保持当前有效正文，历史变化只进入紧凑 revision/superseded 记录。
- plan、tickets、DAG、progress 与 gate entry 属于某次 implementation attempt，是过程与判决记录，不是长期行为合同。
- `execution-findings.md` 是整个任务包及后续 attempt 可共享的执行发现 provenance；`investigations/<topic>.md` 只在确有原始调查材料时创建，默认无 authority，允许不完整、冲突或过期。
- `.impl-package/revision-bindings.json` 与 `.impl-package/runtime-state.json` 是 package-local 机器 SoT：前者保存 D/S/P selection 与 append-only blob binding，后者保存 earned task/ticket current state、artifact hash chain 与 finalized gate index。字段、可变性、current-contract upgrade、projection 和 gate binding 统一由 [impl-package-state-schema.md](impl-package-state-schema.md) 定义；不得在 stage skill 重写 schema。两者都不是 owner-facing deliverable。

Markdown projection contract：

- decision/spec 通过 machine-owned marker 投影当前 D/S alias，并在正文保留 gate 结论。
- plan 通过 machine-owned marker 投影当前 D/S/P revision set，正文保留 Attempt ID、Composition、integration strategy 与发布时 binding validation。
- earned DAG/ticket 通过 machine-owned marker 投影 runtime state；gate 顶部投影最新 finalized verdict。gate entry 正文直接声明判决对应的 revision set、binding validation、comparison point、evidence、verdict reason 与 Durable Deltas；精确 OID 只放隐藏的 machine audit metadata。
- canonical handoff 直接汇总当前 revision set、binding validation、派生 lifecycle/integration qualifier、evidence 与剩余 owner decision。JSON sidecar 不得成为理解或批准交付的前置阅读材料。

terminal gate entry 写入前必须完成 Stage 7 durable-delta capture。gate 关闭后，module knowledge 与 `_pending.md` truth pointer 共同表达当前长期真相及待压实增量；后续 `$backfill-stable-docs` audit/apply/verify 可以延期且相互独立，只有 apply 才把获批增量正式归并进 module knowledge。重新 patch 时，先将 package decision/spec 与当前 module knowledge、相关 pending truth pointer 和代码对账，再激活并修订 package SoT。

### Module Knowledge Watermark（把"先对账"变成可执行检查）

每个 attempt 的 plan 在 Inputs And Authority 记录一份 watermark：本 attempt 打开时，decision/spec 引用到的每份 module-knowledge 文件（通常是 spec 的 Module Boundaries/Dependencies 点名的模块）的 `git log -1 --format=%H -- <path>` commit SHA。

新 attempt（尤其是重新激活已关闭 package 的 patch）打开前，必须重新计算这些文件当前的 commit SHA，与上一个 attempt 记录的 watermark 比对：

- 相符：module knowledge 自本 package 上次触碰以来未变，跳过对账，正常判定 drift classification。
- 不符：module knowledge 已被其他 package/改动推进，先 `git diff` 两个 commit 之间的实际变化，确认 package decision/spec 是否仍然成立，再继续；不得凭印象假设"应该没变"。
- 找不到上一份 watermark（例如首个 attempt）：无需对账，直接记录当前 watermark 供下一次比对。

## 2. Decision/Spec revision 与 drift

decision.md（存在时）的 `revision-set` marker 声明唯一当前 D revision；spec.md 的同一 projection 声明唯一当前 D/S revision。lightweight Decision 不建 decision.md 时，spec 的 D projection 与 Decision Gate Record 共同提供 canonical 落点。默认 projection 使用中文标签 `决策修订（Decision Revision）`、`规格修订（Spec Revision）` 与 `计划修订（Plan Revision）`；这些声明不得在 marker 外重复。

`decision.md` 按持久产品价值 earn：新功能、明显体验变化或业务能力变化通常需要独立文件；已有产品定义下的小型行为修正可由 spec 顶部的 lightweight Decision 记录承载；`contract impact=none` 的实现修复不创建或扩写 decision。Focused PRD 只回答目标用户/场景、问题与触发、期望结果/价值、范围/非目标、核心体验或业务流程及成功信号，不复制 spec 的字段级合同、状态机、错误处理或逐条 Acceptance Criteria。`plan.md` 独立拥有拆解、实现和验证方案。

- 实现偏离现有 spec，但预期行为不变：复用 D/S revision，创建新 attempt。
- 行为、数据、边界、失败恢复、约束或 Acceptance Semantics 改变：升级 S revision，只重跑 Spec Gate。
- Focused PRD 的用户/业务结果、决策选择或 rationale 实质改变：先升级 D revision 并重跑 Decision Gate，再按实际行为合同影响升级 S revision 并重跑 Spec Gate。仅把已存在信息重排进新模板不单独升级 D。
- 旧正文不并排保留；在 revision history 中记录 previous/new、变更摘要、authority、日期与 superseded 说明，完整 provenance 由 Git 提供。

Decision/Spec Gate 只证明其绑定的 revision；旧 gate entry 不证明后续 revision。

### Impact-scoped change routing

开始返工、patch 或恢复前，先从当前 request、实际 diff 与现有 contract 推导四个瞬时信号：

- `contract impact`: `none | plan | spec | decision`，表示变化最远触及哪个事实 owner。
- `acceptance impact`: `none | subset | all`，表示哪些 Acceptance Semantics 或 delivery slice 需要重新证明。
- `authority direction`: `decrease | unchanged | increase`，表示 mutation、安全或外部权限是收缩、保持还是扩大。
- `execution impact`: `none | local-reversible | destructive-external`，表示执行是否产生需额外授权的不可逆或外部效果。

这些信号是路由判断，不是新的 stage、mode、持久 artifact 或必填 JSON schema。只在下游无法从稳定 diff/contract 重建判断，或审计必须解释边界时，把最小结论写入既有 revision history、Execution Record 或 handoff；容易推理的低影响事实不重复投影到多个文件。

按实际影响决定失效范围：

- `contract impact=none` 且未扩大 acceptance/authority/execution 时，复用现有 D/S/P，只修改直接 owner 的 artifact，并运行能证明该 delta 的最小验证。纯减法、证据修正、引用/分类修正通常属于此路径。
- `contract impact=plan` 只升级 P revision；只有依赖被修改 plan 语义的 ticket、DAG 节点或 evidence 需要内容重验证。未受影响 artifact 可以批量确认并机械更新 Plan Revision 引用，不重新生成正文或重跑其验收。
- `contract impact=spec` 只升级 S revision并重跑 Spec Gate；按 `acceptance impact` 重验直接受影响的 subset，除非变化确实覆盖全部 acceptance。
- `contract impact=decision` 才按 Decision → Spec 顺序升级 D/S，并重新规划受影响范围。
- `authority direction=increase` 或 `execution impact=destructive-external` 必须重新检查授权与 safety 路由；`decrease` 不沿用旧的破坏性授权，也不因收缩动作自动触发全量 safety 流程。

若多个信号冲突，采用能覆盖真实影响的最窄保守路径。只有业务结果、Acceptance Semantics、Composition、安全约束、执行策略或 mutation authority 发生实质变化，才重新规划对应部分；不得仅因一个 hash、分类、路径、证据描述或 P 引用变化而推倒整条链。

### Revision-blob binding（防止 revision 号与内容脱节）

D&lt;n&gt;/S&lt;n&gt;/P&lt;n&gt; 是人类好念、好口头下发的**别名**；机器校验使用 `.impl-package/revision-bindings.json` 中与 alias、artifact path 绑定的 Git blob OID。artifact 自身只声明 alias，不记录自身 commit SHA 或 blob OID，避免“为了写入自身 hash 又改变自身 hash”的循环依赖。对 owner 而言，Markdown 中的 revision set 与 binding validation 结论是完整交付面。

内部 sidecar 使用 [`../assets/templates/revision-bindings.json`](../assets/templates/revision-bindings.json) 的 v2 形状；完整不变量引用 [结构化状态契约 §2](impl-package-state-schema.md#2-revision-bindings-schema-v2)。语义 revision、projection/editorial rebinding 均 append-only，后者以 `supersedes` 选择同 alias 的新 terminal binding。lightweight Decision 没有 decision.md 时，D&lt;n&gt; 与 S&lt;n&gt; 可以分别绑定到同一个 spec.md blob。

新 package 先通过 `impl_package_state.py --package <path> init --package-id <id>` 建立两份 current-contract sidecar；生成或升级 revision 时再运行 `register-revision ...`（多个当前 artifact 同步切换时使用 `register-revisions ...`）。命令登记最终 worktree blob、必要时 seed earned runtime records 并执行 working-tree validation。artifact 与 registry 可在同一 commit，restore、ER append 与 gate evaluation 前统一运行 `validate --committed`，由它现场以 `git rev-parse HEAD:<package-relative-path>` 复核 HEAD，不保存 published/validated 状态。低于 current contract 的 sidecar 不进入运行时；先由 agent 按修订摘要直接重塑并通过 current validation。

validation mode 区分 contract artifact 与执行证据：

- decision/spec 使用 `exact-blob`：当前 artifact blob 必须与 binding 完全相等；下文定义的 editorial correction rebinding 是唯一的同 alias 例外。
- plan 使用 `plan-contract-v1`：脚本比较 baseline 与当前 plan 的非 ER contract，并沿 Git 历史机械校验 ER append-only；正常补证不升级 P revision，策略、Composition、Planned Verification 或其他非 ER 内容变化仍会触发 P drift。

restore 或 gate evaluation 时，对 `current` 指向的 D/S/P binding 执行以下检查：

- `validate --committed` 通过：revision 可信，继续；失败则按结构化错误报告处理 capture gap/drift，不由 agent 手工模拟 blob 算法。
- decision/spec 的 `exact-blob` 不匹配时，先判断是否为 **editorial correction**：只改正错字、格式、非规范性表述、普通链接或 provenance，且可证明不改变行为、Acceptance Semantics、设计选择、约束、安全/数据边界或 mutation authority。是则在 revision history 写明依据与 `contract impact=none`，显式运行 `rebind --reason editorial --evidence <pointer> --confirm-contract-impact-none`；不重跑 Gate、不升级 alias。
- 只含 machine-owned marker body 的机械 projection refresh 运行 `refresh-projections` 并自动同 alias rebind；marker 外存在 diff 时命令拒绝，返回 owning skill 做 revision/editorial 判断，不得把语义变化洗白。
- 不能证明为 editorial correction，或其触及任何合同语义时，按 evidence 胜过 stale status 处理为 semantic revision：按本节上方四类重新分类、升级对应 revision 并登记新 binding；不得把语义变化伪装为同 alias rebinding。
- registry 缺失、重复 alias/path、`current` 指向不存在的 binding，或 Git 无法解析 blob：视为 P2 capture gap，不得默认相符。

ER 的 Revision set 表示写入该 ER 时的 current D/S/P set；plan 的 `revision-set` marker 始终表示当前 set。gate entry 为了冻结历史判决，在可读正文写 `Revision set: D<n> / S<n> / P<n>` 与 `Binding validation: passed | failed`；精确 blob OID 和内部 sidecar 路径只放 HTML comment 形式的 machine audit metadata。P blob 是 plan-contract-v1 baseline，实际 ER evidence 由 comparison point + ER anchor 固定。

## 3. Attempt、plan、Composition 与计划拆解

每次 implementation attempt 有唯一 Attempt ID：初始实现使用 initial，patch 使用其 patch-plan 文件 stem `YYYYMMDD-HHMM-&lt;patch-topic&gt;`；精确 stem 已存在时追加 `-02`、`-03`，且创建后不可改名。对应 plan 声明：

~~~markdown
执行尝试 ID（Attempt ID）：<initial | patch-id>
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D<n>
规格修订（Spec Revision）：S<n>
计划修订（Plan Revision）：P<n>
<!-- impl-package:projection revision-set end -->
执行组合（Composition）：tickets=<true|false>, dag=<true|false>
~~~

Composition 的唯一事实源是当前 attempt plan，不在 spec 中声明，也不从历史 attempt 继承。

### Composition triage

默认是 `tickets=true, dag=false`：Ticket 是交付与验收切片；DAG 不是 Ticket 的默认伴随物，只在它提供不可替代的协调价值时才 earned。

- `tickets=true` 是默认。只有单一、局部且一次验收即可收口的变更，才选择 `tickets=false`。
- `dag=true` 必须同时满足：至少两项工作可安全独立启动；存在真实 blocker、跨 owner/跨 session handoff 或 primary ownership 边界；删去 DAG 会丢失该调度或阻塞信息。自然实现顺序、多个文件或多个 Ticket 不是 DAG 依据。
- `tickets=true, dag=true` 只在上述条件成立时使用。Ticket/Task 接近一对一（例如 5 个 Ticket 对 6 个 Task）是反证信号：若 Task 只是重述各 Ticket 的实现步骤，应省略 DAG 并保持 `tickets=true, dag=false`。
- `tickets=false, dag=false` 适用于不需要独立交付切片的单一局部变更；`tickets=false, dag=true` 仍要求同一套 DAG earn condition，不能因缺少 Ticket 而放宽。

四种 Composition 的运行时与验收语义如下：

| Composition | Current execution state | Acceptance state |
| --- | --- | --- |
| tickets=false, dag=false | 无 task record；恢复事实进入现有 plan Execution Record 或 handoff，不创建 progress | spec AC + plan Execution Record + gate entry |
| tickets=true, dag=false | runtime-state ticket records 是机器 SoT，ticket files 投影；不创建 ticket progress | ticket Runtime Acceptance Status projection |
| tickets=false, dag=true | runtime-state task records 是机器 SoT，attempt DAG Runtime State 表投影；Task 仅在 blocker、handoff、重试或并行派发时按需创建 `tasks/Tn-progress.md` | spec AC + plan Execution Record + gate entry |
| tickets=true, dag=true | runtime-state task/ticket records 是机器 SoT，DAG 与 ticket files 各自投影；Task progress 同上，Ticket 不创建 progress | ticket Runtime Acceptance Status projection |

### 计划拆解 bundle 的唯一 owner checkpoint

Ticket 与 DAG 是同一计划拆解阶段的职责 artifact，不是独立审批阶段。`tickets=true` 时，`to-tickets` 必须先形成当前 Attempt/P revision 的完整 Draft Ticket 集合；`dag=true` 时，`create-task-dag` 再消费该集合与 plan，或在 `tickets=false` 时直接消费 plan 生成 DAG。随后联合校验覆盖范围、typed dependency 与 DAG dependency、primary ownership、Ticket AC evidence feasibility、Task contribution、gate/preflight 边界和 D/S/P revision binding。`impl-planning` 将这些内容连同 candidate projection、必要 D/S contract 与联合校验证据形成同一 revision 的 candidate bundle，并只进行一次适用的 `plan-review`。review 内部的 decision wave / early flush 只处理真实产品意图、外部合同、风险偏好或不可逆选择；ledger、manifest、reviewer 调度、旧 run、机械 projection 和验证命令由执行者自动处理，绝不成为 owner decision。

review 收敛后，owner 只在此处决定是否将已审查的完整 candidate bundle 写入、登记并路由到 execution/preflight。该一次 approval 覆盖 Attempt、P revision 及全部 earned Ticket/DAG，不拆出 Ticket、DAG、ledger 或 register 的子审批；已批准后，调度器自动完成既定写入、校验和下游路由。实质改变业务结果、Acceptance Semantics、Composition、安全/数据约束、计划策略或外部 mutation authority 时，旧 approval 失效并回到新的 candidate；纯引用、格式、分类或 machine projection 修正保持连续授权。不存在 earned artifact 的 Composition 不创建空 bundle 或额外 ceremony。

面向 owner 的计划拆解进度可报告为 `drafting`（earned artifacts 未齐或联合校验未通过）、`ready-for-review`（earned artifacts 齐备且校验通过）与 `approved`（当前 bundle 已获 owner approval）；`in-progress` 与 `completed` 继续由现有 Attempt、Task、Ticket acceptance 和 gate 推导。这些标签是汇报语义，不是新的 sidecar 字段、CLI 或可写状态 SoT，也不替代 Draft/Active/Frozen lifecycle。

一个状态只有一个事实源。plan 不保存 task checklist、task runtime status 或 ticket 正文。简单 no-DAG attempt 的 runtime-state `tasks[]` 必须为空；恢复使用既有 Execution Record 或 handoff，不通过给 plan、JSON 或 progress 伪造 executable task checklist。dag=true/tickets=true 时，JSON record 与 earned artifact 必须分别构成 bijection，Markdown marker 只由 `set-state`/`refresh-projections` 更新。

plan 在 attempt 活动期间可通过计划修订（Plan Revision）P&lt;n&gt; 修订策略、Composition 或验证选择；P revision 在该 attempt 内从 P1 单调递增，每次修订记录摘要与 artifact relocation，并在内部 sidecar 追加新 blob binding。terminal gate verdict 后冻结。Composition 变化只影响当前 attempt，不修改 D/S revision；迁移后不得保留两个可写 execution-state source。

### 派生 lifecycle 与 integration qualifier

plan 不保存可手工修改的 `Status`。attempt lifecycle 从 registry 与 gate ledger 派生：

- **Draft**：plan artifact 已存在，但尚未被内部 sidecar 的 `current.attempt` 选中，或其 P binding 尚未通过一致性检查；不得进入执行。
- **Active**：`current.attempt` 唯一指向该 plan/P binding，且不存在适用于当前 D/S/P revision set 的 terminal gate entry。
- **Frozen**：该 Attempt ID 已有 content-bound、且适用于当前 D/S/P revision set 的 pass/fail/defer terminal entry；plan 不再修改，后续变化创建 patch attempt。旧 entry 只证明其记录的 revision set，不因 attempt ID 相同自动冻结新的 D/S/P。

`Integrated, gate open` 是报告 qualifier，不是第四种可写 lifecycle status：当 plan 声明的 target branch 已包含当前 comparison point、但 attempt 仍为 Active 时派生。默认 integration order 是 gate-before-merge；只有 plan 记录 owner-approved pre-gate integration strategy 与证据时，才允许先合入。此后 terminal pass 与 closed claim 必须使用目标分支上的新鲜证据；合入本身不等于 gate 关闭。

**计划修订（Plan Revision）或 bundle artifact 变化后，已创建的 ticket/DAG 必须跟进，但不默认全部重做**：每个 tickets/&lt;ticket&gt;.md 与当前 attempt DAG 都声明自己创建/最后确认时所依据的 `计划修订（Plan Revision）：P<n>`。plan 从 P&lt;n&gt; 升级到 P&lt;n+1&gt; 后，仍声明旧 P&lt;n&gt; 的 artifact 是 `NEEDS-REVALIDATION`，该状态表示需要做影响判断，不表示正文必然失效；Ticket 或 DAG 的 acceptance boundary、typed dependency、Task contribution、ownership、执行顺序或 gate 发生实质变化时，当前 bundle approval 同样失效。先根据实际 delta 列出受影响 subset：受影响内容定向修订、联合校验并重新 review；未受影响内容可批量确认仍成立并机械更新计划修订引用，无需重新生成、逐项重审或重跑验收。纯 projection、引用或格式修正按 §2 的 editorial correction 规则处理。restore 必须完成这次 scoped reconciliation 后再使用相关 artifact。

可选 dispatch shorthand 只展开当前 attempt Composition，不是 sizing gate：

| Shorthand | Composition |
| --- | --- |
| S | tickets=false, dag=false |
| M | tickets=true, dag=false |
| L | tickets=true, dag=true |
| D | tickets=false, dag=true |

用户主动说“按 S/M/L/D 做”时，该字母是 `Composition request`，不是 artifact 授权或最终 SoT。`impl-planning` 先展开为 tickets/dag，再独立检查 earn conditions：

- 一致：接受请求；plan 只把 canonical `Composition: tickets=..., dag=...` 作为下游事实源，可记录 requested shorthand 与 accepted resolution 作为 provenance。
- 冲突：在创建、删除或退休任何 ticket/DAG 前，向 owner 说明请求模式、实际信号、建议 composition/简写和 artifact 影响；不得静默改标签、造 artifact 或删除已挣得的状态源。
- 新 attempt 把冲突作为 owner decision；活动 attempt 只有在 owner 接受后才升级 P revision 并执行 artifact relocation。
- owner 坚持与 earn conditions 不一致的模式时，先调整 scope、acceptance 或 coordination 前提；不能为了服从字母制造 ceremony，也不能删掉正确交付所必需的 artifact。

## 4. Typed blockers 与 readiness

ticket dependency 使用 typed edge：

~~~text
Blocked by:
- implementation: <ticket-id>
- acceptance: <ticket-id>
- release: <ticket-id>
~~~

只有 implementation edge 影响执行可行动性。DAG task 同时检查自己的 Depends on：

~~~text
actionable = unit 非 terminal
             AND ticket implementation blockers 全部 dependency-releasing
             AND DAG task 的 Depends on 全部 dependency-releasing
             AND owner、external gate 与 environment prerequisites 成立
~~~

DONE 是 dependency-releasing；WAIVED / SUPERSEDED 只有在记录替代证据与 impact note 后释放。其他状态均不释放。上游返工使依赖任务与旧证据进入 NEEDS-REVALIDATION。恢复时 evidence 胜过 stale status；多项 actionable 时按文档顺序稳定选择，不把该过滤器描述成 scheduler、leasing 或自动派工。

Task DAG 只解析 Task 的执行依赖，不把 task DONE 或 task dependency 变成 Ticket acceptance 的前置/结论图。Task 与 Ticket 以 `contributes-to` 多对多映射关联；Ticket AC 的证据、正式 review 与 acceptance status 仍只由 Ticket/Spec、plan Execution Record 和 gate 共同判定。Ticket 最终验收前，Working Branch owner 只扫描贡献该 Ticket 的 BLOCKED Task：未完成内容影响 AC、已声明行为或风险边界时必须先解除 blocker；不贡献且不影响该 Ticket 时不阻塞；真实影响扩大时先更新 contribution mapping。

贡献映射或 Task 顺序的机械修正不自动升级 contract 或 owner decision。只有修正改变业务结果、Acceptance Semantics、Composition、安全约束或外部 mutation authority，或存在多个会产生不同业务结果的方案时才请求 owner 决定。

## 5. Contract、task 与 acceptance 分工

- decision 保存选择与 rationale。
- spec 保存 interface、seam contract、contract/acceptance owner、affected targets、compatibility window、migration/rollback contract、全局约束与 Acceptance Semantics。
- plan 保存本 attempt 的执行顺序、具体迁移操作、验证选择和过程证据。
- DAG task 保存 primary ownership、已知依赖、contributes-to tickets 与已知 seam/risk；它不保存 Ticket AC、完整 task contract 或新的执行角色。
- ticket 保存独立 delivery slice、AC 与 Runtime Acceptance Status。
- gate entry 保存对绑定 revision 的判决摘要，不保存完整验证 checklist。

有 tickets 时 `contributes-to` 使用一个或多个 Ticket ID；tickets=false 时可为 `none`，由 spec AC、plan Execution Record 和 gate 保持验收链。共享 seam 的合同与 acceptance 语义仍在 spec，不能在 plan 或 DAG 中建立副本；Working Branch owner 在 integration step 处理已出现的 seam 与冲突。

## 6. Plan verification 与 execution findings 分流

plan 包含两类验证信息：

- Planned Verification：引用权威 test/review policy，记录本 attempt 选择的检查、预期结果与 evidence owner；不复制通用 Data Safety、UI Evidence、Real Route Safety 等整套模板。
- append-only Execution Record：每条使用稳定 anchor，记录实际命令/检查、结果、证据路径、执行时间与适用的 D/S/P revision。旧 record 不回改，后续补证新增 record。

`verification-before-completion` 是 completion claim 的 evidence gate，不是新的验证清单：适用 review、execution findings 分流和 Stage 7 准备完成后，写 terminal `pass` entry 前必须用当前 revision/worktree/environment 审计拟声明的 pass。可复用 provenance 清晰且未被后续变化影响的 ER/review/CI/smoke evidence；只补跑 stale、冲突、跨 revision/environment 或不完整的部分。审计不通过时不得写 pass，应报告 `implemented, not verified` 或具体 pending gate。

terminal metadata commit、目标分支合入或相关环境变化之后，任何 complete、closed、merge-ready 或 release-ready 声明都必须重新执行该审计。纯 metadata delta 不自动使行为测试失效，但最终 HEAD、工作树状态、目标分支集成状态和声明所依赖的 metadata/proof 必须与证据对齐。该 gate 不进入 DAG，也不按 ticket/task 重复运行。

`execution-findings.md` 记录执行中确认的重要发现、风险、方法性经验与跨 task 发现，可由整个任务包和后续 attempt 共同使用。gate evaluation 前判断每条发现是否要求更新 decision/spec/plan 或进入 gate Durable Deltas → `_pending.md`；验证证据进入 plan Execution Record。完成分流后，原始发现仍可作为 package-local provenance 保留。它不是第二份行为合同，也不是临时待办队列。

**这是任意 terminal verdict（pass/fail/defer）的硬性前置条件，力度等同 Stage 7**：`execution-findings.md` 中存在尚未判断其 decision/spec/plan/Durable Deltas 影响的条目时，不得写入 pass、fail 或 defer 的 terminal gate entry——不只是 pass。blocked entry 不受此约束（blocked 本来就允许如实记录 capture gap，后续用新 entry 补齐）。

`investigations/` 不参与上述分流状态：正式文档可按需链接 `investigations/<topic>.md` 作为 provenance，但 investigation 不维护指向正式文档的 backlink 或采用状态，不进入 runtime state、revision binding 或 machine projection。`decision.md` 与 `spec.md` 必须自足表达当前决定与合同，不能要求读者通读 investigation 才能理解。

## 7. Append-only Gate Ledger 与 Stage 7

package 永远只有一个 gate.md。它是 newest-first 的 append-only gate evaluation ledger；每次 evaluation 在文件顶部说明之后插入新 entry，旧 entry 不修改。

gate.md 顶部状态一览只允许存在于 `gate-status` machine-owned marker 内，由 `finalize-gate-entry` 或 `refresh-projections` 根据 canonical resolver 结果刷新；人和 agent 不直接编辑。投影只复述当前 D/S/P 可适用的 finalized entry；只有历史 entry 时必须显示当前尚无 verdict，不能把旧 pass 投影成当前 pass。新建或升级后的 package 不得保留 marker 外机器摘要；agent 升级时直接整理为唯一 projection，不创建 migration record。除 marker body 外，ledger 正文（entry 块本身）保持严格 append-only，当前 contract 不回写既有已提交的人类证据。

每个 entry 使用 &lt;attempt-id&gt;-G&lt;n&gt;，并记录：

~~~markdown
## <attempt-id>-G<n> · <pass|fail|blocked|defer>
- Attempt ID:
- Supersedes: <gate-entry-id | none>
- Evaluated at:
- Revision set: D<n> / S<n> / P<n>
- Binding validation: <passed | failed>
<!-- Machine audit metadata: sidecar=.impl-package/revision-bindings.json; D=<oid>; S=<oid>; P=<oid> -->
- Composition:
- Comparison point:
- Evidence: <one or more plan path#execution-record-anchor>
- Unresolved blocker/deferred item:
- Verdict reason:

### Durable Deltas
<table or none + reason>
~~~

- G 编号由 runtime-state append-only `allocations[]` 的最大编号现场推导，不保存 counter；`new-gate-entry --operation-id <stable-id>` 保证重试返回同一 G id，允许崩溃留下空洞但不复用。最新 finalized entry 表示当前 gate evaluation；同一 attempt 从 blocked 到 pass 时新增 G&lt;n+1&gt;，通过 Supersedes 指向前一条 evaluation。
- pass、fail、defer 是 terminal verdict；对应 plan 冻结。terminal 后的新变更必须创建新 patch attempt。
- gate 尚未 terminal 时，D/S/P revision 或证据变化通过新 plan revision、Execution Record 和 gate entry 表达，旧 entry 不回改。
- Git diff/blame 提供 provenance；不增加额外防篡改机制。

每个 gate entry 的 Durable Deltas 仍是唯一 capture surface：

~~~text
gate entry Durable Deltas -> project _pending.md -> backfill audit/apply/verify
~~~

`gate entry Durable Deltas → _pending.md / truth pointer / 必要 stub` 属于 Stage 7，是任意 terminal verdict 的强制前置；`$backfill-stable-docs` audit/apply/verify 位于 terminal gate 之后，只作为可选维护提示，可以延期且不阻塞 gate、任务 closed 或当前交付。实际调用需要用户明确要求、已批准维护计划或明确进入周期维护流程；提示本身不构成 audit/apply/verify 授权。

每条 delta 记录 delta-id、destination、source、statement、affected modules、authority、evidence 与 pending/truth-pointer 校验。去重键是 &lt;destination&gt;|&lt;delta-id&gt;。无 durable delta 时写 none 和理由。

append-only 写入顺序：运行 `new-gate-entry` 分配 G id 与 scaffold，固定 comparison point/ER anchor 后完整填写 Markdown entry；若 verdict 将是 terminal（pass/fail/defer），先用该 id 完成 _pending.md 注册、truth pointer 与必要 stub；拟写 `pass` 时再通过 `verification-before-completion`。完成正文后立即运行 `finalize-gate-entry` 反解字段、绑定完整 entry block 并追加 finalized index。Markdown verdict 已写但尚未 finalize 的短窗口被消费者 fail-safe 报为 mismatch/manual，这是有意行为；同一工作流必须紧邻执行两步。blocked capture gap 通过后续 entry 补齐，不回改旧 entry。

## 8. Shared validation checklist

- decision/spec 各有唯一当前 revision（lightweight Decision 的 D revision 在 spec 可解析），正文无并行新旧合同；revision history 足以解释 supersession。
- 当前 attempt plan 声明 Attempt ID、D/S/P revision 与唯一 Composition，且与 earned artifacts 一致。
- 计划拆解作为一个 bundle 完成：`tickets=true` 时先有完整 Draft Tickets，`dag=true` 时再有由 plan 与 Draft Tickets（或仅 plan）生成的 DAG；覆盖、依赖、ownership、acceptance/evidence、gate 与 revision binding 联合校验通过后，才允许一次 owner review/approval 与 execution/preflight。
- `validate --committed` 证明 current D/S/P selection、terminal binding、exact-blob/plan-contract-v1、ER append-only、runtime record bijection 与 projections 一致；owner-facing Markdown 已直接写出 revision set、派生 lifecycle/integration qualifier 与 binding validation 结论。
- 每个 earned ticket/DAG 声明的 Plan Revision 与当前 plan 的 P 号一致；不一致的按 NEEDS-REVALIDATION 处理，不得当作可用状态。
- 任意 terminal entry 写入前，Durable Deltas 已完成 `_pending.md` 注册、truth pointer 与必要 stub；无 delta 时已记录 `none + reason`。gate 后 backfill audit/apply/verify 不属于 terminal validation checklist。
- package 同时最多一个由 registry 选中的 Active attempt；未选中的 plan 是 Draft，terminal entry 对应 attempt 是 Frozen。多个 current attempt、或多个被选中且未冻结的 plan 是 lifecycle violation，restore 必须停止。
- plan 无 task runtime status、ticket 正文或长期 contract；通用验证政策只引用，不复制。
- 每个 Ticket AC 有实际 evidence 或明确 manual owner；Task 的 contribution mapping 不替代 AC evidence、正式 review 或 Runtime Acceptance Status。
- 每个 Ticket 最终验收前已扫描其 contributes-to BLOCKED Task；实际影响扩大时已先更新 mapping。
- 最终 package review 前，所有 Task 都是 DONE，或是有替代证据与 impact note 的 WAIVED/SUPERSEDED；不得遗留 BLOCKED，且 active Spec 的 Acceptance Semantics 已被整体覆盖。
- execution seam 的 contract 在 spec，acceptance evidence 在 plan/gate 或 ticket；Working Branch owner 在 integration step 处理执行期出现的 seam。
- plan Execution Record 使用稳定 anchor 且 append-only；gate evidence 链接可解析到对应 record。
- gate entry newest-first、旧块未修改；G allocation 不复用，finalized index 的 entry pointer/content binding 及 id/attempt/number/verdict/supersedes 与 Markdown 反解一致；mismatch 不得 fallback heading。
- execution-findings.md 在写入任意 terminal entry（pass/fail/defer，不只 pass）前已完成分流。
- terminal pass entry 写入前，`verification-before-completion` 已将拟声明的 pass 与当前 revision/worktree/environment 及可追溯 evidence 对齐；未通过时没有写 pass。
- Active attempt 若已先合入 target branch，plan 已记录 owner-approved pre-gate integration strategy，状态对外报告为 `Integrated, gate open`，最终 pass/closed evidence 来自目标分支。
- terminal gate 后 plan 已冻结；重新 patch 前已完成 Module Knowledge Watermark 对账，不是凭印象假设未变。
