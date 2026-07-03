---
name: dev-with-track
description: Tracked development workflow for implementation workspaces with plan/dag/findings/gate ledgers, task-wise progress records, midstream plan adoption, evidence capture, verification gates, and follow-up tracking. Use when the user wants a tracked implementation, DAG/cohort board, gate decisions, findings updates, evidence capture, or a reusable execution ledger.
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

- stable scope and acceptance changes -> `plan.md`;
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
├── plan.md
├── dag.md
├── findings.md
├── gate.md
└── tasks/
    ├── Tn-progress.md
    └── Tn-handoff.md
```

If the repo already has a different conventional root, follow it, but keep the roles intact.

Do not migrate legacy flat plans just to clean the tree. When this skill enters midstream and an impl plan already exists, adopt it into the workspace by creating the slug directory and either:

- moving/copying the existing plan content into `plan.md` when the user asked to reorganize it; or
- creating `plan.md` as a short adoption wrapper that links to the original plan and states that the original remains the plan source.

Completion criterion: the implementation has one clear entry point and the original plan is not orphaned.

## File Roles

- `plan.md`: implementation plan and product/engineering control document: goals, scope, acceptance gates, constraints, and implementation strategy.
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

## First Reads

1. Read repo instructions first: root `AGENTS.md`, app/workspace instructions, and relevant verification docs.
2. Locate any existing implementation plan, flat impl-plan file, roadmap, handoff, process ledger, findings, gate, and evidence.
3. Read `references/control-flow.md` when adopting midstream state, deciding ledger roles, or closing gates.
4. If scaffolding is needed, use templates in `assets/templates/`.

## Operating Rules

- Track by role, not by filename. If the repo uses different names, preserve the roles.
- Treat `plan.md` as the implementation source of truth; do not turn `dag.md` or task ledgers into competing plans.
- Treat `dag.md` as the live coordination surface for main-session scheduling, worker ownership, status, seams, and gates.
- Keep task ledgers thin. They should restore local task state, not become mini implementation plans.
- Promote only cross-task conclusions to `findings.md`.
- Update `gate.md` only when closing, blocking, or explicitly deferring implementation-level acceptance.
- Keep evidence honest: record what actually ran, what was skipped, and why.
- Use project verification commands from repo docs; do not import commands from another project.

## Minimal Execution Checklist

1. Restore or create the implementation workspace.
2. Ensure the active plan is represented by `plan.md`, including midstream adoption of an existing plan when needed.
3. Update `dag.md` with task/cohort status, owner, gate/evidence, and seam notes.
4. Decide whether any task needs a `tasks/Tn-progress.md` ledger using the triggers above.
5. Execute or coordinate the next controlled task.
6. Capture task evidence in the task ledger or `dag.md`.
7. Promote cross-task findings to `findings.md`.
8. Update `gate.md` when implementation-level closure, blocker, or defer decision changes.
9. Report the implementation state by role: plan status, DAG/cohort status, task ledgers touched, findings promoted, gate state.

## Templates

Use these templates when the repo lacks the corresponding ledger:

- `assets/templates/plan.md`
- `assets/templates/dag.md`
- `assets/templates/progress.md`
- `assets/templates/handoff.md`
- `assets/templates/findings.md`
- `assets/templates/gate.md`
