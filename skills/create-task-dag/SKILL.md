---
name: create-task-dag
description: Use when a vertical slice, implementation plan, spec, PRD, handoff, or tracked implementation should become a task DAG for parallel work. Trigger when the user asks to decompose slices, build a task DAG, assign ownership, freeze contracts, coordinate workers, integrate seams, or run final whole-slice review.
---

# Create Task DAG

Use this skill to turn a vertical slice or already-sliced source into dispatchable worker cohorts with clear ownership, stable contracts, integration seams, and final slice-level review.

When the source is a broad implementation plan, bulk implementation request, spec, PRD, or other large source that has not been sliced yet, do not silently draw one oversized DAG. Propose using the vertical slicing flow from `to-issues` first, and ask the user to confirm before doing that slicing. Use `to-issues` in slicing-only mode: stop after drafting and user-confirming the slice breakdown. Do not enter its tracker publication step unless the user explicitly asks for tracker publication. After the user confirms the slice breakdown or provides an already-sliced source, draw a task DAG inside each slice or across shared contract work. Parallelism happens inside the delivery boundary, not by losing the vertical acceptance gate. If the DAG contains horizontal prerequisite tasks, name the slice gates that consume them.

Persistence is optional. This skill works standalone: output the DAG artifacts inline or into the current plan, handoff, tracker note, or repo-specific progress document requested by the user. If a `dev-with-track` implementation workspace exists, prefer its roles as the persistence target:

- stable scope and acceptance changes -> `plan.md`;
- task contracts, cohorts, ownership, status, seams, and verification gates -> `dag.md`;
- durable task-local state -> `tasks/Tn-progress.md`;
- task transfer -> `tasks/Tn-handoff.md`;
- cross-task risks and follow-ups -> `findings.md`;
- final review and closure decision -> `gate.md`.

Do not require a tracking workspace before using this skill.

## Operating Principle

- **Slice:** a vertical delivery unit with user-facing behavior, acceptance criteria, full test matrix, browser evidence, and external smoke when needed.
- **Task DAG:** internal dependency graph that unlocks parallel workers.
- **Main session:** scheduler, contract owner, seam owner, integration validator, external gatekeeper.
- **Worker:** bounded implementer for one task or narrow cohort.
- **Final reviewer:** whole-slice reviewer after task outputs are integrated.

Do not serialize implementation just because shared files exist. Instead, give shared files explicit ownership and make workers report seam needs instead of editing outside their lane.

Use **ownership lanes** instead of a flat owned-files list. Each worker prompt and DAG task should distinguish primary owned files, conditional seam files, and forbidden files. This keeps plan ownership and worker prompts aligned, and makes intentional seam edits reviewable instead of accidental scope creep.

Use **seam status** precisely. A planned dependency between parallel tasks is `NEEDS_SEAM`, not `BLOCKED`. Reserve `BLOCKED` for missing context, missing permission, unavailable data, a wrong plan, or a human decision.

## Workflow

### 1. Ground The Slice

Read the active slice, implementation plan, spec, handoff, repo instructions, and relevant verification docs. If the source is broad and unsliced, use `references/slice-to-dag.md` and ask the user to confirm before invoking `to-issues` in slicing-only mode. Identify:

- final behavior and acceptance criteria;
- current branch and dirty state;
- external mutation permissions and red lines;
- likely shared seam files;
- required local, browser, and external verification.

Completion criterion: the main session can state the vertical slices, what must ship, what must not be touched, and which decisions are still truly owner-owned.

### 2. Freeze Shared Contracts

Before dispatching workers, freeze the contracts they need to work independently:

- DTO/type/API fields;
- fallback and compatibility rules;
- route/page prop names;
- i18n namespace/key conventions;
- UI states expected from worker-owned data;
- external smoke marker and cleanup protocol.

Completion criterion: a worker can consume or produce its assigned contract without inventing shape or touching unowned files.

### 3. Draw The DAG And Ownership Map

Use `references/dag-and-ownership.md` for the task table, ownership patterns, and cohort rules.

Record the DAG in the user's requested artifact. If a `dev-with-track` workspace exists, record task contracts, cohorts, ownership, status, seams, and verification gates in `dag.md`; use `plan.md` only for stable scope or acceptance changes.

Completion criterion: every task has dependencies, parallel-safe neighbours, ownership lanes, focused tests, and done criteria; every vertical slice names the tasks and seams required before the slice can be accepted.

### 4. Dispatch Parallel Worker Cohorts

Use `references/worker-prompts.md` for worker prompt shape and status handling.

Dispatch all tasks in the same cohort that have stable contracts and non-overlapping primary write sets. Generate worker prompts from the DAG ownership lanes; do not hand-write a narrower or broader ownership list than the DAG. Keep shared seam files with the main session or one explicitly named seam worker.

Completion criterion: each worker has a bounded prompt and cannot reasonably mistake its task for the whole slice.

### 5. Integrate Seams

The main session resolves cross-task seams:

- route/page wiring;
- shared type exports;
- dictionary merges;
- prop shape mismatches;
- test matrix gaps;
- conflicts between worker outputs.

Completion criterion: the integrated worktree reflects one coherent vertical slice, not adjacent task islands.

### 6. Review And Verify The Whole Slice

Use `references/review-and-verification.md` for task review, final review, and verification gates.

Task-level review is not enough. After integration, dispatch or perform a whole-slice review against the original slice/source and full diff.

Completion criterion: local integration tests, required browser checks, external smoke gates, and final review status are all recorded honestly.

## Output Contract

When this skill is used for planning or execution setup, output or record:

```markdown
## Task DAG
| Task | Depends on | Can run with | Owns | Must not touch | Gate |
| --- | --- | --- | --- | --- | --- |

## Shared Contracts
- ...

## Parallel Cohorts
- Cohort 1:
- Cohort 2:
- Final:

## Integration Seams
- ...

## Verification Gates
- ...
```

When this skill is used during execution, final reporting must include:

- worker cohorts dispatched;
- seams handled by the main session;
- tests and browser/external checks actually run;
- final whole-slice review result;
- remaining risks or blocked gates.
