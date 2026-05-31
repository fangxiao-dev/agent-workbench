---
name: git-commit
description: Make clean git commits from the current workspace, including the common intents "清空工作区", "提交本session的改动", "提交本次改动", "commit工作区", and close Chinese aliases like "把这次改动提交一下" or "帮我分批提交". Use this whenever the user asks to commit changes, clear the worktree into a clean state, batch a session's edits into one or more commits, or write a concise commit message with bullet-point details.
metadata:
  tags: git, commit, workspace-cleanup, powerShell, conventional-commits
---

# Git Commit

Use this skill to turn the current workspace state into one or more intentional commits. Always evaluate batching before staging anything.

Common user phrasings that should trigger this skill:

- `清空工作区`
- `提交本session的改动`
- `提交本次改动`
- `commit工作区`
- `把这次改动提交一下`
- `帮我分批提交`
- `把当前改动收口成 commit`
- `整理一下 git 提交`

## Trigger Keywords

Use this skill when the request includes any of the following:

- git commit
- commit
- commit workspace
- clean workspace
- clean worktree
- clear workspace
- clear worktree
- submit this session
- submit changes
- stage and commit
- make a commit
- clear the worktree
- 清空工作区
- 提交本session的改动
- 提交本次改动
- commit工作区
- 把这次改动提交一下
- 帮我分批提交
- 把当前改动收口成 commit
- 整理一下 git 提交

## Core intent

Decide which of these two modes the user means before you stage anything:

- `清空工作区`: finish by leaving the workspace clean. Commit all intended changes in the repo, but still split unrelated topics into separate commits before verifying that `git status --short` is empty.
- `提交本session的改动` / `提交本次改动` / `commit工作区`: commit only the changes that belong to the current session, and split them into multiple commits when the actual changes naturally fall into separate topics. Leave unrelated pre-existing edits alone and report them separately if they remain dirty.

If the user does not say which one they want, prefer `提交本session的改动` because it is safer in a shared or dirty worktree.

## Workflow

1. Inspect `git status --short` and `git diff --stat` first.
2. Separate session changes from unrelated existing edits.
3. Before staging or committing, check repository instructions for test-design requirements:
   - Read the applicable `AGENTS.md` files for the current repository or workspace scope.
   - If `AGENTS.md` names a test case entry, test-layering plan, verification matrix, or other project-specific test design, read that plan before choosing verification.
   - Map the intended commit scope to the required extra tests from that plan.
   - Run the extra tests required for the intended commit scope before committing, unless the plan explicitly says no case is required.
   - If a required test cannot run, report the blocker and do not claim the commit is fully verified.
   - Include the relevant verification outcome in the commit body or final report when it materially explains the commit.
4. Create a batching decision before staging:
   - Group changes by topic, not by convenience.
   - A topic is a coherent review unit: feature/fix, tests for that fix, docs for that change, or generated output required by that change.
   - Keep unrelated generated artifacts, local agent artifacts, data updates, code fixes, and documentation updates in separate commits unless one cannot make sense without the other.
   - If there are 2+ topics, make 2+ commits. Do not collapse them into one commit just because the user asked to commit "all" or "the workspace".
   - If making one commit despite multiple-looking file groups, state the reason before staging.
5. Stage only the intended files. Prefer explicit paths or `git add -p` when a file mixes unrelated changes.
6. Write a commit message with:
   - a short conventional title
   - a blank line
   - 2 to 5 bullet points that summarize what changed and why
7. Commit.
8. Verify the result with `git status --short`.

## Commit message shape

Use a title that stays compact and readable:

```text
type(scope): short summary

- what changed
- why it changed
- any important scope boundary or verification note
```

Prefer conventional commit prefixes such as `feat`, `fix`, `docs`, `refactor`, `test`, or `chore`.

## PowerShell newline rule

PowerShell does not treat `\n` as a newline inside normal double-quoted strings. Do not build commit bodies with literal `\n`.

Use one of these instead:

```powershell
$body = @"
- item 1
- item 2
- item 3
"@

git commit -m "feat(scope): short title" -m $body
```

or:

```powershell
$body = @(
  "- item 1"
  "- item 2"
  "- item 3"
) -join [Environment]::NewLine

git commit -m "feat(scope): short title" -m $body
```

If the user wants an even terser body, keep the bullets but drop filler prose. The point is to make the commit log scannable, not verbose.

## Staging rules

- Do not use `git add .` blindly if the worktree contains unrelated changes.
- Stage one topic at a time, commit it, then re-check `git status --short` before staging the next topic.
- Do not include generated, temporary, or user-owned unrelated edits unless the user explicitly asked to clear the whole workspace.
- If a file contains both session and non-session changes, stage the hunks separately.

## Cleanup rule

`清空工作区` means "finish the session with a clean worktree", not "discard code". Never use destructive cleanup commands unless the user explicitly asks to throw changes away.

If the workspace cannot be made clean because of unresolved unrelated edits, say exactly which files remain and why.
