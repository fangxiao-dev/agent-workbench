# Impl-Package Artifact Lifecycle Contract

> **Normative shared contract.** req-align、impl-planning、to-tickets、create-task-dag 与 dev-with-track 必须引用本文件，不得各自重定义 artifact lifecycle、Composition、readiness、gate 或 Stage 7 语义。

## 1. Package identity 与 SoT 生命周期

新 package 使用 UTC 日期生成不可变的 YYMMDD-&lt;topic-slug&gt; package-id；同名时追加 -02、-03。已有 legacy package-id 不改名，post-gate patch 继续复用 owning package-id。

任务包包含两类文档：

- design.md 与 spec.md 是活动变更期间的当前设计 SoT。它们保持当前有效正文，历史变化只进入紧凑 revision/superseded 记录。
- plan、tickets、DAG、progress 与 gate entry 属于某次 implementation attempt，是过程与判决记录，不是长期行为合同。
- `.impl-package/revision-bindings.json` 是 package-local 的内部 revision 选择与内容绑定 sidecar。它只保存 D/S/P alias、artifact path 与 Git blob OID，不保存 task/runtime 状态，也不是 owner-facing deliverable。owner-facing Markdown 按各自职责呈现可读投影，canonical handoff 汇总当前 revision、lifecycle、integration 与 verification 状态；不得要求读者打开 JSON。

Markdown projection contract：

- design/spec 直接声明当前 D/S alias 与 gate 结论。
- plan 直接声明 Attempt ID、D/S/P revision set、Composition、integration strategy 与发布时 binding validation。
- gate 直接声明判决对应的 D/S/P revision set、binding validation、comparison point、evidence 与 verdict；精确 OID 只放隐藏的 machine audit metadata。
- canonical handoff 直接汇总当前 revision set、binding validation、派生 lifecycle/integration qualifier、evidence 与剩余 owner decision。JSON sidecar 不得成为理解或批准交付的前置阅读材料。

terminal gate entry 写入前必须完成 Stage 7 durable-delta capture。gate 关闭后，module knowledge 与 `_pending.md` truth pointer 共同表达当前长期真相及待压实增量；后续 `$backfill-stable-docs` audit/apply/verify 可以延期且相互独立，只有 apply 才把获批增量正式归并进 module knowledge。重新 patch 时，先将 package design/spec 与当前 module knowledge、相关 pending truth pointer 和代码对账，再激活并修订 package SoT。

### Module Knowledge Watermark（把"先对账"变成可执行检查）

每个 attempt 的 plan 在 Inputs And Authority 记录一份 watermark：本 attempt 打开时，design/spec 引用到的每份 module-knowledge 文件（通常是 spec 的 Module Boundaries/Dependencies 点名的模块）的 `git log -1 --format=%H -- <path>` commit SHA。

新 attempt（尤其是重新激活已关闭 package 的 patch）打开前，必须重新计算这些文件当前的 commit SHA，与上一个 attempt 记录的 watermark 比对：

- 相符：module knowledge 自本 package 上次触碰以来未变，跳过对账，正常判定 drift classification。
- 不符：module knowledge 已被其他 package/改动推进，先 `git diff` 两个 commit 之间的实际变化，确认 package design/spec 是否仍然成立，再继续；不得凭印象假设"应该没变"。
- 找不到上一份 watermark（例如首个 attempt）：无需对账，直接记录当前 watermark 供下一次比对。

## 2. Design/Spec revision 与 drift

design.md（存在时）或 spec.md 的 Design Gate Record 声明唯一当前 Design Revision: D&lt;n&gt;；spec.md 声明唯一当前 Spec Revision: S&lt;n&gt;。lightweight Design 不建 design.md 时，D revision 仍必须在 spec 中可解析。

- 实现偏离现有 spec，但预期行为不变：复用 D/S revision，创建新 attempt。
- 行为、数据、边界、失败恢复、约束或 Acceptance Semantics 改变：升级 S revision，只重跑 Spec Gate。
- 设计选择或 rationale 改变：先升级 D revision 并重跑 Design Gate，再升级 S revision 并重跑 Spec Gate。
- 旧正文不并排保留；在 revision history 中记录 previous/new、变更摘要、authority、日期与 superseded 说明，完整 provenance 由 Git 提供。

