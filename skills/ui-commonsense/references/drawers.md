# Drawer Commonsense

Use this reference for side sheets, drawers, slide-over forms, and full-height editing panels.

## Core Principles

- A drawer is focused editing, not a full page squeezed sideways.
- Drawer content should pack naturally from the top unless the design intentionally has a sticky footer.
- Header, body, and actions should have clear roles.
- Avoid nested card stacks inside drawers; a drawer already provides a container.

## Common Defects

- Full-height grid forms whose rows stretch across the available height.
- Fields separated by large vertical gaps unrelated to content.
- Primary action floating far away from the edited content without a stable footer.
- Inner cards around every row, creating “box inside box” noise.
- Long scroll regions inside other scroll regions.

## Fix Patterns

- Add `content-start` to grid form bodies that should not stretch.
- Remove `justify-between` from normal form groups.
- Use a fixed/distinct header and one scrollable body.
- Put save/cancel/status actions in a stable footer or final action row.
- Use row dividers or tables for repeated child rows instead of nested cards.
- Use switches for binary on/off status fields instead of selects.

## Checks

- Does the first field appear near the header with normal spacing?
- Does the drawer still look compact when the viewport is tall?
- Can the user find the save action without scrolling through unrelated whitespace?
- Does each border or background layer add meaning?
