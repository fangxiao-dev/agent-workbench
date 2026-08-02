---
name: create-task-dag
description: >
  当已批准 implementation plan 需要转为最小横向 Task DAG，以协调 ownership、并行和已知依赖时使用。
  Task 不取代 Ticket 验收；执行和 ticket acceptance 分别交由 subagent-driven-development 与 dev-with-track。
---

# Create Task DAG

把当前 implementation package 的 approved Plan 与已形成的 Draft/Approved Ticket 输入转成最小横向执行图。**Ticket** 是纵向、独立可验收的功能/质量单元；**Task** 是用于 ownership、并行和依赖协调的横向执行拆分；**DAG** 只描述 Task 之间的执行依赖。Task 与 Ticket 是多对多 contribution，不是父子树：Task `DONE` 只表示其局部产出和证据可交给现有 Working Branch owner 集成，绝不自动表示任一 Ticket 已验收。Draft Ticket 是合法的 decomposition 输入，不代表 Ticket 已批准；Ticket publication 与 DAG 一起在同一个 review bundle 中完成。

本 skill 的共享语义唯一引用 `skills/impl-package/references/impl-package-composition-contract.md`。不得在本 skill 重定义 canonical status、readiness resolution、composition migration 或 Stage 7。不要引入 Loose/Strict DAG、Workstream、Integrator、Seam Task 或新的 Task 类型；feature、test、documentation、verification 和 seaming 都是同一种 Task。

## 输入与路由边界

可开始 DAG decomposition 的有效输入是当前 attempt plan 声明 `dag=true`，以及：

1. `tickets=true, dag=true`：当前 plan 和同 Attempt ID、完整且相关的 Draft Ticket 集合（或已批准的同一 bundle Ticket 集合）。Draft 是正常输入，不需要先经过独立 Ticket approval。
2. `tickets=false, dag=true`：当前 plan 和 gated `spec.md`；验收仍以 `spec:AC-n` 为准，不创建或伪造 Ticket。

按当前 attempt plan 路由，不能从历史 attempt 或单个 Ticket 猜测：

- `tickets=true, dag=true` 且尚无完整 Draft/Approved Ticket：路由 `to-tickets mode=draft`。
- 已有完整 Draft Ticket：直接开始最小 DAG；联合校验通过后，将 Tickets + DAG 一起交 owner review，再由 `to-tickets mode=publish` 原子发布，不在 DAG 阶段自行标记 Approved。
- `tickets=true, dag=true` 且已有相关 Approved Ticket：仅在当前 bundle 的 revision/binding 仍有效时复用并验证；发现实质变化时按 scoped reconciliation 处理并重新联合 review。
- `tickets=false, dag=true` 且 gated spec 有稳定 AC：直接创建 no-ticket DAG。
- 任一 `dag=false`：不创建 DAG；保留既有 ticket/spec 验收路径。
- Composition 不一致、plan/spec/AC 缺失或漂移：路由 `impl-planning` 或 `req-align` 修正后再继续。

本 skill 不切 delivery slice、不发布 tracker、不把 Draft 变 Approved。DAG 必须持久化在当前 attempt 的 `dag.md` 或 patch DAG；不可只留在对话或写进 `plan.md`。

## 联合拆解校验（Ticket ↔ DAG）

当 `tickets=true, dag=true` 时，DAG 生成的后半段必须与完整 Draft Ticket 集合一起完成一次联合校验；这是一项 review-ready 条件，不是独立的 DAG approval gate。校验结果进入 runner-neutral handoff/既有 Execution Record，不新增持久状态源或 manifest。至少覆盖：

