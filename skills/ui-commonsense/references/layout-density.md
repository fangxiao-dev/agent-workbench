# Layout And Density Commonsense

Use this reference when UI feels too sparse, too cramped, visually unbalanced, or hard to scan.

## Core Principles

- Operations/admin UI should be dense but readable. Large decorative whitespace slows repeated work.
- Layout should reflect content shape. Short labels, numbers, action buttons, and free-text notes should not all receive equal-width columns.
- Keep related controls close together. The user should not have to scan across a wide blank area to understand what a button affects.
- Prefer compact rows for repeated operational items. Use cards only when each repeated item is truly independent.
- Do not stretch content vertically just because the parent has available height.
- Dense operational rows should look intentional even when there is only one item; a single row should not inflate into a large card-like panel.

## Common Defects

- Equal-width grid columns where numbers and actions waste space.
- Read-only numbers that visually sit above or below nearby inputs.
- Huge empty panels used to “fill” a dashboard column.
- Summary cards with mostly blank content.
- Empty states that dominate the page more than real data would.
- A note field or secondary control taking more visual priority than the primary workflow.
- Artificial row height from fixed `min-height`, `1fr` spacer tracks, or empty filler elements used to force alignment.
- Adding broad `overflow-x-auto` or scroll containers to a shared shell to hide one page's wide table. This can break sticky headers, sidebars, overlays, focus containment, and viewport-specific verification.
- Filter/tool/action grids with fixed desktop columns that push buttons or selects outside the card at medium widths.

## Fix Patterns

- Use explicit grid tracks, e.g. narrow supplier/action columns, medium numeric columns, flexible note/content columns.
- Align comparable values with `flex h-[input-height] items-center` or equivalent.
- For dense table rows, prefer table-cell vertical alignment, shared control heights, or explicit grid tracks over fixed row `min-height` and spacer rows.
- Convert tall cards to horizontal metric rows when users only need quick comparison.
- Remove section wrappers that do not add grouping meaning.
- Use row dividers instead of separate cards when list items belong to one continuous set.
- Scope overflow fixes to the content that is actually wide. For example, wrap a business table or row group locally instead of placing horizontal scrolling on the admin shell, page root, sticky header ancestor, or navigation container.
- For toolbar and filter forms, use responsive wrapping first: let inputs form 1-2 columns before wide desktop, keep action buttons `min-w-0`, and only switch to dense fixed tracks when the viewport can actually contain them.

## Checks

- Can the user scan the important values in one horizontal pass?
- Are actions close to the fields they save or affect?
- Does the layout still look intentional when only one row/item exists?
- Is any large blank region caused by flex/grid stretching rather than real content?
- Is alignment achieved by real control geometry rather than invisible spacers or arbitrary minimum heights?
- If horizontal scroll exists, is it owned by the specific table/list that needs it rather than a shared shell ancestor?
