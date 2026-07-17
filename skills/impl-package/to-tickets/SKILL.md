---
name: to-tickets
description: 当已批准 implementation plan 判定需要 tickets，且 spec 含至少两个必须独立跟踪 acceptance 结论的 delivery slice 时使用。
---

# To Tickets — Impl-Package Local Fork

This repository-local fork turns an approved implementation contract into acceptance slices. A ticket is a delivery/acceptance unit, never a worker task or scheduling unit.

## Invocation Contract

Use `mode=draft|publish`. Calls from another Impl-Package skill normally omit the mode or set `mode=draft`; omitted mode means `draft`. The sole cross-skill exception is a recorded explicit owner approval for the same complete Draft set: a caller may then request `mode=publish` to perform the Draft-to-Approved transition. `publish` is never the default continuation of drafting.

Canonical input is the same-package-id package's gated current `spec.md` plus current attempt plan. Stop if the Spec gate is not `PASSED`, the plan is absent, Attempt ID/D-S-P revisions cannot be resolved, or the package IDs disagree. Composition is read only from the current plan.

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

Tickets MUST NOT contain worker ownership, worker/task assignment, file-level steps, implementation snippets, automatic dispatch instructions, or runtime **task** status. The template's `Runtime Acceptance Status` is a machine-owned projection of the package runtime-state ticket record and is updated only through `dev-with-track`; `to-tickets` leaves its marker body at the unrecorded initial projection. Task decomposition and task-to-AC contribution belong to `create-task-dag`. A no-DAG attempt has no task checklist; recovery state uses a justified progress ledger.

## Draft Mode

Draft is local and non-publishing:

1. Read the gated spec and current attempt plan and determine whether tickets are earned.
2. Validate that the earned result equals the plan's `Composition.tickets` value; stop through the fail-closed route above on mismatch.
3. Propose the complete slice set and typed edges for owner review.
4. For every AC, identify the planned observable evidence source at delivery-slice level and perform an evidence-feasibility precheck against the plan and proposed typed edges. Reject an obvious acceptance-evidence cycle; when the later task producer is not yet known, hand the unresolved producer obligation to `create-task-dag` instead of inventing task ownership in the ticket.
5. When earned, write one `Publication Status: Draft` file per slice, include the current Attempt ID, and use [assets/templates/ticket.md](./assets/templates/ticket.md) under the project-configured package root at `tickets/<NN>-<ticket-slug>.md`.
6. Leave each `Runtime Acceptance Status` field unrecorded; Draft mode owns only the publication status and ticket definition.
7. Number files in a deterministic dependency-compatible order; for independent slices, preserve the proposed document order. File numbers and ticket IDs are package-wide unique: continue after historical attempts and never overwrite an older attempt's ticket.
8. Return the package path, draft ticket paths, typed-edge summary, unresolved evidence-producer obligations, and acceptance evidence gaps. Do not publish externally or mark tickets Approved.

## Publish Mode

Publish updates the same local ticket files; it does not create external records. Before changing any status, require explicit owner approval of the full draft set and validate all of the following:

1. the current attempt plan declares `Composition: tickets=true, ...` and every draft belongs to that Attempt ID;
2. every ticket has at least one complete, stable AC with planned evidence or a manual verification owner;
3. every typed dependency references an existing ticket in the same Attempt ID; a historical attempt's terminal ticket cannot be a current runtime blocker;
4. the dependency graph is acyclic across all three edge types;
5. every AC has a feasible evidence source under the plan and proposed typed edges; no known evidence source requires implementation that is blocked by the same ticket's acceptance;
6. the complete set has a deterministic dependency-compatible ordering;
7. no ticket contains task ownership or file-level implementation steps.

若 publish 前唯一差异是新 P revision 且 impact summary 证明 ticket 语义未变，可对完整未受影响 batch 做一次 reconciliation 后更新 Plan Revision；不要重新起草或要求 owner 重批相同内容。受影响 subset 仍按本节完整验证。

Fail publish without partial publication-status updates if any validation fails. Publish owns only the `Draft` to `Approved` publication transition. It must preserve the runtime-state marker body. Runtime readiness and all later ticket acceptance status belong to `dev-with-track` through the shared structured-state contract.

完整 ticket set 发布成功后运行 `impl_package_state.py --package <path> init --package-id <id>` 机械同步 current attempt ticket records，再运行 `refresh-projections`；每个 earned ticket 必须恰有一个 `UNRECORDED` 或既有 current record。同步失败视为 publish 尚未完成收口，不得让 ticket file 与 JSON 成为两个可写状态源。

### Atomic local publish protocol

After every semantic validation passes, perform the status transition as one recoverable package-local transaction:

1. Create a temporary staging directory and journal inside the package. The journal lists the complete target set and stores or references an original byte-for-byte snapshot of every target; staged files contain the complete intended `Approved` contents.
2. Validate the entire staged set again, including ACs, typed references, acyclicity, deterministic order, and the exact target paths.
3. Replace every target from staging. Do not report success during replacement.
4. If any replacement or verification fails, use the journal to restore every original target, verify the restored set, then remove temporary transaction data. Report the publish as failed; never call a partial replacement successful.
5. Only after all replacements and final verification succeed, remove staging and the journal and report every ticket's Publication Status as `Approved`.

At the start of any later draft or publish operation, detect an uncleared publish journal. Restore and verify the recorded originals before continuing; if recovery cannot be verified, stop for owner intervention. Staging and journal are transient transaction data, not persistent Impl-Package artifacts.

## Runner-Neutral Handoff

S/M/L/D shorthand 本身没有创建、删除或退休 ticket 的权限；只读取当前 plan 的 canonical Composition。request 与 earn condition 或 plan 不一致时 fail closed，回 `impl-planning` 形成 owner decision。

向 owner 汇报时使用 `talk-to-boss`：说明共识别多少个可独立验收的交付切片、已起草/批准多少、还缺多少验收证据或审批，以及能否进入下一阶段。

随后返回 runner-neutral canonical handoff：

- topic slug, package-id and package path;
- mode and tickets composition result;
- ticket ids/paths and statuses;
- typed dependencies and validation evidence;
- unresolved AC evidence gaps or owner decisions;
- the next Impl-Package stage (`impl-planning` cross-check or `create-task-dag` when dag is earned).

Do not invoke an implementation command or name a runner. Do not allocate workers, coordinate concurrent execution, or perform runtime scheduling. Execution selects work later through the shared deterministic readiness-resolution contract.