Design/Spec Gate 只证明其绑定的 revision；旧 gate entry 不证明后续 revision。

### Impact-scoped change routing

开始返工、patch 或恢复前，先从当前 request、实际 diff 与现有 contract 推导四个瞬时信号：

- `contract impact`: `none | plan | spec | design`，表示变化最远触及哪个事实 owner。
- `acceptance impact`: `none | subset | all`，表示哪些 Acceptance Semantics 或 delivery slice 需要重新证明。
- `authority direction`: `decrease | unchanged | increase`，表示 mutation、安全或外部权限是收缩、保持还是扩大。
- `execution impact`: `none | local-reversible | destructive-external`，表示执行是否产生需额外授权的不可逆或外部效果。

这些信号是路由判断，不是新的 stage、mode、持久 artifact 或必填 JSON schema。只在下游无法从稳定 diff/contract 重建判断，或审计必须解释边界时，把最小结论写入既有 revision history、Execution Record 或 handoff；容易推理的低影响事实不重复投影到多个文件。

按实际影响决定失效范围：

- `contract impact=none` 且未扩大 acceptance/authority/execution 时，复用现有 D/S/P，只修改直接 owner 的 artifact，并运行能证明该 delta 的最小验证。纯减法、证据修正、引用/分类修正通常属于此路径。
- `contract impact=plan` 只升级 P revision；只有依赖被修改 plan 语义的 ticket、DAG 节点或 evidence 需要内容重验证。未受影响 artifact 可以批量确认并机械更新 Plan Revision 引用，不重新生成正文或重跑其验收。
- `contract impact=spec` 只升级 S revision并重跑 Spec Gate；按 `acceptance impact` 重验直接受影响的 subset，除非变化确实覆盖全部 acceptance。
- `contract impact=design` 才按 Design → Spec 顺序升级 D/S，并重新规划受影响范围。
- `authority direction=increase` 或 `execution impact=destructive-external` 必须重新检查授权与 safety 路由；`decrease` 不沿用旧的破坏性授权，也不因收缩动作自动触发全量 safety 流程。

若多个信号冲突，采用能覆盖真实影响的最窄保守路径。只有业务结果、Acceptance Semantics、Composition、安全约束、执行策略或 mutation authority 发生实质变化，才重新规划对应部分；不得仅因一个 hash、分类、路径、证据描述或 P 引用变化而推倒整条链。

### Revision-blob binding（防止 revision 号与内容脱节）

D&lt;n&gt;/S&lt;n&gt;/P&lt;n&gt; 是人类好念、好口头下发的**别名**；机器校验使用 `.impl-package/revision-bindings.json` 中与 alias、artifact path 绑定的 Git blob OID。artifact 自身只声明 alias，不记录自身 commit SHA 或 blob OID，避免“为了写入自身 hash 又改变自身 hash”的循环依赖。对 owner 而言，Markdown 中的 revision set 与 binding validation 结论是完整交付面。

内部 sidecar 使用 [`../assets/templates/revision-bindings.json`](../assets/templates/revision-bindings.json) 的形状：`current` 选择当前 design/spec/attempt，`bindings` 保存每个已发布 revision 的 artifact path、validation mode 与 blob OID。语义 revision 的历史 binding 不覆盖、不复用；Git 继续提供 sidecar 自身的 provenance。lightweight Design 没有 design.md 时，D&lt;n&gt; 与 S&lt;n&gt; 可以分别绑定到同一个 spec.md blob。

生成或升级 revision 时，先完成 artifact 正文，再用 `git hash-object -- <path>` 计算最终工作树内容的 blob OID并写入 registry；commit 后用 `git rev-parse HEAD:<package-relative-path>` 复核。因为 registry 位于 artifact 外部，artifact 与 registry 可以在同一 commit 中稳定绑定。

validation mode 区分 contract artifact 与执行证据：

