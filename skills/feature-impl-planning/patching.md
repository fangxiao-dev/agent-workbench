# Patch 与 Follow-Up 规则

当请求是修复、扩展、验证或澄清一个已有 implementation slug 时读本文件。
复用该 slug：为 patch 另建第二个 slug 会割裂实现上下文，削弱后续 handoff。

## Spec 修订

- 原地更新该 slug 的 `spec.md`；不要另起新 spec。
- 在 `Revisions` 小节追加带日期的条目，说明改了什么、为什么。
- 调整行为、数据、边界、验收各节，使最新合同无歧义。不要留下新旧语义冲突让
  实现者自行调和。
- 仅当旧内容能解释合同为何变化时才保留它。

## Patch Plan

- 在 slug 根目录新建 `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`；绝不覆盖
  `plan.md`。
- `plan.md` 永远代表该 slug 的初始实施计划。若初始计划已完成或不再是当前执行
  入口，在 `plan.md` 开头标记 `Deprecated / Superseded by <patch-plan-file>`，
  保留它作为历史实施证据。
- 写明本 patch 实现的是 `spec.md` 的哪条修订。
- 说明相对已实现行为的 delta。
- 除验证新行为外，附带回归验证，证明原有验收语义未被破坏。

## Patch DAG

- 若旧 `dag.md` 已 gate passed 或只记录上一批执行账本，可在其开头标记
  `Retired / gate passed`。
- 当 patch/follow-up 需要新的任务图、cohort、ownership 或 seam 调度时，在 slug
  根目录新建 `YYYYMMDD-HHMM-<patch-topic>.patch-dag.md`，不要把新任务追加到已
  retired 的旧 `dag.md`。
- 新 patch DAG 是当前 patch 的执行控制板；旧 `dag.md` 保留为历史证据。

## Task ID 续编

patch plan 提议 tracking task ID 时，检查该 slug 的 `dag.md`、
`tasks/T*-progress.md`、`tasks/T*-handoff.md`、`plan.md`、既往 patch plan 和
既往 patch DAG；从已有最高 `T<number>` 继续编号。不复用、不重排旧编号。
