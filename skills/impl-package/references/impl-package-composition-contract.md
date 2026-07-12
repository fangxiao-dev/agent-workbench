# Impl-Package Artifact Lifecycle Contract

> **Normative shared contract.** req-align、impl-planning、to-tickets、create-task-dag 与 dev-with-track 必须引用本文件，不得各自重定义 artifact lifecycle、Composition、readiness、gate 或 Stage 7 语义。

## 1. Package identity 与 SoT 生命周期

新 package 使用 UTC 日期生成不可变的 YYMMDD-&lt;topic-slug&gt; package-id；同名时追加 -02、-03。已有 legacy package-id 不改名，post-gate patch 继续复用 owning package-id。

任务包包含两类文档：

- design.md 与 spec.md 是活动变更期间的当前设计 SoT。它们保持当前有效正文，历史变化只进入紧凑 revision/superseded 记录。
- plan、tickets、DAG、progress 与 gate entry 属于某次 implementation attempt，是过程与判决记录，不是长期行为合同。

package gate 关闭并完成 backfill 后，module knowledge 重新成为产品当前 SoT。后续重新 patch 时，先将 package design/spec 与当前 module knowledge 和代码对账，再激活并修订 package SoT。

## 2. Design/Spec revision 与 drift

design.md（存在时）或 spec.md 的 Design Gate Record 声明唯一当前 Design Revision: D&lt;n&gt;；spec.md 声明唯一当前 Spec Revision: S&lt;n&gt;。lightweight Design 不建 design.md 时，D revision 仍必须在 spec 中可解析。

- 实现偏离现有 spec，但预期行为不变：复用 D/S revision，创建新 attempt。
- 行为、数据、边界、失败恢复、约束或 Acceptance Semantics 改变：升级 S revision，只重跑 Spec Gate。
- 设计选择或 rationale 改变：先升级 D revision 并重跑 Design Gate，再升级 S revision 并重跑 Spec Gate。
- 旧正文不并排保留；在 revision history 中记录 previous/new、变更摘要、authority、日期与 superseded 说明，完整 provenance 由 Git 提供。

Design/Spec Gate 只证明其绑定的 revision；旧 gate entry 不证明后续 revision。

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

plan 在 attempt 活动期间可通过 Plan Revision: P&lt;n&gt; 修订策略、Composition 或验证选择；P revision 在该 attempt 内从 P1 单调递增，每次修订记录摘要与 artifact relocation。terminal gate verdict 后冻结。Composition 变化只影响当前 attempt，不修改 D/S revision；迁移后不得保留两个可写 execution-state source。

可选 dispatch shorthand 只展开当前 attempt Composition，不是 sizing gate：

| Shorthand | Composition |
| --- | --- |
| S | tickets=false, dag=false |
| M | tickets=true, dag=false |
| L | tickets=true, dag=true |
| D | tickets=false, dag=true |

实际 earn condition 与 shorthand 冲突时修正 shorthand，不制造 ticket 或 DAG。

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

findings.md 是发现 inbox。gate evaluation 前必须分流：设计决定进 design，规范性行为进 spec，长期项目知识进入 gate Durable Deltas → _pending.md，验证证据进 plan Execution Record，其余调查事实/风险保留在 findings。findings 不成为第二 SoT。

## 7. Append-only Gate Ledger 与 Stage 7

package 永远只有一个 gate.md。它是 newest-first 的 append-only gate evaluation ledger；每次 evaluation 在文件顶部说明之后插入新 entry，旧 entry 不修改。

每个 entry 使用 &lt;attempt-id&gt;-G&lt;n&gt;，并记录：

~~~markdown
## <attempt-id>-G<n> · <pass|fail|blocked|defer>
- Attempt ID:
- Supersedes: <gate-entry-id | none>
- Evaluated at:
- Design revision:
- Spec revision:
- Plan revision:
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
gate entry Durable Deltas -> project _pending.md -> backfill report/apply
~~~

每条 delta 记录 delta-id、destination、source、statement、affected modules、authority、evidence 与 pending/truth-pointer 校验。去重键是 &lt;destination&gt;|&lt;delta-id&gt;。无 durable delta 时写 none 和理由。

append-only 写入顺序：先保留下一个 G id、固定 comparison point 与 plan ER anchor，组装完整 entry；若 verdict 将是 terminal（pass/fail/defer），先用该保留 id 完成 _pending.md 注册、受影响 module spec truth pointer 与必要 stub，再把完成态 entry 一次性插入 gate.md。blocked entry 可如实记录 capture gap；后续补齐通过新 entry 表达，不回改 blocked entry。禁止先写“临时 gate entry”再原地补字段。

## 8. Shared validation checklist

- design/spec 各有唯一当前 revision（lightweight Design 的 D revision 在 spec 可解析），正文无并行新旧合同；revision history 足以解释 supersession。
- 当前 attempt plan 声明 Attempt ID、D/S/P revision 与唯一 Composition，且与 earned artifacts 一致。
- package 同时最多一个 active attempt；多个未被 terminal entry 冻结的 plan 是 lifecycle violation，restore 必须停止。
- plan 无 task runtime status、ticket 正文或长期 contract；通用验证政策只引用，不复制。
- 每项 AC 有 evidence producer/manual owner；task-to-AC 与 typed dependency 引用均可解析且无环。
- execution seam 的 contract 在 spec，execution owner 在当前 attempt DAG，acceptance evidence 在 plan/gate 或 ticket。
- plan Execution Record 使用稳定 anchor 且 append-only；gate evidence 链接可解析到对应 record。
- gate entry newest-first、旧块未修改；G 编号不复用，Supersedes、revision、comparison point、ER anchor、verdict 与 Durable Deltas 完整。
- terminal gate 后 plan 已冻结；重新 patch 前已与当前 module knowledge/code 对账。
