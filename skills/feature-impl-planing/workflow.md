# Semantic Feature Implementation Planning Workflow

Use this workflow to create or update the task-local planning documents for one
implementation slug.

## Purpose

The output is implementation-scoped:

- `spec.md` captures the ad-hoc Func Design for the current task.
- `plan.md` captures the initial implementation plan.
- `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md` captures later patch or
  follow-up implementation plans for the same slug.

This workflow intentionally does not update long-lived product, architecture, or
feature-design documents. It may list durable-doc candidates for a later
knowledge-curation task.

## Inputs

Accept any concrete source that defines a change enough to plan:

- requirement-alignment artifact
- issue
- handoff
- user discussion
- existing Func Design or implementation plan
- patch request against a previous slug

If the source is too ambiguous to classify the task or choose a slug, ask one
concise alignment question before writing.

## Discovery

Read project context by semantic role:

- source requirement or discussion
- durable product requirements
- architecture and data-contract docs
- existing feature/module designs
- test and verification docs
- existing implementation workspaces and plans
- focused code facts that validate or correct the docs

Use folder names as hints only. Do not require exact names like
`docs/func-design/`, `docs/impl-plans/`, or `docs/exchange/`.

## Routing

Classify the task before writing:

| Routing | Use When | Output |
| --- | --- | --- |
| New implementation | No existing slug clearly owns the work | Create `docs/implementations/<slug>/spec.md` and `plan.md` |
| Patch/follow-up | The work fixes, extends, verifies, or clarifies an existing slug | Update that slug's `spec.md` and create `YYYYMMDD-HHMM-<topic>.patch-plan.md` in the slug root |

Prefer reusing an existing slug when ownership is clear. Creating a second slug
for a patch fragments the implementation context and makes later handoff weaker.

## Spec Update Rules

For a new slug:

- Create `spec.md` from the source requirement and relevant stable references.
- Make the current functional contract explicit.
- Separate goals, non-goals, data semantics, boundaries, acceptance semantics,
  and owner decisions.

For a patch:

- Update `spec.md` in place.
- Add a dated revision or patch note.
- Adjust the current contract so the latest intended behavior is unambiguous.
- Preserve old context only when it helps explain why the current contract
  changed.

Do not move durable docs into the slug. Reference them.

## Plan Writing Rules

For a new slug:

- Write `plan.md`.
- Include exact files, commands, expected results, and verification gates.

For a patch:

- Write a new `YYYYMMDD-HHMM-<topic>.patch-plan.md` in the slug root.
- Do not overwrite `plan.md`.
- Link the patch plan to the updated `spec.md` revision.
- Explain the delta from prior behavior and the regression checks needed to keep
  original acceptance semantics intact.
- If the patch plan names tracking tasks, inspect existing `T<number>` IDs in
  `dag.md`, task ledgers, the initial plan, and prior patch plans; continue from
  the highest existing number.

## Relationship To Dev With Track

This workflow stops at planning artifacts:

- create or update `spec.md`;
- create `plan.md` or a root-level `*.patch-plan.md`;
- review those planning artifacts for coherence.

`dev-with-track` owns the execution ledger: `dag.md`, task progress/handoff
files, `findings.md`, and `gate.md`. When tracked execution starts, pass the
selected slug and active plan file to `dev-with-track` instead of redefining
tracking rules here.

## Review

Review `spec.md` and the plan as a pair:

- Does the plan fully implement the current spec?
- Are product/data semantics in `spec.md` rather than hidden in the plan?
- Did patch routing reuse the right slug?
- Are owner decisions explicit?
- Are verification commands concrete?

Use a review subagent when the current environment and user permissions allow
it. If subagents are unavailable or inappropriate, run the checklist inline and
state that in the final summary.

Temporary review ledgers, if any, stay outside the repository. Formal documents
must stand alone without links to temporary review notes.

## Return Summary

Report:

- selected slug
- routing: new implementation or patch/follow-up
- files created or changed
- review method and corrections applied
- remaining owner decisions
- ready-for-implementation status
