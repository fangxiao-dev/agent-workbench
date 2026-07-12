---
name: ui-commonsense
description: Use when implementing, refactoring, or reviewing frontend UI with common usability defects: unclear object/action ownership, mixed-abstraction navigation, excessive spacing, stretched drawers, nested cards, awkward forms, broken combobox/dropdown behavior, misaligned fields, quantity inputs without steppers, unclear table/list structure, weak visual states, private-page loading boundaries, or incomplete browser verification. This is an entry-map skill: load the relevant references before changing UI.
---

# UI Commonsense

Repository-local entry map for practical UI defect prevention. This skill is not a style system and does not decide product/business semantics. It routes recurring frontend problems to focused references so the agent can avoid low-level usability mistakes before implementation and before final review.

## How To Use

1. Identify the UI surface and failure mode from the user request, screenshot, or browser evidence.
2. Before designing new controls or feedback patterns, run the reusable component check below.
3. Load only the reference files that match the failure mode.
4. Apply the reference as a checklist while inspecting code and rendered UI.
5. Verify with browser interaction or DOM measurements when the issue is visual, spatial, or behavioral.

## Reusable Component Check

Before creating an action result, async submit button, dialog, data table, badge, combobox, editable row, or repeated admin control:

1. Check `docs/top-level-knowledge/ui-component-inventory.md`.
2. Search the codebase for the relevant component or behavior keyword.
3. Prefer an existing component when it covers about 80% of the need.
4. If you intentionally do not reuse it, state the missing behavior or mismatch.

Load `references/reusable-components.md` for reusable component discovery, extraction, or review work.

## User-Facing Data Rule

Normal UI should expose user-meaningful names, statuses, timestamps, actors, quantities, and operational evidence. Do not show database-facing keys, record IDs, operation IDs, idempotency keys, or integration linkage keys unless the surface is explicitly a developer/debug/diagnostic view.

## Reference Map

- `references/object-owned-operations.md`
  Use before designing operational/admin navigation, tabs, detail surfaces, row actions, or editable object workflows. Helps decide which concept owns a property or action before layout work begins.

- `references/reusable-components.md`
  Use before adding reusable-looking controls, feedback messages, buttons, dialogs, tables, badges, comboboxes, editable rows, or admin UI patterns.

- `references/layout-density.md`
  Use for excessive whitespace, equal-width columns, cramped rows, baseline misalignment, oversized empty states, or dashboard/card density problems.

- `references/drawers.md`
  Use for drawer/sheet forms, full-height panels, vertical stretching, sticky headers/footers, and drawer action placement.

- `references/forms-and-quantity.md`
  Use for numeric inputs, steppers, units, editable rows, note fields, row-level save actions, and form control selection.

- `references/comboboxes.md`
  Use for search-and-select controls, dropdown behavior, selected value display, reopen-on-click bugs, option hover/selected states, and z-index/clipping issues.

- `references/tables-lists-rows.md`
  Use for deciding between table/list/card, avoiding card-in-card, defining clean columns, showing units in the right column, and compact repeated row layouts.

- `references/visual-states.md`
  Use for hover, selected, disabled, loading, focus, danger, and primary/secondary action states.

- `references/server-data-boundaries.md`
  Use when structuring a private or personalized page, deciding whether data belongs behind a Suspense boundary, preserving access-before-data-read order, or extracting async content for tests. Explains when a stable shell is useful and when this pattern is unnecessary.

- `references/browser-verification.md`
  Use before claiming completion. Contains browser verification scenarios and DOM measurement snippets for layout, combobox, drawer, and alignment checks.

## Default Review Flow

For most UI refactors, load these in order:

1. `references/object-owned-operations.md`
2. `references/reusable-components.md`
3. `references/layout-density.md`
4. `references/forms-and-quantity.md`
5. `references/comboboxes.md`
6. `references/browser-verification.md`

For drawer-heavy work, add `references/drawers.md`.
For repeated data or ingredients/items/orders, add `references/tables-lists-rows.md`.
For feedback about “looks wrong when hovered/selected/disabled”, add `references/visual-states.md`.

## Output Expectations

When using this skill during implementation or review, report:

- which references were loaded;
- the UI defects found or prevented;
- the concrete fixes made or recommended;
- browser verification evidence, not just code inspection.

Keep reports short and grounded in the rendered UI.