- **Coverage**：每个 earned Ticket 都有一个或多个 Task 的 `Contributes to tickets` 贡献路径；Task 不指向不存在、历史 Attempt 或其他 package 的 Ticket，且不把未挣得的 Ticket 伪造为验收目标。
- **Typed dependencies**：Ticket 的 `implementation|acceptance|release` blockers 与 Task `Known depends on` 保持可解释且无环；只把 implementation edge 作为执行 readiness 前置，其他 edge 不被降格为调度依赖。
- **Ownership/contribution**：每个 Task 有一个不重叠的 primary ownership；贡献映射允许多对多，但 Ticket 不保存 worker ownership，DAG 不把贡献映射变成父子树或 Task→AC 验收映射。
- **AC evidence feasibility**：每个 Ticket AC 仍由 Ticket/Spec 声明 planned evidence 或 manual owner；DAG 只能证明存在可产出 evidence 的执行贡献并发现循环，不复制 AC 文本或替代正式 acceptance。
- **Gate/P binding**：Ticket、DAG、Plan 与同一 package/Attempt、D/S/P revision 和 binding 对齐；DAG 的依赖、ownership 或 contribution 不能绕过 plan verification、safety authorization、external gate 或 Working Branch owner integration。

任何一项失败都保持 bundle 在 `drafting`，修正后重新校验；全部 earned artifacts 齐备且校验通过后才可报告 `ready-for-review`。`ready-for-review` 后交回 `impl-planning` 选择 fresh、适用的 `$plan-review`；只有 admission `ready` 或 normal/focused review 已验证 ledger `cleared` 后才请求 owner 一次批准 Tickets + DAG，随后 `to-tickets mode=publish` 才能执行 Ticket publication，bundle 才能进入 execution preflight。

## 最小记录与拆分规则

DAG 不是 Ticket 的默认伴随物。只有当前 plan 已按 shared Composition triage 证明：至少两项工作可安全独立启动，且删去 DAG 会丢失真实 blocker、跨 owner/跨 session handoff 或 primary ownership 边界的协调信息，才创建 DAG。单一 owner 下的串行实现、自然步骤顺序、多个文件或多个 Ticket 都不构成依据；此时保持 `tickets=true, dag=false`。Ticket/Task 接近一对一（例如 5 个 Ticket 对 6 个 Task）时，先证明每个 Task 的独立执行或协调价值；不能证明则不建 DAG。

默认只使用下列模板。`Integration responsibility` 是现有 Working Branch owner 的职责说明，不是新角色、ID、状态机或 artifact：

```markdown
# Task DAG

Integration responsibility: Working Branch owner

| Task | Primary ownership | Known depends on | Contributes to tickets | Known seam / risk |
| --- | --- | --- | --- | --- |
| T1 | ... | none | TST-01 | ... |
| T2 | ... | T1 | TST-02, TST-03 | ... |
```

- 只记录已知、确定的依赖；不要为证明所有潜在依赖而做大量预研。
- Primary ownership 按模块、目录或共享 seam 划分，不必穷举文件。只有能独立启动、且不抢占其他 Task primary ownership 的工作才拆 Task。
- 能形成独立纵向验收结果的工作，拆成 Ticket，不要增加复杂 Task。
- 共享 migration、tenant/auth/permission、安全边界、公共 contract 或 rollback 边界的工作默认不拆；保持一个串行 Task 或一个 Ticket。
- 跨模块、跨阶段或 seaming 本身不等于必须由 Working Branch owner 亲自实现。上游接口与风险取舍已经闭合后，若连接层的写入范围可隔离、结果可独立复核且失败会交回 owner，可增加一个依赖上游 Task 的普通集成性 Task；它不获得新类型、状态或验收权。
- 默认不写完整 Task Contract、所有 consumer、完整 review basis、cohort/lanes 或逐 Task formal review。共享 seam、跨 session handoff 或高风险边界真实出现时，仅补受影响 Task 的最小必要细节。
- 有 Ticket 时 `Contributes to tickets` 写 ticket ID；no-ticket DAG 写 `none`，由 spec AC、plan Execution Record 和 gate 保持验收链。该列只表示执行贡献，不建立 Task→AC acceptance mapping。

Task identity 的唯一来源是 state CLI：调用 `allocate-task-id --attempt <attempt>` 取得下一个 ID；返回的 `attempt:Tn` 是完整 identity，DAG 中只显示该 attempt 内的 `Tn`。不要手工扫描或发明编号格式。创建或更新 DAG 后，`preflight-register`/正式登记会以同一 grammar 初始化 runtime records 并刷新 Task 投影；每个 Task 有一个 runtime record。不要默认创建独立 progress 文件。仅 Task 实际 BLOCKED、跨 session handoff、需重试或由主 session 派发并行 subagent 时，才记录 `tasks/Tn-progress.md`；内容只包括 blocker/原因、已做 evidence、下一可执行动作及受影响 Ticket，不能复制 Ticket AC。Ticket 的最小恢复摘要由主 session写回 Ticket 自身，不由本 skill 或 Task worker 维护。

