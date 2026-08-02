---
name: to-tickets
description: 当已批准 implementation plan 判定需要 tickets，且 spec 含至少两个必须独立跟踪 acceptance 结论的 delivery slice 时使用。
---

# To Tickets — Impl-Package Local Fork

This repository-local fork turns an approved implementation contract into acceptance slices. A ticket is a delivery/acceptance unit, never a worker task or scheduling unit.

## Invocation Contract

Use `mode=draft|publish`. Calls from another Impl-Package skill normally omit the mode or set `mode=draft`; omitted mode means `draft`. `Draft` is the normal handoff from ticket slicing to `create-task-dag` when the current Composition earns a DAG. `mode=publish` is reserved for the single owner-approved decomposition bundle: every artifact earned by the current Composition (Tickets, and DAG when `dag=true`) must have passed joint validation before the Draft-to-Approved transition. `publish` is never the default continuation of drafting and never represents an independent Ticket-only approval gate.

Canonical input is the same-package-id package's gated current `spec.md` plus current attempt plan. Stop if the Spec gate is not `PASSED`, the plan is absent, Attempt ID/D-S-P revisions cannot be resolved, or the package IDs disagree. Composition is read only from the current plan. The plan remains the only source for whether Tickets and/or a DAG are earned; this skill does not create a DAG to satisfy an approval precondition and does not publish a Ticket set before an earned DAG is ready for the same review.

## Earn Tickets Before Creating Files

Tickets are earned only when there are at least two delivery slices worth tracking with independent acceptance conclusions. “Independent acceptance” means a clear boundary, local acceptance criteria, and observable evidence; it does not promise independent release.

If there is only one slice, keep its Acceptance Semantics in `spec.md`, report `tickets=false`, and DO NOT create `tickets/` or a ticket file. Never create ceremony to represent a single slice.

Before writing a draft, compare the earned result with the current plan's exact `Composition: tickets=<true|false>, dag=<true|false>` value. Write only when they agree. Fail closed when `tickets=false` but two or more slices are earned, or when `tickets=true` but fewer than two slices are earned: do not create, delete, or update any ticket file; do not silently edit the spec. Return a plan-revision decision and route to `impl-planning`; Composition mismatch does not trigger D/S revision unless ticket slicing exposes an actual contract gap.

## Slice The Acceptance Surface

Create tracer-bullet vertical slices: each ticket delivers a narrow, complete, user-verifiable path rather than a horizontal layer. Use repository vocabulary and respect the package's global seams, migration/rollback policy, and constraints.

For a wide mechanical refactor that cannot land green as vertical slices, use expand–contract: expand the new form beside the old, migrate bounded batches while both remain valid, then contract only after every migration is accepted. Preserve a final integration-and-verification slice when intermediate batches cannot independently stay green.

Each ticket MUST contain:

- stable ticket id and title;
- `Publication Status: Draft` or the publish result `Publication Status: Approved`;
- the current Attempt ID, Spec Revision, and Plan Revision it was created/last confirmed against — a ticket that still cites a superseded Plan Revision after the plan advances is `NEEDS-REVALIDATION` until reconciled;
- user-visible `What to build` boundary;
- stable, individually identified acceptance criteria (`AC-1`, `AC-2`, ...), including their planned observable evidence or manual verification owner;
- zero or more typed blocking edges in the form `<implementation|acceptance|release>: <ticket-id>`.

Plan Revision 前进时先读取 P delta，而不是重建完整票集。只有 acceptance boundary、typed edge、planned evidence 或 slice definition 依赖该 delta 的 ticket 需要内容重验证；未受影响 ticket 可作为一个 batch 确认仍成立并机械更新 Plan Revision。`NEEDS-REVALIDATION` 是待判断标记，不等于所有 ticket 失效，也不要求重新发布 owner 已批准但语义未变的 Draft/Approved 结论。

The edge type states what is blocked. Do not collapse implementation, acceptance, and release dependencies into an untyped `Blocked by` list.

