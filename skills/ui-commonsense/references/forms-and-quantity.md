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
- Keep notes secondary. Do not add line-level note fields unless each line truly has independent note semantics.
- Avoid long note inputs inside compact operational rows.

## Common Defects

- Text inputs for numeric values, causing no steppers and weak validation.
- Quantity and unit split across unrelated columns.
- Save buttons whose scope is unclear.
- Row forms with extra subtext and helper text that users do not need during repeated operation.
- Multiple forms in one row that appear to do the same thing.

## Checks

- Can the user adjust a number quickly with keyboard or steppers?
- Does the unit move with the number if the row is scanned or copied?
- Is the save scope obvious?
- Are notes present only where they change a user decision?