- design/spec 使用 `exact-blob`：当前 artifact blob 必须与 binding 完全相等；下文定义的 editorial correction rebinding 是唯一的同 alias 例外。
- plan 使用 `plan-contract-v1`：binding 保存 P revision 发布时的 baseline blob。restore 用 `git cat-file blob <oid>` 读取 baseline，把 baseline 与当前 plan 的 `## Execution Record` 正文统一替换为同一固定 marker 后比较；其他内容必须完全相等。ER 仍按 append-only 规则单独验证，因此正常补证不升级 P revision，策略、Composition、Planned Verification 或其他非 ER 内容变化仍会触发 P drift。

restore 或 gate evaluation 时，对 `current` 指向的 D/S/P binding 执行以下检查：

- artifact header 的 alias、registry revision、path 和 validation mode 一致，且 `exact-blob` 或 `plan-contract-v1` 检查通过：revision 可信，继续。
- design/spec 的 `exact-blob` 不匹配时，先判断是否为 **editorial correction**：只改正错字、格式、非规范性表述、普通链接或 provenance，且可证明不改变行为、Acceptance Semantics、设计选择、约束、安全/数据边界或 mutation authority。是则在既有 revision history 写明 correction、依据与 `contract impact=none`，用当前 artifact blob 更新同一 current D/S alias 的 binding，并复核；不重跑 Gate、不升级 alias。此例外不增加 JSON 字段或新 artifact，旧 blob 仍由 Git 与 revision history 追溯。
- 不能证明为 editorial correction，或其触及任何合同语义时，按 evidence 胜过 stale status 处理为 semantic revision：按本节上方四类重新分类、升级对应 revision 并登记新 binding；不得把语义变化伪装为同 alias rebinding。
- registry 缺失、重复 alias/path、`current` 指向不存在的 binding，或 Git 无法解析 blob：视为 P2 capture gap，不得默认相符。

gate entry 为了冻结历史判决，在可读正文写 `Revision set: D<n> / S<n> / P<n>` 与 `Binding validation: passed | failed`；精确 blob OID 和内部 sidecar 路径只放 HTML comment 形式的 machine audit metadata。P blob 是 plan-contract-v1 baseline，实际 ER evidence 由 comparison point + ER anchor 固定。gate 引用其他 artifact 的 blob，不产生自引用。

## 3. Attempt、plan 与 Composition

每次 implementation attempt 有唯一 Attempt ID：初始实现使用 initial，patch 使用其 patch-plan 文件 stem `YYYYMMDD-HHMM-&lt;patch-topic&gt;`；精确 stem 已存在时追加 `-02`、`-03`，且创建后不可改名。对应 plan 声明：

~~~text
Attempt ID: <initial | patch-id>
Design Revision: D<n>
Spec Revision: S<n>
Plan Revision: P<n>
Composition: tickets=<true|false>, dag=<true|false>
~~~

Composition 的唯一事实源是当前 attempt plan，不在 spec 中声明，也不从历史 attempt 继承。tickets 与 DAG 仍按两个正交 earn condition 决定：

| Composition | Current execution state | Acceptance state |
| --- | --- | --- |
| tickets=false, dag=false | 无 task artifact；需要中断恢复、独立交接或外部 gate 时才创建 `tasks/<attempt-id>-progress.md` attempt ledger | spec AC + plan Execution Record + gate entry |
| tickets=true, dag=false | ticket files；whole-ticket 恢复时按触发创建 `tasks/<ticket-id>-progress.md` | ticket Runtime Acceptance Status |
| tickets=false, dag=true | 必须持久化的 attempt DAG；task progress ledger 按需创建 | spec AC + plan Execution Record + gate entry |
| tickets=true, dag=true | attempt DAG；ticket 状态只可作为明确标注的只读投影，whole-ticket progress 按触发创建 | ticket Runtime Acceptance Status |

一个状态只有一个事实源。plan 不保存 task checklist、task runtime status 或 ticket 正文。简单 no-DAG attempt 没有结构化 task 状态；恢复需要由 Kind=attempt 的 progress ledger 解决，不通过给 plan 增加 executable task checklist。dag=true 时 DAG 是必需的持久过程记录，不得只留在对话/handoff 或回写 plan。