Tickets MUST NOT contain worker ownership, worker/task assignment, file-level steps, implementation snippets, automatic dispatch instructions, or runtime **task** status. The template's top `Runtime Acceptance Status` is a machine-owned projection of the package runtime-state ticket record and is updated only through `dev-with-track`; `to-tickets` leaves its marker body at the unrecorded initial projection. `Phase` and `Next` are a short human recovery summary, not a second runtime state. Task decomposition and Task-to-Ticket many-to-many contribution belong to `create-task-dag`; Task completion never updates ticket acceptance automatically. A no-DAG attempt still has no task checklist or separate progress ledger; when tickets are earned, recovery context stays in each ticket's own `Progress` section and points to the existing Execution Record evidence.

## Draft Mode

Draft is local and non-publishing:

1. Read the gated spec and current attempt plan and determine whether tickets are earned.
2. Validate that the earned result equals the plan's `Composition.tickets` value; stop through the fail-closed route above on mismatch.
3. Propose the complete slice set and typed edges for owner review.
4. For every AC, identify the planned observable evidence source at delivery-slice level and perform an evidence-feasibility precheck against the plan and proposed typed edges. Reject an obvious acceptance-evidence cycle; when the later task producer is not yet known, hand the unresolved producer obligation to `create-task-dag` instead of inventing task ownership in the ticket.
5. When earned, write one `Publication Status: Draft` file per slice, include the current Attempt ID, and use [assets/templates/ticket.md](./assets/templates/ticket.md) under the project-configured package root at `tickets/<NN>-<ticket-slug>.md`. Initialize `Phase: planning`, one concrete `Next`, and one creation entry under `Progress` that summarizes the drafted boundary and points to the current D/S/P evidence.
6. Leave each `Runtime Acceptance Status` field unrecorded; Draft mode owns the publication status, ticket definition, and initial recovery summary, but no runtime acceptance judgment.
7. Number files in a deterministic dependency-compatible order; for independent slices, preserve the proposed document order. File numbers and ticket IDs are package-wide unique: continue after historical attempts and never overwrite an older attempt's ticket.
8. Return the package path, draft ticket paths, typed-edge summary, unresolved evidence-producer obligations, and acceptance evidence gaps. When `dag=true`, hand the complete Draft set to `create-task-dag`; do not publish externally or mark tickets Approved while the DAG and joint review are still pending.

## Publish Mode

Publish updates the same local ticket files; it does not create external records. It is the final publication step of the plan-decomposition review, not a separate Ticket approval stage.

After a successful publish, update the ticket's top `Phase` / `Next` and append one concise `Progress` entry that routes to execution preflight. This human recovery update must not alter the machine-owned status marker or duplicate the publication transaction's evidence.

Before changing any status, require `impl-planning` to have completed the applicable fresh `plan-review`: admission `ready`, or normal/focused review with a runtime ledger absolute path that passes `verify-clearance` immediately before mutation; a focused `closure-verified` chat verdict and any plain `cleared` message are invalid. Then require one explicit owner approval of the complete earned bundle and validate all of the following:

1. the current attempt plan declares `Composition: tickets=true, ...` and every draft belongs to that Attempt ID;
2. every ticket has at least one complete, stable AC with planned evidence or a manual verification owner;
3. every typed dependency references an existing ticket in the same Attempt ID; a historical attempt's terminal ticket cannot be a current runtime blocker;
4. the dependency graph is acyclic across all three edge types;
5. every AC has a feasible evidence source under the plan and proposed typed edges; no known evidence source requires implementation that is blocked by the same ticket's acceptance;
6. the complete set has a deterministic dependency-compatible ordering;
7. no ticket contains task ownership or file-level implementation steps;
8. when `dag=true`, the same-Attempt Draft DAG exists and has passed the joint Ticket↔DAG validation: earned-ticket coverage, typed blocker ↔ Task dependency consistency, non-overlapping Task primary ownership, many-to-many `contributes-to` mappings, AC evidence feasibility, and D/S/P revision plus gate/preflight binding. The DAG must not copy Ticket ACs, assign Ticket ownership, or create a Task→AC acceptance mapping;
9. when `dag=false`, the absence of a DAG is the earned Composition and is recorded as such; do not create one merely to satisfy this checklist.

若 publish 前唯一差异是新 P revision 且 impact summary 证明 ticket 语义未变，可对完整未受影响 batch 做一次 reconciliation 后更新 Plan Revision；不要重新起草或要求 owner 重批相同内容。受影响 subset 仍按本节完整验证。

