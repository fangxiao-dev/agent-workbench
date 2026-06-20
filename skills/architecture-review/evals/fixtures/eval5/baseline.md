# Foundation Baseline: Membership and Dashboard v0

## Required P0 gates

- Membership and role changes must write a durable business audit row with actor,
  target user, previous role, next role, and reason.
- Authorization must fail closed when a caller lacks the `members.manage`
  permission.

## Explicitly out of scope for this review

- AI dashboard summaries are a prototype surface. Do not block the foundation on
  missing prompt governance, model selection, or summary quality unless they
  affect a required P0 gate above.
