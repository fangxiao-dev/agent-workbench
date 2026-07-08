---
name: dev-with-track
description: Tracked development workflow for implementation workspaces with temporary design/spec, plan/dag/findings/gate ledgers, task-wise progress records, midstream plan adoption, evidence capture, verification gates, and follow-up tracking. Use when the user wants a tracked implementation, implementation-local design/spec roles, DAG/cohort board, gate decisions, findings updates, evidence capture, or a reusable execution ledger.
user-invocable: true
---

# Dev With Track

Use this skill to create or maintain an implementation workspace that survives context loss and supports parallel execution. The durable unit is an implementation, not a chat turn and not a single slice file.

The core loop is:

```text
restore implementation -> update DAG -> execute task -> capture evidence -> promote findings -> decide gate
```

This skill owns tracking structure only. Domain skills, repo `AGENTS.md`, implementation plans, and verification docs still own product language, safety rules, commands, and acceptance details.

## Companion Skills

When the implementation needs worker cohorts, parallel-safe task decomposition, ownership boundaries, seam handling, or whole-slice review, use `create-task-dag` for the scheduling method. Persist its outputs into this implementation workspace:

- implementation-local top design and stable-doc backfill source -> `design.md` when the work creates PRD/ARD/tech-stack knowledge;
- temporary task-specific functional contract -> `spec.md`;
- implementation execution strategy and acceptance checklist -> `plan.md`;
- task contracts, cohorts, ownership, status, seams, and verification gates -> `dag.md`;
- durable task-local state -> `tasks/Tn-progress.md`;
- task transfer -> `tasks/Tn-handoff.md`;
- cross-task risks and follow-ups -> `findings.md`;
- final review and closure decision -> `gate.md`.

Do not reimplement the DAG method here. This skill provides the durable container; `create-task-dag` provides the parallel execution protocol.

## Implementation Workspace

For new tracked work, create one implementation slug directory:

```text
docs/implementations/<implementation-slug>/
├── [design.md]
├── spec.md
├── plan.md
├── [YYYYMMDD-HHMM-<patch-topic>.patch-plan.md]
├── dag.md
├── findings.md
├── gate.md
└── tasks/
    ├── Tn-progress.md
    └── Tn-handoff.md
```

If the repo already has a different conventional root, follow it, but keep the roles intact.

`design.md` is optional. Create it when the implementation produces top-level product, architecture, or runtime knowledge that should later be backfilled into stable PRD, Func Design, ARD, Tech Stack, or hands-on knowledge docs. It is implementation-local and temporary; it is not itself the stable destination.

`spec.md` is required. It is the temporary, task-specific Func Design / implementation spec for this slug. It can be thick or thin, but it must exist so the implementation workspace has one local functional-contract entrypoint.

`plan.md` is the initial implementation plan. Root-level
`YYYYMMDD-HHMM-<patch-topic>.patch-plan.md` files are patch/follow-up plan
inputs for the same slug. This skill consumes those plan files when refreshing
the execution ledger; it does not redefine the planner's spec/plan authoring
rules.

Do not place an ad-hoc task spec directly into long-lived `docs/func-design/` by default. If an ad-hoc spec or Func Design already exists for this exact implementation, adopt it into the slug directory as `spec.md` when allowed. If the existing `docs/func-design/...` document is already a stable long-lived design, do not move it; create a thin `spec.md` that references the stable design and records only this implementation's delta, scope, non-goals, and temporary decisions.

Do not migrate legacy flat plans just to clean the tree. When this skill enters midstream and an active impl plan already exists for the same implementation, adopt that plan as the workspace plan by moving it into the slug directory as `plan.md`, then adjust its links and tracking metadata in place. Do not copy the plan and do not create a wrapper plan, because duplicate plan sources drift quickly.

Only preserve the original plan path when the user explicitly asks to keep that path stable. In that exception, make the tracked `plan.md` a short pointer and mark the original path as the plan source.

Only preserve the original ad-hoc spec path when the user explicitly asks to keep that path stable or when moving it would break an accepted project index. In that exception, make `spec.md` a short pointer/adoption wrapper and mark the original path as the current spec source.

Completion criterion: the implementation has one clear entry point, `spec.md` and `plan.md` both exist, previous ad-hoc spec/plan paths are either moved or explicitly preserved, and repo indexes/links point to the active implementation workspace.

## File Roles

- `design.md`: optional task-local top design and stable-doc backfill source: product/PRD notes, architecture/ARD notes, tech-stack/runtime notes, and a stable-doc backfill map. Use it to avoid stuffing PRD, ARD, and tech-stack material into `spec.md`.
- `spec.md`: temporary task-specific Func Design / implementation spec: functional contract, referenced stable specs, task-local deltas, non-goals, acceptance semantics, and open decisions. It is source material for later stable-doc backfill, not automatically a long-lived design.
- `plan.md`: implementation plan and engineering execution document: implementation strategy, file scope, task outline, verification plan, and acceptance checklist. Do not make it the primary home for functional behavior when `spec.md` exists.
- `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`: patch/follow-up execution input for the same implementation slug. Treat it as a plan delta layered on top of `spec.md` and `plan.md`; map it into `dag.md` and task ledgers without overwriting the initial plan.
- `dag.md`: execution control board: cohorts, task ownership, seams, status, gates, and verification evidence.
- `tasks/Tn-progress.md`: task-wise progress ledger for tasks that need their own record.
- `tasks/Tn-handoff.md`: optional task-level handoff, only when that task needs a standalone transfer across sessions or agents.
- `findings.md`: cross-task findings, risks, decisions, follow-ups, and reusable lessons that are not just local task notes.
- `gate.md`: final closure dossier for the implementation.

