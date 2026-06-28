# Tables, Lists, And Rows Commonsense

Use this reference when representing repeated items, ingredients, orders, inventory rows, or compact dashboards.

## Choose The Structure

- Use a table when users compare repeated attributes by column.
- Use a compact row when each item has one primary edit/action path.
- Use cards for independent objects that need their own local hierarchy.
- Use dividers before nested cards when rows belong to one list.

## Column Semantics

- Keep columns semantically clean.
- Name columns contain names.
- Source/supplier columns contain source/supplier labels.
- Quantity columns contain quantity plus unit.
- Status columns contain state labels or badges.
- Action columns contain controls.
- Do not expose database-facing keys, record IDs, operation IDs, idempotency keys, or integration linkage keys in normal UI tables/lists. Show user-meaningful names, statuses, timestamps, actors, quantities, and evidence labels instead; keep technical keys in hidden form fields, logs, diagnostics, or explicit developer/debug views.

Do not mix unit, status, and source into a name just to save space.

## Density Rules

- Do not wrap every child row in a rounded bordered card inside another bordered container.
- A repeated line item inside a form should usually be one row.
- If line items need headers, use a lightweight table rather than repeated labels per row.
- Empty states should be shorter than real data rows would be.

## Common Defects

- “Box inside box” line items.
- Repeated field labels that make a dense list tall.
- Metadata concatenated into one long label where users need separate columns.
- Internal database or integration keys shown as if they are operational information for end users.
- Action buttons separated far from the row they affect.
- Tables without headers when the row data is not self-evident.

## Checks

- Can users compare row values without reading every sentence?
- Are units and quantities in the same cell?
- Is the row action visually scoped to that row?
- Are all visible identifiers meaningful to the user rather than database/debug keys?
- Could the same information be clearer as a table?
