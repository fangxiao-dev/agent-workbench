---
name: create-task-dag
description: >
  当已批准 implementation plan 需要转为最小横向 Task DAG，以协调 ownership、并行和已知依赖时使用。
  Task 不取代 Ticket 验收；执行和 ticket acceptance 分别交由 subagent-driven-development 与 dev-with-track。
---

# Create Task DAG

把当前 implementation package 的已批准输入转成最小横向执行图。**Ticket** 是纵向、独立可验收的功能/质量单元；**Task** 是用于 ownership、并行和依赖协调的横向执行拆分；**DAG** 只描述 Task 之间的执行依赖。Task 与 Ticket 是多对多 contribution，不是父子树：Task `DONE` 只表示其局部产出和证据可交给现有 Working Branch owner 集成，绝不自动表示任一 Ticket 已验收。

本 skill 的共享语义唯一引用 `skills/impl-package/references/impl-package-composition-contract.md`。不得在本 skill 重定义 canonical status、readiness resolution、composition migration 或 Stage 7。不要引入 Loose/Strict DAG、Workstream、Integrator、Seam Task 或新的 Task 类型；feature、test、documentation、verification 和 seaming 都是同一种 Task。

## 输入与路由边界

可开始 DAG decomposition 的有效输入是当前 attempt plan 声明 `dag=true`，以及：

1. `tickets=true, dag=true`：当前 plan 和同 Attempt ID、相关、Approved 的 Ticket 子集。
2. `tickets=false, dag=true`：当前 plan 和 gated `spec.md`；验收仍以 `spec:AC-n` 为准，不创建或伪造 Ticket。

按当前 attempt plan 路由，不能从历史 attempt 或单个 Ticket 猜测：

- `tickets=true, dag=true` 且尚无 Draft/Approved Ticket：路由 `to-tickets mode=draft`。
- 已有 Draft Ticket：等待明确 owner approval 后路由 `to-tickets mode=publish`；本 skill 不标记 Approved。
- `tickets=true, dag=true` 且已有相关 Approved Ticket：开始最小 DAG。
- `tickets=false, dag=true` 且 gated spec 有稳定 AC：直接创建 no-ticket DAG。
- 任一 `dag=false`：不创建 DAG；保留既有 ticket/spec 验收路径。
- Composition 不一致、plan/spec/AC 缺失或漂移：路由 `impl-planning` 或 `req-align` 修正后再继续。

本 skill 不切 delivery slice、不发布 tracker、不把 Draft 变 Approved。DAG 必须持久化在当前 attempt 的 `dag.md` 或 patch DAG；不可只留在对话或写进 `plan.md`。

## 最小记录与拆分规则

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
- 默认不写完整 Task Contract、所有 consumer、完整 review basis、cohort/lanes 或逐 Task formal review。共享 seam、跨 session handoff 或高风险边界真实出现时，仅补受影响 Task 的最小必要细节。
- 有 Ticket 时 `Contributes to tickets` 写 ticket ID；no-ticket DAG 写 `none`，由 spec AC、plan Execution Record 和 gate 保持验收链。该列只表示执行贡献，不建立 Task→AC acceptance mapping。

创建或更新 DAG 后，按现有 runtime-state 机制初始化并刷新 Task 投影；每个 Task 有一个 runtime record。不要为每个 Task 或每个 Ticket 默认创建 progress。仅 Task 实际 BLOCKED、跨 session handoff、需重试或由主 session 派发并行 subagent 时，才记录 `tasks/Tn-progress.md`；内容只包括 blocker/原因、已做 evidence、下一可执行动作及受影响 Ticket，不能复制 Ticket AC 或维护第二套 Ticket 状态。

## 状态、BLOCKED 与集成

保留最小状态：`PENDING`、`RUNNING`、`DONE`、`BLOCKED`。不得写入 `NEEDS_SEAM`；共享 seam 只是 BLOCKED 原因，或由新增/调整的普通 Task 完成。

- `DONE`：横向产出和局部证据可交给 Working Branch owner 集成；`DONE ≠ Ticket accepted`。
- `BLOCKED`：Task 暂时无法继续，记录一句 blocker 原因、建议动作及受影响 Ticket（如有）。发现共享 seam 时不擅自扩大 primary ownership。

Working Branch owner 在并行 Task 返回、出现 BLOCKED、或 Ticket 最终验收前执行 integration step：合并 Task 产出，处理已出现的 seam/冲突，运行共享验证和正式 review，将 evidence 映射回 Ticket AC，再决定 Ticket 是否可验收。不要把该步骤抽象成新的身份或产物。

Ticket 最终验收前只扫描 contributes-to 该 Ticket 的 BLOCKED Task：若未完成内容影响其 AC、已声明行为或风险边界，先解除阻塞，Ticket 不可通过；不贡献且不影响该 Ticket 的 blocker 不阻塞它。若真实影响扩大，先更新 contribution mapping，再按 blocker 处理，不能静默绕过。

最终 package review 前，Working Branch owner 全局扫描未终结 Task：全部必须为 `DONE`，或有明确、已批准且带理由的 `WAIVED` / `SUPERSEDED`，不得遗留 `BLOCKED`。最终判断仍以 Ticket AC evidence 和 active Spec 全覆盖为中心，不以 Task 数量或状态替代。

## 工作流

1. 读取当前 plan、gated spec、相关 Approved Ticket（如有）、仓库约束与现有 DAG/runtime state；确认可验收目标及外部 mutation 红线。
2. 用最小表格划分可安全独立启动的 Task；记录确定依赖、primary ownership、Ticket contribution 和已知 seam/risk。不能安全并行就不拆。
3. 派发 primary ownership 不重叠、依赖已释放的 Task；普通 prompt 只给目标、ownership、禁改范围、依赖、贡献 Ticket、局部验证与 BLOCKED 返回格式（见 `references/worker-prompts.md`）。
4. 收集局部 evidence；BLOCKED 直接记录原因、建议动作和影响 Ticket。实际 seam 可以通过调整/新增普通 Task 处理。
5. 由 Working Branch owner 集成并执行共享验证和 Ticket 层正式 review；本 skill 不把局部验证升格为 Ticket acceptance。

高风险 Task（tenant isolation、auth/permission、migration、真实外部写入、金额、不可逆数据风险）可按实际 diff 要求更严格验证或 review；这是同一 Task 的额外质量要求，不是 Strict Task 机制。优先选择不拆，或拆成可独立验收的 Ticket。

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

输出持久化的最小 DAG、条件化的 Task progress（如 earned）和实际验证 evidence。Ticket 的长期事实仍是 AC、evidence 和 acceptance status。向 owner 汇报进度或最终状态时使用 `talk-to-boss`：先说明总范围、已完成阶段、剩余工作、是否 closed 和需要的 owner 决定；再给出 Task/validation 证据。
