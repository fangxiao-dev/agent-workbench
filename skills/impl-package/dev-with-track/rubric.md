# Dev With Track Rubric

## Confirmed preferences

- Preserve complete Progress: current Task/Ticket state、resume、Attempt checkpoint/judgment history and conditional Task Handoff.
- Keep `state.json` as the sole current-state source; Progress and runtime tables are projections.
- Task completion never implies Ticket acceptance.
- Evidence paths are repository-relative and must exist.
- Gate contains the current verdict; Git contains history.
- Revalidate only the subset affected by an actual contract or plan change.
