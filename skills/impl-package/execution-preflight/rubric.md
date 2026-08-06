# Execution Preflight Rubric

## Confirmed preferences

- Check worktree, branch, HEAD commit, package, write-set, dirty conflicts and external mutation authority.
- Reuse cross-session approval only when its Git commit and current diff preserve the authorized boundary.
- Do not create parallel freshness state.
- READY authorizes one named next action, not push, merge, release or external mutation by implication.