The owner approval covers the Tickets and, when earned, the DAG as one revision-bound bundle. `revise` or `unavailable` admission conclusions cannot be owner-waived into publish. After the atomic transition succeeds, report the bundle as `approved` and only then hand it to execution preflight. `create-task-dag` does not have an independent publication or approval gate.

### Material changes and scoped re-review

After bundle approval, a change to an acceptance boundary, typed dependency, Task contribution, primary ownership, execution ordering, AC evidence feasibility, Composition, safety/gate boundary, or D/S/P binding supersedes the approval for the affected scope. Reconcile only the affected Tickets and DAG nodes (or regenerate the affected DAG portion when needed), run joint validation again, return to `impl-planning` for fresh admission, then request owner approval before execution resumes. Keep unaffected artifacts as a confirmed batch when the impact evidence supports it; do not silently edit an approved structure. Pure formatting, citation, classification, or mechanical Plan Revision rebinding that cannot change those semantics does not require a new approval, but its evidence must be recorded in the existing handoff/Execution Record.

Fail publish without partial publication-status updates if any validation fails. Publish owns only the `Draft` to `Approved` publication transition. It must preserve the runtime-state marker body. Runtime readiness and all later ticket acceptance status belong to `dev-with-track` through the shared structured-state contract.

完整 ticket set 的 planning-only publish 统一交给 [Fast planning apply](#fast-planning-apply)：它通过共享 state engine 在同一事务中注册 current attempt、seed earned ticket/task records 并刷新 projections；不再在 publish 后手工重复运行 `init` 或 `refresh-projections`。每个 earned ticket 必须恰有一个 `UNRECORDED` 或既有 current record；同步失败视为 publish 尚未完成收口，不得让 ticket file 与 JSON 成为两个可写状态源。

### Fast planning apply

When the review baseline is fresh, the owner has approved the exact current
manifest, no blocker is unresolved, and the change is planning-only, use the
single package-local transaction in
[plan-apply-runbook](../references/plan-apply-runbook.md):

```powershell
python skills/impl-package/scripts/impl_package_apply.py publish-plan `
  --package <package> `
  --decision <D<n>> `
  --spec <S<n>> `
  --plan <P<n>> `
  --ledger <ledger> `
  --authorization <owner-authorization.json>
```

The helper verifies clearance and owner authorization, validates the complete
Ticket/AC/typed-edge/DAG bundle once, atomically publishes all Draft tickets,
registers D/S/P and projections through the shared state engine, performs one
final summary validation, then cleans its transient journal. It returns only
`APPLIED` or a concrete `BLOCKER`; on failure it restores and verifies the
original bytes. It does not create manual backup/staging directories and does
not commit, push, or update GitHub. Inspect the actual worktree before retrying
an interrupted parent process; never infer transaction completion from a
cleanup attempt.

The separate `sync-working-unit` helper can generate a PR/Issue Markdown
summary from package state after commit/push. Remote updates remain an
independent, explicitly authorized workflow.

## Runner-Neutral Handoff

S/M/L/D shorthand 本身没有创建、删除或退休 ticket 的权限；只读取当前 plan 的 canonical Composition。request 与 earn condition 或 plan 不一致时 fail closed，回 `impl-planning` 形成 owner decision。

向 owner 汇报时使用 `talk-to-boss`：说明共识别多少个可独立验收的交付切片、已起草/批准多少、还缺多少验收证据或审批，以及能否进入下一阶段。

随后返回 runner-neutral canonical handoff：

- topic slug, package-id and package path;
- mode and tickets composition result;
- ticket ids/paths and statuses;
- each ticket's current Phase / Next and latest Progress evidence anchor;
- typed dependencies and validation evidence;
- joint Ticket↔DAG validation result and revision/gate binding when `dag=true`;
- unresolved AC evidence gaps or owner decisions;
- the next Impl-Package stage (`impl-planning` cross-check, `create-task-dag` when `dag=true` and the bundle is still drafting, or execution preflight only after the joint bundle is approved).

Do not invoke an implementation command or name a runner. Do not allocate workers, coordinate concurrent execution, or perform runtime scheduling. Execution selects work later through the shared deterministic readiness-resolution contract.
