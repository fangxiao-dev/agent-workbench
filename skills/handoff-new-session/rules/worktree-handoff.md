# Worktree Handoff Guidance

Use this reference only when the session involves a dedicated feature worktree, multiple worktrees, or branch integration back to trunk.

## Determine The Target Workspace

- Identify the implementation worktree from conversation paths, `git worktree list`, current `pwd`, and changed files.
- Do not assume the main workspace is the implementation target just because the shell is currently there.
- If the user names a feature worktree, place the handoff under that worktree's `docs/exchange/handoffs/` by default.
- State the role of each workspace:
  - implementation worktree
  - main workspace / trunk checkout
  - any coordination-only workspace

## Capture Git State

Record these facts from commands:

- `git status --short --branch`
- `git branch --show-current`
- `git log --oneline -1`
- `git rev-parse HEAD`
- `git rev-parse master` or the configured local trunk branch, if present
- `git rev-parse origin/master` or the relevant remote trunk, if present
- `git rev-list --left-right --count HEAD...master`
- `git rev-list --left-right --count HEAD...origin/master`

If local trunk is ahead of remote trunk, do not call `origin/master` "latest trunk" without qualification. Say which target appears intended and what still needs confirmation.

## Choose The Worktree Scenario

There are two common branch/worktree handoff shapes:

- Existing feature branch/worktree needs to catch up with trunk before it can return.
- Current work is still on trunk, but the next session should move it to another worktree and feature branch.

Classify the situation from `git status --short --branch`, `git branch --show-current`, `git worktree list`, changed paths, and the user's stated next step. If neither common shape fits, state the actual shape and choose the least surprising Git action from the verified state.

## Scenario 1: Feature Branch Needs Trunk First

For a feature worktree that is behind trunk:

1. Protect current feature work first.
   - Prefer a local WIP commit on the feature branch when many files are dirty.
   - A patch outside the worktree is useful as a backup.
   - Avoid reset/checkout operations that can overwrite user or feature changes.
2. Rebase the feature branch/worktree onto the intended trunk, usually from inside the feature worktree:
   - Use `git rebase <local-trunk>` after the feature work is protected and the intended trunk target is confirmed.
   - Resolve conflicts in the feature worktree, then continue with `git rebase --continue`.
   - Use `git rebase --abort` if the conflict set reveals the target or approach was wrong; do not paper over unclear ownership or behavior gaps.
   - Fall back to a merge only when rebase is inappropriate for the repository policy or the user explicitly requests a merge-based integration.
3. Resolve conflicts and investigate gaps in the feature worktree.
4. Run verification in the feature worktree.
5. Only after verification should the branch be considered for merge back to trunk/main workspace.

Do not describe this as "sync the feature branch to master" if that could imply directly changing trunk. Use wording like "rebase `codex/foo` onto local `master` and verify on the feature branch."

## Scenario 2: Trunk Work Should Move To Another Worktree

When the current workspace is already on trunk/main and the next session should continue in a new or existing feature worktree/branch:

1. Inspect the current trunk workspace for relevant uncommitted and untracked files.
   - Treat untracked planning, handoff, design, or case-status documents as potentially important context, especially under `docs/` and `test-cases/`.
   - Do not assume untracked files will follow a new worktree; they usually will not.
2. Ask the user whether to carry strongly related untracked documents forward.
   - Preferred option: commit intentional documentation/context files on trunk before creating or switching worktrees, if they are meant to be shared project state.
   - Alternative option: copy the selected untracked files into the target worktree after it is created or selected, preserving relative paths.
   - Leave unrelated local scratch files behind.
3. After the carry-forward decision, create or switch to the target worktree/branch and verify the expected context files exist there.
4. Continue implementation in the target worktree, not on trunk, unless the user explicitly wants trunk edits.

## Handoff Content To Include

In `Fresh Workspace State`, include:

- The absolute implementation worktree path.
- The main workspace path, if different.
- Which workspace should receive future code changes.
- Whether the main workspace should remain untouched except for coordination.
- The intended trunk target and whether it is local or remote.

In `Open Issues`, include:

- Any route/API/module surfaces introduced on trunk that may need feature changes ported.
- Overlapping files between feature diff and trunk changes.
- Any strongly related untracked documents that may need to be committed on trunk or copied into the target worktree.
- Any live external-system validation that still requires approval.

In the continuation prompt, include:

- The handoff path in the feature worktree.
- The instruction to start in the verified target workspace.
- For Scenario 1, the first action to protect dirty changes before trunk integration.
- For Scenario 2, the instruction to ask about committing or copying strongly related untracked documents before moving to the target worktree.