## 状态、BLOCKED 与集成

保留最小状态：`PENDING`、`RUNNING`、`DONE`、`BLOCKED`。不得写入 `NEEDS_SEAM`；共享 seam 只是 BLOCKED 原因，或由新增/调整的普通 Task 完成。

- `DONE`：横向产出和局部证据可交给 Working Branch owner 集成；`DONE ≠ Ticket accepted`。
- `BLOCKED`：Task 暂时无法继续，记录一句 blocker 原因、建议动作及受影响 Ticket（如有）。发现共享 seam 时不擅自扩大 primary ownership。

Working Branch owner 在并行 Task 返回、出现 BLOCKED、或 Ticket 最终验收前执行 integration step：合并 Task 产出，处理已出现的 seam/冲突，运行共享验证和正式 review，将 evidence 映射回 Ticket AC，再决定 Ticket 是否可验收。不要把该步骤抽象成新的身份或产物。

Ticket 最终验收前只扫描 contributes-to 该 Ticket 的 BLOCKED Task：若未完成内容影响其 AC、已声明行为或风险边界，先解除阻塞，Ticket 不可通过；不贡献且不影响该 Ticket 的 blocker 不阻塞它。若真实影响扩大，先更新 contribution mapping，再按 blocker 处理，不能静默绕过。

最终 package review 前，Working Branch owner 全局扫描未终结 Task：全部必须为 `DONE`，或有明确、已批准且带理由的 `WAIVED` / `SUPERSEDED`，不得遗留 `BLOCKED`。最终判断仍以 Ticket AC evidence 和 active Spec 全覆盖为中心，不以 Task 数量或状态替代。

## 工作流

1. 读取当前 plan、gated spec、完整同 Attempt Draft/Approved Ticket 集合（如有）、仓库约束与现有 DAG/runtime state；确认可验收目标及外部 mutation 红线。
2. 用最小表格划分可安全独立启动的 Task；记录确定依赖、primary ownership、Ticket contribution 和已知 seam/risk。不能安全并行就不拆。
3. 运行本节联合 Ticket↔DAG 校验，确认 coverage、typed dependency、ownership/contribution、AC evidence feasibility 与 gate/P binding；失败则返回 `to-tickets`/`impl-planning` 修正，不发布任何 Ticket。
4. 持久化最小 `dag.md`/patch DAG、联合校验结果与 review handoff，并报告 `ready-for-review`；交回 `impl-planning` 选择 fresh、适用的 `$plan-review`，此时不派发 worker、不创建 Task progress、不收集执行 evidence，也不触发 Ticket publication。
5. admission `ready` 或正常 full plan-review 返回 `cleared` 后，owner 批准完整 bundle、`to-tickets mode=publish` 成功并进入 execution preflight 后，由 `dev-with-track`/`subagent-driven-development` 按 DAG 派发 primary ownership 不重叠、依赖已释放的 Task；普通 prompt 只给目标、ownership、禁改范围、依赖、贡献 Ticket、局部验证与 BLOCKED 返回格式。集成性 Task 还要给出冻结接口、连接层写入范围、核心禁改范围及正反向证明；这些信息属于派发输入，不新增 DAG artifact 或角色。
6. 执行阶段收集局部 evidence；BLOCKED 直接记录原因、建议动作和影响 Ticket。由 Working Branch owner 集成并执行共享验证和 Ticket 层正式 review；本 skill 不把局部验证升格为 Ticket acceptance。

高风险 Task（tenant isolation、auth/permission、migration、真实外部写入、金额、不可逆数据风险）可按实际 diff 要求更严格验证或 review；这是同一 Task 的额外质量要求，不是 Strict Task 机制。优先选择不拆，或拆成可独立验收的 Ticket。

