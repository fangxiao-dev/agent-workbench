# Source Selection

Configuration uses explicit repository-relative paths. Implementation roots contribute their direct child directories. Stable-doc entries may name a file or directory; directory traversal includes Markdown files only. Pending files are listed directly in `records.pending`. Ignore entries use `{path, owner, reason}`；新增排除项不能只给路径。

Audit configured pending entries first. A package with a trustworthy terminal Gate becomes `gap-catching` only when its comparison commit is reachable from configured `targetBranch` and no pending registration mentions the package. Pending-registry items remain readable even when Gate recognition is unavailable; Gate alone never decides truth.

Backfill always records the main worktree Source HEAD/branch/dirty state. Other worktrees are optional research inputs and must not be merged into the source snapshot silently. Missing configured paths are verification failures, not silently empty matches.
