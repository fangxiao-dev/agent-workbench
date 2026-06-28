# Combobox And Dropdown Commonsense

Use this reference for search-and-select controls and dropdown menus.

## Core Principles

- Selecting an existing object should use keyword search plus a dropdown.
- Users should not manually type IDs, keys, or hidden identifiers.
- Candidate options belong in the dropdown, not permanently expanded in the form.
- The selected value may stay in the input when it helps recognition.

## Interaction Rules

- Opening should happen on focus and click.
- Clicking an already-focused input should reopen the dropdown. Do not rely only on `onFocus`.
- Selecting an option should update hidden/submitted value and visible selected label.
- If the input remains focused after option click, make sure the next click can reopen the menu.
- Filtering should search useful visible fields, not only internal IDs.

## Display Rules

- Use a simple selected value in the input when enough.
- Add a selected summary below the input only if it provides new decision-making information.
- Avoid permanent chips/cards below the input just to repeat “Selected: X”.
- Dropdown option hover and selected states should be subtle and reversible.
- Avoid black selected rows unless the design system explicitly uses black as a neutral selected state.

## Layering Rules

- Dropdowns must render above following content.
- Check z-index and clipping inside drawers, cards, scroll containers, and grid layouts.
- Dropdown height should be capped with scroll, not push the entire form down excessively.

## Common Defects

- Option list always visible, making the form look like a static list.
- Input cannot reopen menu after a selection until focus moves elsewhere.
- Selected value hidden below the input instead of shown in the input.
- Dropdown clipped by parent overflow.
- Strong selected background that looks like a destructive or primary action.

## Checks

- Search by keyword, select, then immediately click the input again. Does the dropdown reopen?
- Is the submitted value stored separately from the visible label?
- Are options only visible when the dropdown is open?
- Does the dropdown stay above nearby content in the actual browser?