## 联合 review 与后续修订

当完整 Ticket 集合与 DAG 通过联合校验后，状态只能报告为 `ready-for-review`；Tickets 与 DAG 作为一个 revision-bound bundle 交回 `impl-planning` 完成 fresh admission，之后才交由 owner 一次 review/approval。owner 批准前，DAG 不得触发 Ticket publication；批准后由 `to-tickets mode=publish` 原子完成 Draft→Approved，并共同进入 execution preflight。`in-progress`/`completed` 仍由 Attempt、Task、Ticket acceptance 与 gate 的既有运行时事实派生，不在 DAG 中新增状态字段。

任何影响 acceptance boundary、typed blocker、Task contribution、primary ownership、执行顺序、AC evidence feasibility、Composition、gate/safety boundary 或 D/S/P binding 的实质变更都会使受影响 bundle approval 失效。按影响范围修订 Ticket 与 DAG 节点、重新运行联合校验并重新 review；未受影响节点可以批量确认，未受影响部分可机械更新 Plan Revision。仅格式、引用、分类或不改变上述语义的机械投影修正不要求重新审批，但必须保留在既有 handoff/Execution Record 中，不能静默改写已批准结构。

## 示例：测试系统最小图

以下示例针对 `D:\CodeSpace\kaispan-dev\docs\implementations\2026-07-17-testing-system`，primary ownership 分别落在 `D:\CodeSpace\kaispan-dev\packages\db` 与 `D:\CodeSpace\kaispan-dev\apps\api` 的相关范围：

```markdown
# Task DAG

Integration responsibility: Working Branch owner

| Task | Primary ownership | Known depends on | Contributes to tickets | Known seam / risk |
| --- | --- | --- | --- | --- |
| T1 | TEST_DATABASE_URL runner、env、CI、db test support | none | TST-01 | 后续 db/api tests 消费 runner |
| T2 | FileObject persistence integration test | T1 | TST-02 | 可能消费 fixture cleanup seam |
| T3 | Idempotency persistence integration test | T1 | TST-03 | 可能消费 fixture cleanup seam |
| T4 | P0 case pointers | T2, T3 | TST-04 | 只消费真实 evidence |
| T5 | E2E readiness investigation | none | TST-05 | 不安装 browser runner |
```

T1 完成不自动验收 TST-01，仍由 TST-01 的 evidence/review 判定。T2/T3 的实际 fixture seam 可在执行时成为 BLOCKED，不在规划期强行穷尽；T4 只在 T2/T3 的真实 evidence 存在后推进。T5 可独立完成且不影响其它 Ticket：T2 的 blocker 不影响 TST-05 时，TST-05 可单独验收；T2 若影响 TST-02，TST-02 不可通过。最终 package review 前仍须全局扫完所有 BLOCKED Task。

## 示例：不可拆边界

若同一 Ticket 同时修改 `D:\CodeSpace\kaispan-dev\packages\db\prisma\schema.prisma` 与 `D:\CodeSpace\kaispan-dev\docs\platform\identity-access\hands-on-knowledge\implementation\rbac-integration.md`，涵盖 tenant model、migration、RBAC resource scope 和 rollback 行为，则共享 tenant/data integrity/security/rollback 边界，保持一个串行 Task。若能抽出独立、纵向可验收的结果，拆 Ticket，不要升级为“严格” Task。

## 输出与汇报

输出持久化的最小 DAG、条件化的 Task progress（如 earned）、联合校验结果和实际验证 evidence。Ticket 的长期验收事实仍是 AC、evidence 和 acceptance status；Phase/Next/Progress 只提供恢复索引。向 owner 汇报进度或最终状态时使用 `talk-to-boss`：先说明总范围、已完成阶段、剩余工作、是否 closed 和需要的 owner 决定；再给出 Task/validation 证据。runner-neutral handoff 必须列出当前 Composition、Draft/Approved Ticket 状态、DAG 路径、coverage/typed dependency/ownership/contribution/AC evidence/gate-P binding 结果、未决 owner decision，以及下一步是 `to-tickets mode=publish`（owner 已批准后）还是 execution preflight。
