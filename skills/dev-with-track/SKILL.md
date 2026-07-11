---
name: dev-with-track
description: >
  Impl-Package 体系的执行阶段：当已批准 implementation package 需要恢复执行现场、
  确定性判定下一可执行单元、记录 task/ticket 证据、处理返工失效或关闭 gate 时使用。
  不用于撰写 design、spec、plan、ticket 或分配 worker。
---

# Dev With Track

执行一个 implementation package 的持久恢复与闭环。持久单位是
`docs/implementations/<slug>/`，不是聊天轮次、ticket 或 worker。它消费上游已批准
合同，不重写需求、切片或 task-DAG 方法。

本 skill 的共享规范源是
[Impl-Package Composition Contract](../../docs/skill-design/references/impl-package-composition-contract.md)。
其中四种 composition、canonical status home、typed blocker、readiness、task-to-AC、
seam、迁移及 Stage 7 的语义均以该文件为准；本 skill 仅实施和验证，不能另行定义。

核心循环：

```text
restore -> readiness resolution -> execute -> evidence -> findings -> gate
```

这不是自动派工或动态 frontier：不做 worker leasing、并发锁、资源分配或自动启动
worker。若有多个可执行单元，按 ticket/task 文档顺序稳定选择，并由主 session 决定
是否实际执行。

## 上下游边界

- `requirement-alignment` 拥有必过的 Design / Spec gates、`design.md` 和 `spec.md`。
- `feature-impl-planning` 拥有 `plan.md`、patch plan 和 composition migration 的计划
  内容；`to-tickets` 拥有 ticket 的切片、draft/publish 与验收定义；
  `create-task-dag` 拥有 execution decomposition 与 `dag.md` task 合同。
- 本 skill 维护运行时事实、按需 task/ticket progress、findings 与 gate。它不能自行
  earn tickets/dag 或从宽需求切片；输入缺少已批准 artifact 时，路由回相应上游 skill。

## Package scaffold

先读 `spec.md` 中唯一的 `Composition: tickets=<true|false>, dag=<true|false>` 声明，
再按共享 contract 的四态表 scaffold。`spec.md` 与 `plan.md` 恒有；只有 earned 的
artifact 才能创建：

```text
docs/implementations/<slug>/
├── [design.md]
├── spec.md
├── plan.md
├── [tickets/]
│   └── <ticket>.md                 # only tickets=true
├── [dag.md]                        # only dag=true
├── findings.md
├── gate.md
└── tasks/
    ├── Tn-progress.md              # only when task ledger trigger applies
    ├── Tn-handoff.md               # only when independent task transfer is needed
    └── <ticket>-progress.md        # only when whole ticket is a recovery/transfer unit
```

Never create `dag.md` as a ticket index. For `tickets=true, dag=false`, ticket files are
the execution and acceptance fact sources and `plan.md` remains task-free. For
`tickets=true, dag=true`, any ticket status in `dag.md` is an explicitly labelled,
read-only projection; it never overwrites a ticket's acceptance conclusion. For no-ticket
packages, Acceptance evidence stays in `spec.md` / `gate.md`. A progress ledger restores
local state; it does not earn a DAG or replace its execution topology.

If the declared artifacts and workspace disagree, do not silently add placeholders:
restore evidence, identify the mismatch, and route an intended composition change through
the contract's recorded Composition Migration. The migration must leave a relocation
pointer and remove the old writable maintenance entry point.

## Restore and readiness resolution

Before any execution:

1. Read repo instructions, then active `design.md` (if present), approved `spec.md`,
   active `plan.md`, earned tickets, earned DAG, progress ledgers, findings and gate.
2. Reconcile document status against recorded command/test/review/external evidence.
   Evidence wins over stale status and the canonical fact source is corrected.
3. Validate the relevant static graph: typed ticket blockers when tickets are earned;
   `Depends on` references when dag is earned. Missing references or cycles block execution.
4. Apply the shared-contract readiness resolution before choosing a unit. Ticket
   `implementation` blockers and DAG task dependencies must both be dependency-releasing;
   owner, external gate and environment prerequisites must hold.
5. Choose the first actionable unit in documented order. Do not use acceptance/release
   ticket edges to release implementation work, and do not let a ticket state release a
   DAG `Depends on` edge.

