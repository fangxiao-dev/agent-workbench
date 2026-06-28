# Visual State Commonsense

Use this reference for hover, selected, focus, disabled, loading, primary, secondary, and destructive states.

## Core Principles

- Visual state should communicate interaction state, not surprise the user.
- Hover is temporary affordance; selected is persistent state.
- Primary actions should be visually stronger than secondary actions.
- Destructive actions need a distinct but not overwhelming treatment.

## Rules

- Hover states should not look like permanent selection.
- Selected states should remain visible after pointer leaves.
- Focus rings must remain visible and keyboard-navigable.
- Disabled controls should explain why when the reason is not obvious.
- Loading buttons should preserve approximate width and show pending scope.
- Icon-only buttons need accessible labels and familiar icons.
- Strong black/dark fills should be reserved for primary actions or explicit design-system selected state.

## Common Defects

- A selected dropdown row appears as a black primary CTA.
- Hover state hides text or changes layout.
- Loading label changes button width and shifts nearby content.
- Disabled action appears broken because no reason is shown.
- Focus outline removed for aesthetics.

## Checks

- Can users distinguish hover, selected, disabled, and loading at a glance?
- Does keyboard focus remain visible?
- Does a state change move neighboring UI?
- Is there only one primary action in a local action group?
