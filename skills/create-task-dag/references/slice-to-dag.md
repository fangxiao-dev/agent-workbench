# Slice To DAG

Use this reference when the source is a broad implementation plan, bulk implementation request, spec, PRD, or handoff rather than one already-sized vertical slice.

If the source has not been sliced yet, do not turn the whole source into one DAG. Propose using the vertical slicing flow from `to-issues`, show the user that this is a slicing step, and wait for confirmation before doing it. Use `to-issues` in slicing-only mode: draft slices, review the breakdown with the user, and stop before tracker publication unless the user explicitly asks to publish tracker work items. After the user confirms the slice breakdown or supplies a sliced source, continue with the task DAG.

## Slice First

Start with vertical delivery slices before assigning workers. A slice is not a layer; it is a narrow end-to-end behavior that can be accepted on its own.

For each slice, record:

```markdown
| Slice | What to build | Blocked by | User stories covered | Acceptance gate |
| --- | --- | --- | --- | --- |
```

Good slices:

- deliver a Supplier Operator or Customer-visible outcome, or a required external validation gate;
- include enough data/API/UI/test work to be verifiable;
- can be reviewed independently;
- name dependencies explicitly.

Avoid turning layers into slices. "Update all source adapters" is usually a task; "persist threshold from UI through Lark readiness" is a slice.

## Then Draw Tasks

Inside each slice, draw parallelizable tasks:

- data/source/readiness;
- read-model construction;
- UI shell;
- i18n/copy review;
- seam integration;
- local/browser/external verification;
- final whole-slice review.

Some tasks, such as shared DTO contracts, may serve multiple slices. Treat them as contract tasks and freeze their output before parallel workers consume them.

When the DAG uses horizontal prerequisite tasks, say so explicitly. A worker finishing a horizontal task does not make the vertical slice accepted. The slice acceptance gate must name the task set and seam work required before that slice is demoable or externally verifiable.

## Relationship To Trackers

If the user asks to publish tracker issues, use `to-issues` or the project's tracker skill. This skill can provide the slice and DAG content, but it does not publish tracker work items by itself.

If the user asks only to update a plan, write the slice table and DAG into the requested artifact. In standalone mode this may be the plan, handoff, or repo-specific progress document. If a `dev-with-track` workspace exists, keep stable slice scope and acceptance in `plan.md`, and put live task contracts, cohorts, ownership, seams, and status in `dag.md`. Do not ask for tracker approval.
