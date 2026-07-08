# [Implementation Name] DAG

状态：[计划中 / 活跃 / 暂停 / 已关闭 / Retired（gate passed，见当前 patch-dag）]
创建：[YYYY-MM-DD]
Spec：[spec.md](spec.md)
Plan：[plan.md](plan.md)
Findings：[findings.md](findings.md)
Gate：[gate.md](gate.md)

本文是 implementation 的并行调度控制面板：记录 cohort、owner、status、gate/evidence 和 seam。不要在这里写长日志；复杂任务下放到 `tasks/Tn-progress.md`，需要单独交接时再创建 `tasks/Tn-handoff.md`。

任务编号在本 slug 内稳定递增。新增任务前检查 `dag.md`、根目录 `*.patch-dag.md`、`tasks/T*-progress.md`、`tasks/T*-handoff.md`、`plan.md` 和根目录 `*.patch-plan.md`，从最高 `T<number>` 继续编号，不复用或重排旧编号。

## Shared Contracts

- [contract / DTO / route prop / external smoke protocol]

## Task Contracts

| Task | Depends on | Can run with | Primary owned | Conditional seam | Forbidden | Input contract | Output contract | Focused tests | Done when |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | [dependency] | [parallel-safe tasks] | [正常写入范围] | [文件 + 编辑条件] | [禁改] | [input] | [output] | [commands] | [done gate] |

## DAG Board

| Cohort | Task | Owner | Status | Progress | Handoff | Gate / Evidence | Seam / Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | T1 [task] | [main / worker] | Planned | [tasks/T1-progress.md](tasks/T1-progress.md) | - | [gate] | [seam] |

Status vocabulary：`Planned` / `Ready` / `Running` / `Needs seam` / `Blocked` / `Integrated` / `Verified local` / `Verified external` / `Deferred`

## Task Ledger Index

只在满足触发条件时创建 `tasks/Tn-progress.md`。只在 task 需要单独交接时创建 `tasks/Tn-handoff.md`。

| Task | Progress | Handoff | Why separate |
| --- | --- | --- | --- |
| T1 | [tasks/T1-progress.md](tasks/T1-progress.md) | - | [owner/gate/blocker/evidence/etc.] |

## Verification Gates

- Local：
- Browser：
- External：
- Review：

## Open Seams

- [seam / owner / next action]

## Last Update

- [YYYY-MM-DD] [meaningful status change]
