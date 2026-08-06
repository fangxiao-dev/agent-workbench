# Audit Runbook

1. Resolve the main worktree and record Source HEAD、branch、dirty state.
2. Validate the repository configuration and target branch.
3. Collect explicit pending files and direct child packages.
4. Separate `pending-registry` from reachable terminal `gap-catching`; record target-unreachable packages without promoting them.
5. Read each source, current code/tests and destination stable docs.
6. Classify each durable statement; do not infer truth from Gate alone.
7. Report origin counts, manual Gate reviews, blockers and owner decisions.
8. Stop without writes.
