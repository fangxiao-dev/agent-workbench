---
name: to-tickets
description: Impl-Package 体系的 ticket 验收切分阶段：当已批准 attempt plan 声明 tickets=true，且 spec 的验收面存在两个或更多需要独立跟踪结论的 delivery slice 时使用。
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

The edge type states what is blocked. Do not collapse implementation, acceptance, and release dependencies into an untyped `Blocked by` list.

Tickets MUST NOT contain worker ownership, worker/task assignment, file-level steps, implementation snippets, automatic dispatch instructions, or runtime **task** status. The template's `Runtime Acceptance Status` is different: it is the ticket's canonical runtime/acceptance fact area and is written only by `dev-with-track` after publication. `to-tickets` must preserve it without assigning a runtime value, evidence, or revalidation conclusion. Task decomposition and task-to-AC contribution belong to `create-task-dag`. A no-DAG attempt has no task checklist; recovery state uses a justified progress ledger.

## Draft Mode

Draft is local and non-publishing:

1. Read the gated spec and current attempt plan and determine whether tickets are earned.
2. Validate that the earned result equals the plan's `Composition.tickets` value; stop through the fail-closed route above on mismatch.
3. Propose the complete slice set and typed edges for owner review.
4. When earned, write one `Publication Status: Draft` file per slice, include the current Attempt ID, and use [assets/templates/ticket.md](./assets/templates/ticket.md) at `docs/implementations/<package-id>/tickets/<NN>-<ticket-slug>.md`.
5. Leave each `Runtime Acceptance Status` field unrecorded; Draft mode owns only the publication status and ticket definition.
6. Number files in a deterministic dependency-compatible order; for independent slices, preserve the proposed document order. File numbers and ticket IDs are package-wide unique: continue after historical attempts and never overwrite an older attempt's ticket.
7. Return the package path, draft ticket paths, typed-edge summary, and acceptance evidence gaps. Do not publish externally or mark tickets Approved.

## Publish Mode

Publish updates the same local ticket files; it does not create external records. Before changing any status, require explicit owner approval of the full draft set and validate all of the following:

1. the current attempt plan declares `Composition: tickets=true, ...` and every draft belongs to that Attempt ID;
2. every ticket has at least one complete, stable AC with planned evidence or a manual verification owner;
3. every typed dependency references an existing ticket in the same Attempt ID; a historical attempt's terminal ticket cannot be a current runtime blocker;
4. the dependency graph is acyclic across all three edge types;
5. the complete set has a deterministic dependency-compatible ordering;
6. no ticket contains task ownership or file-level implementation steps.

Fail publish without partial publication-status updates if any validation fails. Publish owns only the `Draft` to `Approved` publication transition. It must preserve the unrecorded or existing `Runtime Acceptance Status` content. Runtime readiness and all later ticket acceptance status belong to `dev-with-track` under the shared readiness-resolution contract.

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

面向 owner 的汇报先遵循 [Owner-Facing Reporting Contract](../references/owner-facing-reporting.md)：说明共识别多少个可独立验收的交付切片、已起草/批准多少、还缺多少验收证据或审批，以及能否进入下一阶段。

随后返回 runner-neutral canonical handoff：

- topic slug, package-id and package path;
- mode and tickets composition result;
- ticket ids/paths and statuses;
- typed dependencies and validation evidence;
- unresolved AC evidence gaps or owner decisions;
- the next Impl-Package stage (`impl-planning` cross-check or `create-task-dag` when dag is earned).

Do not invoke an implementation command or name a runner. Do not allocate workers, coordinate concurrent execution, or perform runtime scheduling. Execution selects work later through the shared deterministic readiness-resolution contract.