On reopened/reworked upstream work, mark affected dependent DAG tasks and their old
evidence `NEEDS-REVALIDATION`; do not proceed until rechecked. Worker return status maps
to runtime state only according to the shared contract: claimed `DONE` remains running
until `Done when` evidence is recorded; concerns and integration findings require explicit
revalidation. `DONE`, or a justified `WAIVED`/`SUPERSEDED` with replacement evidence and
impact note, is the only dependency-releasing outcome.

## Evidence, progress, and acceptance

Use `tasks/Tn-progress.md` only when a task has an independent owner/subagent, external
gate, blocker/seam/finding, cross-session recovery need, independent durable evidence, or
gate-relevant detail too large for its canonical execution source. A normal task stays in
that source (the DAG when earned, otherwise the no-DAG plan checklist). Task numbers remain
stable and increment across the slug.

Ticket acceptance is not a sum of completed tasks. For ticketed composition, the ticket
file's `Runtime Acceptance Status` is the canonical ticket runtime/acceptance fact source:
only this skill writes its `Value`, `Direct evidence`, and `Revalidation` fields. Its
separate `Publication Status` remains owned by `to-tickets` and is not a runtime result.
Do not create a ticket progress file by default. Create `<ticket>-progress.md` only when
the *whole ticket* is independently resumed or handed over; it records local state and a
task index, never duplicate task ledgers or the ticket's runtime acceptance conclusion.

Before execution begins, check that every ticket AC (or no-ticket spec AC) has a planned
evidence producer or named manual-verification owner. For DAG packages, resolve every
`contributes-to` / `enables` target to an existing AC; an infrastructure `enables` entry
does not by itself close an AC. Before ticket/package closure, record direct evidence for
each relevant AC. A seam remains open until its plan contract owner, DAG execution owner,
and plan acceptance owner have completed their respective responsibilities; an unaccepted
seam blocks each affected acceptance target.

Promote only cross-task decisions, risks, reusable findings, and explicit follow-ups to
`findings.md`; ordinary command output remains on the task/ticket evidence path.

## Gate and Stage 7

Open or update `gate.md` only for implementation-level closing, blocking, or deferral.
Its decision cannot be inferred from task `DONE` states. Before closing, verify the shared
contract's complete Stage 7 durable-delta path:

- every gate-table `Delta ID` is registered in project `_pending.md` under
  `<destination>|<delta-id>`;
- every affected module spec contains the pending-delta truth pointer; and
- a required missing target module-spec stub exists before its pointer is written.

With no durable delta, retain `none` and a reason in the gate. A missing capture, pending
entry, pointer, stub, or evidence is a gate blocker/capture gap—not evidence that there was
no change. Route report/apply work to `backfill-stable-docs`; do not write stable-document
content as a shortcut from this skill.

## Task ledger trigger and templates

Use the templates only for earned artifacts:

- `assets/templates/dag.md` — only `dag=true`; references the shared task and seam fields.
- `assets/templates/progress.md` — task or justified ticket recovery ledger.
- `assets/templates/handoff.md` — independent task transfer only.
- `assets/templates/findings.md` — cross-task conclusions only.
- `assets/templates/gate.md` — implementation gate and Stage 7 capture evidence.

`design.md` / `spec.md` templates remain in `requirement-alignment`; `plan.md` and
composition migration content remain in `feature-impl-planning`; ticket templates remain
in `to-tickets`.

## Execution checklist

1. Restore the package and verify approved Design/Spec/plan inputs.
2. Read the composition declaration; scaffold only matching earned artifacts.
3. Reconcile evidence and canonical states; validate static dependencies and AC references.
4. Run deterministic readiness resolution and select the documented next actionable unit.
5. Execute only under the existing owner/task contract; record real evidence.
6. Update the canonical task/ticket status and any justified progress ledger; propagate
   `NEEDS-REVALIDATION` after upstream rework.
7. Check AC evidence and seam acceptance before closing tickets or no-ticket package gates.
8. Promote cross-task findings, then complete or explicitly block/defer the gate.
9. For a closing gate, complete Stage 7 durable-delta capture or record `none` with reason.
10. Report composition, canonical state sources, selected/blocked unit, evidence, findings,
    AC/seam coverage, gate state, and any capture gap.
