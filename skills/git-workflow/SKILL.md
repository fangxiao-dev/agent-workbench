---
name: git-workflow
description: >
  Guide safe local Git branch and integration-base workflows. Use this skill whenever
  the user needs to create or switch a task branch, determine the repository's
  integration base, update a local task branch with that base, resolve an in-progress
  merge or rebase conflict, or remove a confirmed merged local branch. Do not use it
  for staging or commits (use git-commit), push/PR work, routine status or log queries,
  Git configuration, or history rewriting and recovery.
metadata:
  tags: git, branches, rebase, merge-conflicts, integration-base
  platforms: Codex, Claude, Gemini
---

# Git Workflow

Manage the local lifecycle of a task branch. Keep the working tree, branch ownership, and integration base explicit so a convenience command does not turn into an unrelated state change.

## Scope

Use this skill for exactly these workflows:

- start a task branch from the repository's intended integration base;
- bring a local task branch up to date with that base;
- continue or abort an already-started merge or rebase after a conflict;
- delete a local branch only after confirming that it was merged and is unused by another worktree.

Do not use this skill for staging, commits, commit messages, push, pull requests, merging a task branch into an integration branch, remote branch deletion, Git configuration, stash operations, `reset`, force-push, reflog recovery, or general Git reference questions. Route commit work to `git-commit`. Handle excluded operations only when the user explicitly asks for them under the repository's general safety rules.

## Required preflight

Before changing branches or history:

1. Read the applicable repository instructions and resolve the intended integration base. Do not assume `main`, `master`, `develop`, or a remote name. If the base is ambiguous, stop and ask.
2. Inspect the current state:

   ```bash
   git status --short
   git branch --show-current
   git worktree list
   ```

3. Treat unrelated or uncommitted changes as a boundary. Do not automatically stash, discard, or carry them across a branch switch. Explain the state and ask the user how to preserve it.
4. Use the repository's existing task-branch naming convention. Do not invent one when instructions do not define it.

## Workflows

### Start a task branch

Use this only from a clean working tree and after resolving `<base-branch>` and the configured remote `<remote>`.

```bash
git switch <base-branch>
git pull --ff-only <remote> <base-branch>
git switch -c <task-branch>
```

`--ff-only` prevents this update step from creating an unexpected merge commit. If it cannot fast-forward, stop and report the divergence rather than choosing a merge or rebase strategy implicitly.

To switch to an existing local task branch, complete the same preflight and then run only:

```bash
git switch <task-branch>
```

Do not fetch, rebase, or otherwise update the branch merely because the user asked to switch to it.

### Update a local task branch from its integration base

Use rebase only for a local task branch that is not shared or published for collaborators to build on. If that ownership is unclear, stop and ask. Fetch first; do not use `--autostash`.

```bash
git fetch <remote>
git rebase <remote>/<base-branch>
```

This skill does not merge a task branch into the integration branch. It only updates the task branch from the base.

### Resolve an in-progress merge or rebase

First identify the active operation with `git status`. Read each conflict before editing it, resolve only the intended content, and stage explicit paths.

```bash
git status
git diff -- <resolved-file>
git add <resolved-file>
git rebase --continue   # during a rebase
git merge --continue    # during a merge
```

Run the repository-required verification before continuing when the conflict changes executable behavior. If the resolution is not reliable, preserve the evidence and return to the pre-operation state instead of guessing:

```bash
git rebase --abort      # during a rebase
git merge --abort       # during a merge
```

### Remove a confirmed merged local branch

Confirm all three conditions before deletion: the target is not the current branch, it appears in `git branch --merged <base-branch>`, and `git worktree list` shows it is not checked out elsewhere. Then use only non-force deletion:

```bash
git branch -d <task-branch>
```

If any condition fails, do not use `-D` or delete a remote branch. Report the condition that prevented cleanup.

## Completion report

Report the resolved integration base and its source, the starting branch state, the workflow performed, whether a conflict was continued or aborted, and the final branch plus `git status --short` result. State any unresolved divergence or user decision separately; do not call the workflow complete when one remains.
