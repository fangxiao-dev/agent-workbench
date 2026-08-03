# DAG 与 Ownership

本 reference 只描述 Task 的最小执行分解。Composition、Ticket/Spec 验收、状态 schema 和最终 gate 以 `skills/impl-package/references/impl-package-composition-contract.md` 为准。

## 最小 Task 记录

```markdown
# Task DAG

Integration responsibility: Working Branch owner

| Task | Primary ownership | Known depends on | Contributes to tickets | Known seam / risk |
| --- | --- | --- | --- | --- |
| T1 | packages/db test support | none | TST-01 | downstream tests consume runner |
```

Task 是横向 execution unit；Ticket 是独立纵向 acceptance unit。`Contributes to tickets` 是多对多 contribution：一个 Task 可贡献多个 Ticket，一个 Ticket 可由多个 Task 支撑，Task 完成不自动改变 Ticket acceptance status。无 Ticket 的 DAG 使用 `spec:AC-n`，但仍只表达贡献，不伪造 Ticket 或 acceptance 映射。

只记录已知确定依赖。Primary ownership 按模块、目录或共享 seam 划分，派发时它是正常写入范围；未列出的范围默认禁改。发现需要共享范围时返回 BLOCKED，而非越界编辑。不要用 ownership lanes、完整文件清单、全量 input/output contract、consumer 清单、cohort 或 seam execution owner 作为普通 Task 的必填项。

只有实际共享 seam、跨 session handoff 或高风险边界需要时，在受影响 Task 行下补充最小必要范围、接口或验证细节。Task 编号沿 package 中最高 `T<n>` 续编；retired DAG 的新 attempt 使用 patch DAG，不改写历史 DAG。

## 状态与 progress

最小状态为 `PENDING`、`RUNNING`、`DONE`、`BLOCKED`。`DONE` 指局部产出和 evidence 可交给 Working Branch owner；不等于 Ticket accepted。`BLOCKED` 必须记录原因、建议下一动作及受影响 Ticket（如有）。不要产生 `NEEDS_SEAM`：实际 seam 以 blocker 原因记录，或通过调整/新增普通 Task 解决。

Task 的默认运行事实在 DAG/runtime state。仅 BLOCKED、跨 session handoff、重试或主 session 并行派发时才写 `tasks/Tn-handoff.md`，仅包含 blocker/原因、已做 evidence、下一可执行动作、影响 Ticket；不复制 Ticket AC。Ticket 不维护 Phase/Next/Progress；两条状态轴由 package `progress.md` 投影，公共判断与 checkpoint 由主 session 通过 `er-add` 写入 Attempt ledger。

## 拆分与集成

- 仅把可独立启动且不抢占其他 primary ownership 的工作拆 Task。
- 共享 migration、tenant/auth/permission、安全、公共 contract 或 rollback 边界默认不拆；保持串行 Task 或改拆独立 Ticket。
- feature、test、documentation、verification 与 seaming 都是普通 Task，不建立类型系统。
- Working Branch owner 在 Task 返回、出现 BLOCKED 和 Ticket 最终验收前合并产出、处理 seam/冲突、运行共享验证和正式 review，并把 evidence 映射回 Ticket AC。这是既有 owner 的 integration responsibility，不是 Integrator 实体。

Ticket 进入最终验收前，仅检查贡献该 Ticket 的 BLOCKED Task。它影响该 Ticket 的 AC、声明行为或风险边界时必须先解除；否则不阻塞。真实影响扩大时先更新 contribution mapping。最终 package review 前扫描全局 Task，所有 Task 必须 DONE，或有明确、已批准且带理由的 WAIVED/SUPERSEDED，且没有 BLOCKED。
