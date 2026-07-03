# Forms And Quantity Commonsense

Use this reference for form controls, editable rows, numeric values, units, notes, and save behavior.

## Control Choice

- Use the native control that matches the data.
- Quantities, counts, thresholds, and stock values should use `type="number"` unless there is a strong reason not to.
- If decimal values are valid, use `step="any"` or a domain-specific decimal step.
- Keep native steppers available for quick increment/decrement.

## Quantity And Units

- Put units with the quantity value.
  - Good: `2,5 kg` in a quantity cell.
  - Bad: `Salt · kg` in a name cell while the quantity is elsewhere.
- Align read-only quantity values with editable numeric fields around them.
- Avoid making a user choose increase/decrease when a signed or directly editable numeric value is clearer.

## Editable Rows

- If the whole row is saved together, put the save button in an `Action` column or clearly scoped row action area.
- If a field can be directly edited, avoid adding a separate adjustment form unless it represents a different workflow.
- In compact row editors, align inputs, switch-like controls, action buttons, and preview chips to a shared height token.
- Short fields such as price, status, quantity, or availability usually belong in one horizontal control row, not stacked as a small form.
- Inline previews should read as compact metric chips when they summarize one or two values; avoid mini card stacks inside each row.
- Keep notes secondary. Do not add line-level note fields unless each line truly has independent note semantics.
- Avoid long note inputs inside compact operational rows.
- Do not add dividers around notes unless the note changes the row's primary decision; dividers can give secondary text too much visual priority.

## Common Defects

- Text inputs for numeric values, causing no steppers and weak validation.
- Quantity and unit split across unrelated columns.
- Save buttons whose scope is unclear.
- Row forms with extra subtext and helper text that users do not need during repeated operation.
- Multiple forms in one row that appear to do the same thing.
- Inputs, switches, preview chips, and row actions using different heights, making the row look uneven.
- Price/status/quantity controls stacked vertically when users need to scan and edit repeated rows quickly.

## Checks

- Can the user adjust a number quickly with keyboard or steppers?
- Does the unit move with the number if the row is scanned or copied?
- Is the save scope obvious?
- Are notes present only where they change a user decision?
- Do same-row controls share a consistent height and baseline?