plan 在 attempt 活动期间可通过 Plan Revision: P&lt;n&gt; 修订策略、Composition 或验证选择；P revision 在该 attempt 内从 P1 单调递增，每次修订记录摘要与 artifact relocation，并在内部 sidecar 追加新 blob binding。terminal gate verdict 后冻结。Composition 变化只影响当前 attempt，不修改 D/S revision；迁移后不得保留两个可写 execution-state source。

### 派生 lifecycle 与 integration qualifier

plan 不保存可手工修改的 `Status`。attempt lifecycle 从 registry 与 gate ledger 派生：

- **Draft**：plan artifact 已存在，但尚未被内部 sidecar 的 `current.attempt` 选中，或其 P binding 尚未通过一致性检查；不得进入执行。
- **Active**：`current.attempt` 唯一指向该 plan/P binding，且该 Attempt ID 尚无 terminal gate entry。
- **Frozen**：该 Attempt ID 已有 pass/fail/defer terminal entry；plan 不再修改，后续变化创建 patch attempt。

`Integrated, gate open` 是报告 qualifier，不是第四种可写 lifecycle status：当 plan 声明的 target branch 已包含当前 comparison point、但 attempt 仍为 Active 时派生。默认 integration order 是 gate-before-merge；只有 plan 记录 owner-approved pre-gate integration strategy 与证据时，才允许先合入。此后 terminal pass 与 closed claim 必须使用目标分支上的新鲜证据；合入本身不等于 gate 关闭。

**Plan Revision 变化后，已创建的 ticket/DAG 必须跟进，但不默认全部重做**：每个 tickets/&lt;ticket&gt;.md 与当前 attempt DAG 都声明自己创建/最后确认时所依据的 `Plan Revision: P<n>`。plan 从 P&lt;n&gt; 升级到 P&lt;n+1&gt; 后，仍声明旧 P&lt;n&gt; 的 artifact 是 `NEEDS-REVALIDATION`，该状态表示需要做影响判断，不表示正文必然失效。先根据 P revision 的实际 delta 列出受影响 subset：受影响内容定向修订和验证；未受影响内容可批量确认仍成立并机械更新 Plan Revision 引用，无需重新生成、逐项重审或重跑验收。restore 必须完成这次 scoped reconciliation 后再使用相关 artifact。

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

typed edge 图无环还不够；ticket 与 DAG 共存时必须检查 **readiness satisfiability**。对每个 ticket AC，解析其必需 evidence producer；若 producer task 或其任一传递依赖要求该 ticket 先达到 Runtime Acceptance Status，则形成 acceptance-evidence semantic cycle，即使 ticket edge 图和 task DAG 各自都无环也必须拒绝。每项 AC 至少存在一条不经过自身 acceptance 的可执行 evidence path，才能把相关 ticket/DAG 当作可用输入。

semantic cycle 首先视为 decomposition/readiness defect，不自动升级为 contract drift 或 owner decision。若修正只改变 typed edge 分类、task 顺序、evidence producer/owner 投影或对应 artifact 引用，并且保持 D/S、业务范围、AC、Composition、安全约束与外部 mutation authority 不变，则 owning skill 应修正、完成必要的 P/ticket/DAG revalidation 后继续执行。只有修正会改变上述任一业务或授权事实，或存在多个会产生不同业务结果的合理方案时才请求 owner 决定。请求前必须说清选项及其不同业务结果；无法指出业务结果差异时，不得把机械修正报告为 owner blocker。

## 5. Contract、task 与 acceptance 分工

- design 保存选择与 rationale。
- spec 保存 interface、seam contract、contract/acceptance owner、affected targets、compatibility window、migration/rollback contract、全局约束与 Acceptance Semantics。
- plan 保存本 attempt 的执行顺序、具体迁移操作、验证选择和过程证据。
- DAG task 保存依赖、execution ownership、contributes-to / enables 与 seam execution owner。
- ticket 保存独立 delivery slice、AC 与 Runtime Acceptance Status。
- gate entry 保存对绑定 revision 的判决摘要，不保存完整验证 checklist。

