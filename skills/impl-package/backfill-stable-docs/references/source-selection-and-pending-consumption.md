# Source Selection

Configuration uses explicit repository-relative paths. Implementation roots contribute their direct child directories. Stable-doc entries may name a file or directory; directory traversal includes Markdown files only. `records.pending` is optional and defaults to empty. Ignore entries use `{path, owner, reason}`；新增排除项不能只给路径。

Canonical state locations:

| Location | Role |
| --- | --- |
| Gate Durable Deltas | Source declaration of durable facts, each with a readable `delta-id` |
| `records.pending` / `_pending.md` | Optional human queue; supplementary entry, not gap-catching dedup |
| `records.done` | Processed disposition ledger; gap-catching must consume it |
| Git history | Historical trail |

Gap-catching candidates are item-level and form only when:

1. the package Gate is current and terminal;
2. its comparison commit is reachable from configured `targetBranch`;
3. the Gate Durable Delta line has a stable readable `delta-id` (`none` yields no candidates);
4. the corresponding item is **not** already recorded in `records.done` for that comparison commit.

Pending-registry items remain readable even when Gate recognition is unavailable. Closing or deleting a pending line must not reintroduce the same delta: `records.done` is the sole machine dedup for already-handled items. A new patch / new comparison commit can re-open candidacy for the same delta-id.

Backfill always records the main worktree Source HEAD/branch/dirty state. Other worktrees are optional research inputs and must not be merged into the source snapshot silently. Missing configured implementation/stable-doc paths are verification failures; missing optional pending or a not-yet-created done file is not.
