# Audit Runbook

1. Resolve the main worktree and record Source HEAD、branch、dirty state.
2. Validate the repository configuration and target branch.
3. Collect optional pending files, `records.done`, and direct child packages.
4. Emit item-level inventory: `pending-registry` items, reachable terminal Gate Durable Deltas as `gap-catching`, and done-filtered items with reasons. Pending never suppresses gap-catching; done does.
5. Read each source, current code/tests and destination stable docs.
6. Classify each durable statement; do not infer truth from Gate alone. `none` produces no candidates.
7. Report origin counts, item IDs, done filter reasons, manual Gate reviews, blockers and owner decisions.
8. Stop without writes. Output stays on CLI or an explicit path; no required reports directory.
