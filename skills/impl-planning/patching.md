# Patch 与 Follow-Up 规则

当请求是修复、扩展、验证或澄清一个已有 implementation package-id 时读本文件。
复用该 package-id：为 patch 另建第二个 package-id 会割裂实现上下文，削弱后续 handoff。

Patch 只属于**已关闭 package gate 之后（post-gate）**的生命周期。未关闭 gate 的 package 仍在
原 `plan.md` / tickets / DAG 生命周期中：合同变化回到 `req-align` 重新
过门，计划或 DAG 修正留在原 artifact，绝不用 patch 绕过 gate。`to-tickets` 的
ticket 生命周期也不产生每-ticket patch；patch 始终覆盖 package 级增量。

## Spec 修订

- 合同发生变化时路由到 `req-align`；由它在同一 package-id 原地修订
  `spec.md`，不要另起新 spec。
- `req-align` 在 `Revisions` 小节追加带日期的条目，说明改了什么、
  为什么，并重新执行 Design 与 Spec 两道必过门。
- 由 `req-align` 调整行为、数据、边界、验收各节，使最新合同无歧义。
  不要留下新旧语义冲突让实现者自行调和。
- 仅当旧内容能解释合同为何变化时才保留它。
- `impl-planning` 只在两道 gate 均重新通过后写 patch plan；任一 gate
  `BLOCKED` 时停止，不创建 patch plan。
- 若修订需要改变 `Composition:`，只能由 `req-align` 记录、重新通过
  两道门后再由 planning 执行共享 contract 的受控 Composition Migration；planning
  不自行改写 Composition，也不创建 per-ticket patch。

## Patch Plan

- 在 package-id 根目录新建 `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`；绝不覆盖
  `plan.md`。
- 创建 patch plan 前确认原 package 的 gate 已关闭，并在 patch plan 记录该证据；
  否则停在原生命周期更新，不创建 patch 文件。
- `plan.md` 永远代表该 package-id 的初始实施计划。若初始计划已完成或不再是当前执行
  入口，在 `plan.md` 开头标记 `Deprecated / Superseded by <patch-plan-file>`，
  保留它作为历史实施证据。
- 写明本 patch 实现的是 `spec.md` 的哪条修订。
- 说明相对已实现行为的 delta。
- 除验证新行为外，附带回归验证，证明原有验收语义未被破坏。

## Patch DAG

- 若旧 `dag.md` 已 gate passed 或只记录上一批执行账本，可在其开头标记
  `Retired / gate passed`。
- 当 patch/follow-up 需要新的任务图、cohort、ownership 或 seam 调度时，在 package-id
  根目录新建 `YYYYMMDD-HHMM-<patch-topic>.patch-dag.md`，不要把新任务追加到已
  retired 的旧 `dag.md`。
- patch DAG 仍遵守当前 `spec.md` 的 Composition 与
  [Impl-Package Composition Contract](../../docs/skill-design/references/impl-package-composition-contract.md)；
  它不是按 ticket 拆出的 patch artifact。
- 新 patch DAG 是当前 patch 的执行控制板；旧 `dag.md` 保留为历史证据。

## Task ID 续编

patch plan 提议 tracking task ID 时，检查该 package-id 的 `dag.md`、
`tasks/T*-progress.md`、`tasks/T*-handoff.md`、`plan.md`、既往 patch plan 和
既往 patch DAG；从已有最高 `T<number>` 继续编号。不复用、不重排旧编号。
