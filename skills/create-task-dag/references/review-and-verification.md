# Review And Verification

Use this reference after workers return or when closing the slice.

## Review Layers

- **Task spec review:** confirms a worker satisfied its bounded task contract.
- **Task quality review:** confirms the worker's patch is maintainable and locally tested.
- **Whole-slice review:** confirms the integrated vertical slice satisfies the original slice source.

Do not close the slice after task-level approvals alone. Task approvals can miss broken seams, duplicated fallback policy, missing route props, i18n drift, and external smoke gaps.

## Main Session Integration Checks

Before final review, the main session should verify:

- shared contracts still have one meaning;
- no two workers implemented competing fallback rules;
- route/page props and shared exports are wired once;
- i18n keys exist in every locale and do not drift semantically;
- tests cover the slice-level behavior, not only isolated helpers;
- process, progress, handoff, or tracking notes match what actually ran.

## Verification Gates

Workers run focused tests for their ownership. The main session runs the slice matrix after integration.

For UI changes:

- verify the changed route in a real browser;
- cover desktop and constrained viewport when no specific viewport is reported;
- record sticky/floating element geometry when headers, drawers, menus, or overlays change;
- record horizontal overflow status when table/list layout changes.

For external systems:

- run external smoke only after local and browser evidence;
- print and confirm non-production target identity before mutation;
- use a unique marker;
- record created/updated record IDs;
- read back the field/behavior being proven;
- clean up or record retained residue and why cleanup failed.

## Final Report Shape

For slice completion, report:

- committed changes or dirty files;
- worker cohorts and main-session seams;
- commands run and results;
- browser evidence;
- external smoke run/not run and why;
- residual risk;
- final whole-slice review status.

## Persistence Mapping

Standalone mode can keep review and verification evidence inline, in the current plan, or in the requested handoff/progress artifact.

When a `dev-with-track` workspace exists:

- write whole-slice review and closure status to `gate.md`;
- write cross-task risks or follow-ups to `findings.md`;
- write local task review findings to `tasks/Tn-progress.md`;
- write task transfer details to `tasks/Tn-handoff.md`;
- keep cohort and seam status in `dag.md`.
