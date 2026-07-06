---
name: feature-impl-planing
description: >
  Create or update task-local ad-hoc Func Design and implementation plan files
  for a concrete implementation task. Use this when the user asks for an
  implementation plan, feature plan, Func Design, patch plan, or issue
  implementation plan. This skill writes implementation-scoped spec/plan
  artifacts, discovers project docs by meaning instead of fixed folder names,
  reuses an existing implementation slug for patches, and does not maintain
  long-lived product or architecture specs.
---

# Feature Impl Planing

Create the task-local documents needed to implement one concrete change.

This skill is a planning producer for tracked implementation workflows. It
creates or updates the ad-hoc functional contract and execution plan that a
coding agent can use next. It does not backfill long-lived PRD, ARD, or
`docs/func-design/` knowledge; durable documentation maintenance belongs to a
separate knowledge-curation task.

## Output Model

Prefer an implementation slug workspace:

```text
docs/implementations/<slug>/
  spec.md
  plan.md
  YYYYMMDD-HHMM-<patch-topic>.patch-plan.md
```

Roles:

- `spec.md` is the task-local ad-hoc Func Design. It captures the temporary
  functional contract for this implementation, including scope, behavior, data
  semantics, module boundaries, acceptance semantics, and open owner decisions.
- `plan.md` is the initial implementation plan for the slug. It is an execution
  document: exact files, bite-sized steps, commands, expected results, and
  verification.
- `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md` files are follow-up
  implementation plans for patches, fixes, or scope changes on the same
  implementation slug. They must link to and rely on the updated `spec.md`
  instead of duplicating the whole original plan.

If the repository already has a different implementation-workspace convention,
adapt to that convention while preserving these roles: task-local spec, initial
plan, and separate patch plans.

## Workflow Details

The complete semantic planning workflow is in [workflow.md](./workflow.md).
Read it when you need more detail than the compact procedure below.

## Slug And Patch Routing

Before writing, classify the request:

- **New implementation**: create a new slug only when there is no existing
  implementation workspace that clearly owns the feature, issue, or module
  change.
- **Patch or follow-up**: reuse the existing slug when the request fixes,
  extends, verifies, or clarifies a previous implementation. Update `spec.md`
  and write a new `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md` in the slug root;
  do not overwrite `plan.md`.

Find the existing slug semantically. Search implementation directories, previous
plan/spec names, issue IDs, feature names, touched modules, and user-provided
paths. If two candidate slugs are plausible, ask one concise question before
creating a new workspace.

Patch `spec.md` updates should preserve useful history while making the current
contract clear. Add a dated revision note or update an existing "Revisions" /
"Patch Notes" section, then adjust the relevant behavior, data, boundary, and
acceptance sections so implementers do not need to reconcile contradictions.

When a patch plan proposes task IDs for later tracking, do not reuse existing
task numbers. Inspect the selected slug's `dag.md`, `tasks/T*-progress.md`,
`tasks/T*-handoff.md`, prior plans, and patch plans; continue from the highest
existing `T<number>`.

## Relationship To Dev With Track

This skill produces planning inputs. `dev-with-track` consumes those inputs and
owns execution tracking.

Do not define or maintain `dag.md`, `tasks/Tn-progress.md`,
`tasks/Tn-handoff.md`, `findings.md`, or `gate.md` here. If the user asks for
tracked execution after planning, hand off the selected slug plus the active
plan file (`plan.md` or `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`) to
`dev-with-track`.

When `dev-with-track` is already active, update only `spec.md` and the relevant
plan file from this skill, then let `dev-with-track` refresh DAG/task/gate state
from those planning inputs.

## Semantic Discovery

Discover project context by meaning, not by hard-coded folder names. Use the
repository's own documentation culture.

Look for:

- source requirement, issue, handoff, discussion, or requirement-alignment note
- product requirement docs, PRDs, roadmap docs, user stories, or acceptance notes
- architecture docs, ADRs, technical design docs, integration contracts, or data
  model docs
- existing feature designs or module designs, whether long-lived or ad-hoc
- test case indexes, E2E designs, verification rules, smoke-test records, or QA
  notes
- existing implementation workspaces, plans, handoffs, and progress records
- focused code facts needed to avoid planning against stale docs

Do not fail because a specific folder is missing. Folder names are hints, not
workflow gates.

## Workflow

1. Announce that you are creating task-local implementation planning artifacts.
2. Identify the source request, topic, and whether this is a new implementation
   or a patch/follow-up.
3. Discover relevant docs and existing implementation workspaces semantically.
4. Choose or create the implementation slug.
5. Create or update `spec.md` as the ad-hoc Func Design for this task.
6. Create `plan.md` for a new implementation, or create a new
   `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md` for a patch/follow-up.
7. Apply the implementation-plan quality bar: exact files, small checklist
   steps, verification-first steps where practical, concrete commands, and
   expected results.
8. Review the `spec.md` and plan together for consistency, missing owner
   decisions, and execution readiness. If a review subagent is available and
   appropriate in the current environment, use it; otherwise run the review
   checklist inline and state that reason in the final summary.
9. Apply obvious corrections so the formal documents stand alone.
10. Return a compact summary with changed paths, selected slug, whether this was
    new or patch routing, review method, remaining owner decisions, and whether
    the plan is ready for implementation.

## Spec Structure

Use this structure unless the existing slug already has a compatible `spec.md`:

```markdown
# <Feature Or Patch Topic> Temporary Func Design

## Source And Stable References

## Context

## Current Functional Contract

## Scope

## Non-Goals

## Data And Interface Semantics

## Module Boundaries

## Error Handling And Edge Cases

## Acceptance Semantics

## Revisions

## Future Durable-Docs Candidates

## Open Questions
```

Rules:

- Make clear that this is an implementation-scoped ad-hoc spec, not the durable
  source of product or architecture truth.
- Reference durable docs that shaped the task, but do not update those durable
  docs from this skill.
- Keep implementation steps out of `spec.md`; put execution mechanics in the
  plan.
- For patches, keep the current functional contract coherent after the patch.
  Do not leave mutually conflicting old and new semantics without an explicit
  resolution.

## Plan Requirements

The implementation plan is temporary and executable by a coding agent with
limited context.

Include:

- link to the task-local `spec.md`
- whether this is the initial plan or a patch plan
- exact files to create or modify
- bite-sized checkbox steps
- test-first or verification-first steps where practical
- concrete commands with expected results
- acceptance gates and rollback/cleanup notes where relevant
- no placeholders or vague "add validation" steps

For patch plans, include:

- the existing slug being patched
- the specific spec revision or dated patch note it implements
- the delta from prior implementation behavior
- verification that proves the patch did not regress the original acceptance
  semantics

## Review Checklist

Before returning final output, verify:

- `spec.md` exists or was updated in the selected implementation slug.
- A new implementation has `plan.md`; a patch/follow-up has a new
  `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md` in the slug root.
- Any proposed tracking task IDs continue from the highest existing task number
  in the slug.
- The plan implements the current `spec.md` contract.
- Functional semantics live in `spec.md`, not only in the plan.
- Patch routing reused the existing slug when one clearly owned the change.
- Durable docs are referenced when relevant but not updated by this skill.
- Open owner decisions are explicit and separated from implementation steps.
- Verification commands are concrete and scoped to the change.

## Output Contract

Return:

- selected implementation slug
- routing: new implementation or patch/follow-up
- files created or changed
- main spec and implementation summary
- review method used and corrections applied
- remaining owner decisions
- whether the plan is ready for implementation