acceptance target 使用 &lt;ticket-id&gt;:AC-&lt;n&gt; 或 spec:AC-&lt;n&gt;。每个引用必须解析到现有 AC。execution seam 必须有当前 attempt 的 dag=true 和 DAG execution owner；contract 与 acceptance 语义仍在 spec，不能在 plan 或 DAG 中建立副本。

## 6. Plan verification 与 findings 分流

plan 包含两类验证信息：

- Planned Verification：引用权威 test/review policy，记录本 attempt 选择的检查、预期结果与 evidence owner；不复制通用 Data Safety、UI Evidence、Real Route Safety 等整套模板。
- append-only Execution Record：每条使用稳定 anchor，记录实际命令/检查、结果、证据路径、执行时间与适用的 D/S/P revision。旧 record 不回改，后续补证新增 record。

`verification-before-completion` 是 completion claim 的 evidence gate，不是新的验证清单：适用 review、findings 分流和 Stage 7 准备完成后，写 terminal `pass` entry 前必须用当前 revision/worktree/environment 审计拟声明的 pass。可复用 provenance 清晰且未被后续变化影响的 ER/review/CI/smoke evidence；只补跑 stale、冲突、跨 revision/environment 或不完整的部分。审计不通过时不得写 pass，应报告 `implemented, not verified` 或具体 pending gate。

terminal metadata commit、目标分支合入或相关环境变化之后，任何 complete、closed、merge-ready 或 release-ready 声明都必须重新执行该审计。纯 metadata delta 不自动使行为测试失效，但最终 HEAD、工作树状态、目标分支集成状态和声明所依赖的 metadata/proof 必须与证据对齐。该 gate 不进入 DAG，也不按 ticket/task 重复运行。

findings.md 是发现 inbox。gate evaluation 前必须分流：设计决定进 design，规范性行为进 spec，长期项目知识进入 gate Durable Deltas → _pending.md，验证证据进 plan Execution Record，其余调查事实/风险保留在 findings。findings 不成为第二 SoT。

**这是任意 terminal verdict（pass/fail/defer）的硬性前置条件，力度等同 Stage 7**：findings.md 中存在未分流、且不属于"已验证调查事实/风险，保留在 findings 是正确去处"的条目时，不得写入 pass、fail 或 defer 的 terminal gate entry——不只是 pass。blocked entry 不受此约束（blocked 本来就允许如实记录 capture gap，后续用新 entry 补齐）。

## 7. Append-only Gate Ledger 与 Stage 7

package 永远只有一个 gate.md。它是 newest-first 的 append-only gate evaluation ledger；每次 evaluation 在文件顶部说明之后插入新 entry，旧 entry 不修改。

gate.md 允许在正式 ledger（本节格式的 entry 序列）之前保留至多一行可变的"当前状态一览"（例如 `状态：<最新 entry 的 verdict 人话摘要>`），方便 owner 一眼看到当前状态，不必翻到最新 entry。这一行不属于 append-only ledger，可以随时改写，但只能用来复述最新 entry 已经写明的内容——不能携带任何最新 entry 里找不到的判断或证据。发现这行和最新 entry 不一致时，以最新 entry 为准，且应该把这行改到和最新 entry 一致，而不是反过来改 entry。除这一行外，ledger 正文（entry 块本身，含历史遗留下来、格式早于本节模板的旧 gate.md 里的 Gate Decision/Verification 等判决与证据内容）保持严格 append-only，旧内容一律不回改，只能通过新 entry 补充或更正。

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

- G 编号在同一 Attempt ID 内从 G1 单调递增，取该 attempt 已有最大编号加一，不复用。最新 entry 表示当前 gate evaluation；同一 attempt 从 blocked 到 pass 时新增 G&lt;n+1&gt;，通过 Supersedes 指向该 attempt 的前一条 evaluation。
- pass、fail、defer 是 terminal verdict；对应 plan 冻结。terminal 后的新变更必须创建新 patch attempt。
- gate 尚未 terminal 时，D/S/P revision 或证据变化通过新 plan revision、Execution Record 和 gate entry 表达，旧 entry 不回改。
- Git diff/blame 提供 provenance；不增加额外防篡改机制。

每个 gate entry 的 Durable Deltas 仍是唯一 capture surface：

~~~text
gate entry Durable Deltas -> project _pending.md -> backfill audit/apply/verify
~~~