Avoid root `process.md` for new implementation work. It tends to duplicate `plan.md` and `dag.md`. For legacy tracked slices that already use `process.md`, read it as legacy state and map its current facts into the implementation roles when useful.

## When To Create A Task Ledger

Keep simple tasks as one row in `dag.md`. Create `tasks/Tn-progress.md` only when at least one trigger applies:

- independent owner or subagent;
- dedicated external gate such as Chrome, Lark, email, Lexware, public smoke, or production-like verification;
- `NEEDS_SEAM`, blocker, reviewer finding, or unresolved decision;
- expected to continue across sessions;
- independent evidence that must be preserved, such as record IDs, smoke markers, screenshots, cleanup results, or target identity;
- affects the final gate, but the details would make `dag.md` too crowded.

Completion criterion: every task with durable state has a ledger; trivial seam edits and one-off tests stay in `dag.md`.

Do not invent other task-level documents by default. Put evidence, reviewer findings, and local notes into `Tn-progress.md` until that convention proves too crowded. Create `Tn-handoff.md` only when a task needs a separate handoff for another session, agent, or worker.

Task IDs are stable within a slug. Before adding tasks, inspect `dag.md`,
`tasks/T*-progress.md`, `tasks/T*-handoff.md`, `plan.md`, and root-level
`*.patch-plan.md`; assign the next `T<number>` after the highest existing task
number. Never renumber existing tasks just to make a patch plan look tidy.

## First Reads

1. Read repo instructions first: root `AGENTS.md`, app/workspace instructions, and relevant verification docs.
2. Locate any existing ad-hoc spec / Func Design, implementation plan, root-level `*.patch-plan.md`, flat impl-plan file, roadmap, handoff, process ledger, findings, gate, and evidence.
3. Read `references/control-flow.md` when adopting midstream state, deciding ledger roles, or closing gates.
4. If scaffolding is needed, use templates in `assets/templates/`.

## Operating Rules

- Track by role, not by filename. If the repo uses different names, preserve the roles.
- Use `design.md` for upper-layer knowledge that cuts across stable-doc destinations. Do not duplicate its content into `spec.md`; let `spec.md` reference it and define only the current functional contract.
- Treat `spec.md` as the task-local functional contract. Treat `plan.md` as the implementation execution source of truth. Do not turn `dag.md` or task ledgers into competing specs or plans.
- Treat root-level `*.patch-plan.md` as planner-produced deltas for the same slug. Consume them when updating `dag.md`, task ledgers, findings, and gate state; keep the authoring rules for patch plans in the planning skill.
- Keep temporary `spec.md` distinct from stable `docs/func-design/` / PRD / ARD documents. Stable-doc backfill is a later documentation-maintenance task unless the user explicitly includes it in the current implementation.
- Treat `dag.md` as the live coordination surface for main-session scheduling, worker ownership, status, seams, and gates.
- Keep task ledgers thin. They should restore local task state, not become mini implementation plans.
- Promote only cross-task conclusions to `findings.md`.
- Update `gate.md` only when closing, blocking, or explicitly deferring implementation-level acceptance.
- Keep evidence honest: record what actually ran, what was skipped, and why.
- Use project verification commands from repo docs; do not import commands from another project.

## Minimal Execution Checklist

1. Restore or create the implementation workspace.
2. Decide whether `design.md` is needed for PRD/ARD/tech-stack backfill knowledge; create or update it when needed.
3. Ensure the active temporary task spec is represented by `spec.md`, including midstream adoption of an existing ad-hoc spec / Func Design when needed.
4. Ensure the active plan is represented by `plan.md`, including midstream adoption of an existing plan when needed.
5. Update `dag.md` with task/cohort status, owner, gate/evidence, and seam notes.
6. Decide whether any task needs a `tasks/Tn-progress.md` ledger using the triggers above.
7. Execute or coordinate the next controlled task.
8. Capture task evidence in the task ledger or `dag.md`.
9. Promote cross-task findings to `findings.md`.
10. Update `gate.md` when implementation-level closure, blocker, or defer decision changes, including stable-doc backfill status if relevant.
11. Report the implementation state by role: design status when present, spec status, plan status, DAG/cohort status, task ledgers touched, findings promoted, gate state.

## Templates

Use these templates when the repo lacks the corresponding ledger:

- `assets/templates/design.md`
- `assets/templates/spec.md`
- `assets/templates/plan.md`
- `assets/templates/dag.md`
- `assets/templates/progress.md`
- `assets/templates/handoff.md`
- `assets/templates/findings.md`
- `assets/templates/gate.md`
