# Worker Prompts

Use this reference when dispatching implementation or review workers.

## Implementation Worker Prompt

```markdown
You are implementing Task <ID> for <slice>.

Workspace:
- <path>

Tracking:
- <standalone / dev-with-track>
- Progress ledger: <tasks/Tn-progress.md or N/A>
- Handoff ledger: <tasks/Tn-handoff.md or N/A>

Slice goal:
- <summary>

Your ownership:
- You may edit: <files/modules>
- You must not edit: <files/modules>

Contracts:
- Input: <DTO/API/props you consume>
- Output: <DTO/API/behavior you produce>

Requirements:
- <acceptance bullets>

Tests to run:
- <focused commands>

Rules:
- You are not alone in this codebase.
- Do not revert changes made by others.
- Do not edit files outside your ownership.
- If an unowned edit is needed, return NEEDS_SEAM instead of making it.

Return:
- status: DONE / DONE_WITH_CONCERNS / NEEDS_SEAM / BLOCKED
- files changed
- tests run and results
- unowned seam needs
- residual risks
```

When a worker returns status or evidence and a `dev-with-track` progress ledger exists, update `tasks/Tn-progress.md`. Create `tasks/Tn-handoff.md` only when the task needs standalone transfer to another session, agent, or worker.

## Status Handling

- `DONE`: proceed to task spec review.
- `DONE_WITH_CONCERNS`: read concerns before review; resolve correctness or scope concerns first.
- `NEEDS_SEAM`: main session handles the seam or changes ownership before continuing.
- `BLOCKED`: provide missing context, split the task, change model/worker, or escalate if the plan is wrong.

Do not ask the same worker to retry without changing the context that caused the status.

## Review Worker Prompts

Task spec reviewer:

```markdown
Review Task <ID> against its task contract.

Check:
- required behavior implemented;
- no unowned scope added;
- promised tests are present or reported;
- output contract matches the frozen shared contract.

Return APPROVED or NEEDS_CHANGES with concrete findings.
```

Task quality reviewer:

```markdown
Review Task <ID> for implementation quality.

Check:
- maintainability;
- local patterns;
- test coverage for risky behavior;
- unnecessary abstractions or coupling;
- hidden cross-task assumptions.

Return APPROVED or NEEDS_CHANGES with concrete findings.
```

Whole-slice reviewer:

```markdown
Review the integrated slice, not an individual task.

Inputs:
- original slice/source/plan;
- final diff or commit range;
- DAG, progress, handoff, or tracking artifacts;
- verification evidence.

Check:
- every acceptance item is covered;
- task outputs fit together;
- shared contracts stayed consistent;
- no worker left an unintegrated seam;
- browser/external smoke risks are explicit;
- test matrix is sufficient or gaps are named.

Return APPROVED or NEEDS_CHANGES with severity-ranked findings.
```