`gate entry Durable Deltas → _pending.md / truth pointer / 必要 stub` 属于 Stage 7，是任意 terminal verdict 的强制前置；`$backfill-stable-docs` audit/apply/verify 位于 terminal gate 之后，只作为可选维护提示，可以延期且不阻塞 gate、任务 closed 或当前交付。实际调用需要用户明确要求、已批准维护计划或明确进入周期维护流程；提示本身不构成 audit/apply/verify 授权。

每条 delta 记录 delta-id、destination、source、statement、affected modules、authority、evidence 与 pending/truth-pointer 校验。去重键是 &lt;destination&gt;|&lt;delta-id&gt;。无 durable delta 时写 none 和理由。

append-only 写入顺序：先保留下一个 G id、固定 comparison point 与 plan ER anchor，组装完整 entry；若 verdict 将是 terminal（pass/fail/defer），先用该保留 id 完成 _pending.md 注册、受影响 module spec truth pointer 与必要 stub；若拟写 `pass`，再调用 `verification-before-completion` 审计该 pass claim；通过后才把完成态 entry 一次性插入 gate.md。blocked entry 可如实记录 capture gap；后续补齐通过新 entry 表达，不回改 blocked entry。禁止先写“临时 gate entry”再原地补字段。

## 8. Shared validation checklist

- design/spec 各有唯一当前 revision（lightweight Design 的 D revision 在 spec 可解析），正文无并行新旧合同；revision history 足以解释 supersession。
- 当前 attempt plan 声明 Attempt ID、D/S/P revision 与唯一 Composition，且与 earned artifacts 一致。
- 内部 sidecar 的 `current` 唯一选择当前 design/spec/attempt；每个 D/S/P alias 都能解析到唯一 artifact/mode/blob binding，design/spec 通过 exact-blob，plan 通过 plan-contract-v1 且 ER append-only。owner-facing Markdown 已直接写出 revision set、派生 lifecycle/integration qualifier 与 binding validation 结论。
- 每个 earned ticket/DAG 声明的 Plan Revision 与当前 plan 的 P 号一致；不一致的按 NEEDS-REVALIDATION 处理，不得当作可用状态。
- 任意 terminal entry 写入前，Durable Deltas 已完成 `_pending.md` 注册、truth pointer 与必要 stub；无 delta 时已记录 `none + reason`。gate 后 backfill audit/apply/verify 不属于 terminal validation checklist。
- package 同时最多一个由 registry 选中的 Active attempt；未选中的 plan 是 Draft，terminal entry 对应 attempt 是 Frozen。多个 current attempt、或多个被选中且未冻结的 plan 是 lifecycle violation，restore 必须停止。
- plan 无 task runtime status、ticket 正文或长期 contract；通用验证政策只引用，不复制。
- 每项 AC 有 evidence producer/manual owner；task-to-AC 与 typed dependency 引用均可解析且无环。
- ticket AC 的 evidence producer 与 task 传递依赖通过 readiness satisfiability 检查；不存在 producer 被自身 ticket acceptance 阻塞的 semantic cycle。
- execution seam 的 contract 在 spec，execution owner 在当前 attempt DAG，acceptance evidence 在 plan/gate 或 ticket。
- plan Execution Record 使用稳定 anchor 且 append-only；gate evidence 链接可解析到对应 record。
- gate entry newest-first、旧块未修改；G 编号不复用，Supersedes、revision、comparison point、ER anchor、verdict 与 Durable Deltas 完整。
- findings.md 在写入任意 terminal entry（pass/fail/defer，不只 pass）前已完成分流。
- terminal pass entry 写入前，`verification-before-completion` 已将拟声明的 pass 与当前 revision/worktree/environment 及可追溯 evidence 对齐；未通过时没有写 pass。
- Active attempt 若已先合入 target branch，plan 已记录 owner-approved pre-gate integration strategy，状态对外报告为 `Integrated, gate open`，最终 pass/closed evidence 来自目标分支。
- terminal gate 后 plan 已冻结；重新 patch 前已完成 Module Knowledge Watermark 对账，不是凭印象假设未变。
