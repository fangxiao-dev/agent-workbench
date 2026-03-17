---
name: wt-dev
description: Use when implementing a tracked WT-PM task inside its dedicated worktree, especially when the repo may use different branch prefixes, setup commands, or verification flows.
user-invocable: true
---

# wt-dev: Task Implementation & Integration

Worktree-side skill for the WT-PM lifecycle. Run this from the task worktree terminal.

Covers:
1. Detect current task from branch name and repo task table
2. Load plan context from the task's workplan directory
3. Run repo-directed environment setup if required
4. Sync trunk and run repo-appropriate regression checks
5. Implement the task with progress tracking
6. Pause for manual testing
7. Re-sync trunk and run final regression checks
8. Update plan evidence
9. Merge back to trunk
10. Mark `DONE` and optionally clean up the worktree

For planning on trunk, use `wt-plan`.

## Core Rule

Do not assume:
- task branches are always `feat/<task_id>-<slug>`
- all repos have standard setup commands
- all repos use the same regression gate

Detect repo conventions first from:
1. `AGENTS.md`
2. `CLAUDE.md`
3. current git branch and worktree list
4. `plans/todo_current.md`

If repo documents conflict with observable repo state, surface the conflict and follow observable repo state.

## Trigger Phrases

- `开工`
- `继续开发`
- `开始`
- `start task`
- `resume wt`
- `wt-dev`
- `继续TC-<id>`

## Phase 0: Auto-Detect Current Task

Goal: detect `task_id`, `slug`, current worktree path, branch prefix, and trunk branch from the actual environment.

### 0a. Read branch and task table

```bash
git branch --show-current
git rev-parse --show-toplevel
```

Read `plans/todo_current.md` and collect known task ids first.

### 0b. Parse branch using repo-known task ids

Accepted branch patterns include:
- `feat/<task_id>-<slug>`
- `codex/<task_id>-<slug>`
- any repo-consistent prefix already visible in `git branch --list` or `git worktree list`

Rules:
- Match the branch against task ids already present in `plans/todo_current.md`
- Prefer the longest matching task id
- Derive `slug` from the remainder after `<task_id>-`

Stop conditions:
- branch name does not contain a repo-known task id
- task id is not in `plans/todo_current.md`
- task status is `DONE`
- task status is `UNPLANNED`

### 0c. Detect trunk branch

Inspect repo docs and git branch list.

Rules:
- Prefer explicitly documented trunk if present
- Otherwise accept `master`, `main`, or `dev`
- If ambiguous, stop and surface the candidates

## Phase 1: Load Plan Context

Goal: restore the complete task context before taking any implementation action.

### 1a. Locate workplan files

Use the task id to locate:
- `plans/workplans/<task_id>/task_plan.md`
- `plans/workplans/<task_id>/findings.md`
- `plans/workplans/<task_id>/progress.md`
- optional `plans/workplans/<task_id>/dev-status.md`

Stop if the current task's three core files cannot be found.

### 1b. Read context

Always read:
- task plan
- findings
- progress

Also read `dev-status` if present.

After reading, summarize:
- task goal
- current phase or last completed step
- blockers or risks

If `dev-status` exists and `status` is not `DONE`, stop and surface the blocker first.

## Phase 2: Environment Initialization

Goal: prepare the current worktree only when repo rules explicitly require task-local setup.

Skip condition:
- progress already records setup as complete
- or repo has no explicit setup steps to run

Detection order:
1. `AGENTS.md`
2. `CLAUDE.md`
3. project setup docs

Rules:
- If repo explicitly says setup belongs in the worktree, do it here
- If repo gives exact setup commands, run only those commands
- If repo gives no explicit setup commands, do not guess generic install commands
- Instead report: `该仓库无标准自动 setup 命令，按项目约定执行`

Stop condition:
- any explicit setup command fails

After successful repo-directed setup, update progress.

## Phase 3: Sync Trunk + Initial Regression Gate

Goal: integrate the latest trunk changes and verify no obvious regression before implementation.

Sync:

```bash
git fetch origin <trunk>
git merge origin/<trunk>
```

Fallback:

```bash
git merge <trunk>
```

If conflicts occur, use the conflict triage protocol below.

### Regression gate selection

Detection order:
1. repo docs with explicit verification commands
2. task plan acceptance criteria
3. existing project test entrypoints related to changed subsystem

Rules:
- Prefer commands explicitly documented by the repo
- If the repo has no standard command, run the most relevant available checks and state what remains unverified
- Never run stack-specific commands copied from another project

Examples of valid outputs:
- `Ran repo-documented verification command: <cmd>`
- `No standard automated verification command found; ran <cmd> as closest relevant check`
- `Manual verification still required in WeChat DevTools`

Stop condition:
- any required gate fails

Update progress with sync and gate results.

## Phase 4: Implementation

Goal: execute the task plan phases in order.

Process:
1. Read the implementation phases from the task plan
2. Implement one phase at a time
3. Update progress after each completed phase
4. Record new discoveries or decisions in findings
5. Keep behavior within the approved task scope

After implementation, run relevant verification again using the repo-directed gate selection above.

### Implementation Escalation Protocol

If any of the following occurs, write `plans/workplans/<task_id>/dev-status.md` and stop:

| 情况 | status 值 |
|------|-----------|
| 测试失败超过 3 次且根因不明 | `BLOCKED` |
| 需求理解有歧义，无法推进 | `NEEDS_CLARIFICATION` |
| 发现改动范围超出 task plan 边界 | `SCOPE_EXCEEDED` |
| 存在无法自主判断的架构方案分歧 | `DECISION_NEEDED` |

Allowed self-resolution:
- syntax errors
- clear unit test failures
- missing dependencies with an explicit project instruction

## Phase 5: Manual Testing Confirmation

Goal: pause before merge so the user can verify the task end-to-end.

Test checklist source:
1. task plan acceptance criteria
2. adjacent regression areas touched by the task
3. repo-specific manual verification requirements

If the repo is UI-heavy or a WeChat Mini Program, explicitly instruct verification in WeChat DevTools.

Do not call the task complete here. At most say:
- implementation complete
- waiting for manual verification

Interpret replies:
- positive reply: continue to Phase 6
- negative or partial reply: stop, collect issues, fix in Phase 4, then return here
- `abort`: stop and record the reason in progress

## Phase 6: Re-sync Trunk + Final Regression Gate

Goal: after manual signoff, re-sync trunk and re-run final checks on the latest integrated state.

Use the same trunk sync logic and regression gate selection from Phase 3.

Stop condition:
- any sync or required gate fails

## Phase 7: Update Plan Files

Goal: persist completion evidence before merge, without prematurely marking `DONE`.

Required updates:
- progress: final execution summary, verification results, timestamp
- findings: final decisions, risks, noteworthy implementation details
- `plans/todo_current.md` must still show `PLANNED` before merge succeeds

Allowed wording after this phase:
- `实现已完成，已通过人工验证，准备 merge`

Forbidden wording:
- `task 已完成`
- `已经 done`

## Phase 8: Merge Back to Trunk

Goal: merge the verified task branch into the detected trunk branch from within the worktree terminal.

### 8a. Find the trunk worktree path

```bash
git worktree list
```

Locate the entry whose branch matches the detected trunk branch.

### 8b. Commit any outstanding task changes

```bash
git status --short
```

If needed, commit task changes before merge.

### 8c. Merge current task branch into trunk

Use the actual current branch name, not a reconstructed `feat/...` string.

```bash
git -C <trunk_path> merge --no-ff <current_branch>
```

Stop condition:
- final re-sync or regression gate has not passed

### 8d. Verify trunk state

```bash
git -C <trunk_path> log --oneline -5
git -C <trunk_path> status --short
```

Confirm the merge commit is present and trunk is clean.

## Phase 9: Mark DONE

Goal: update task state only after verified merge.

Preferred:

```bash
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . set-status --task-id <task_id> --status DONE
```

If tracker output is unavailable, update `plans/todo_current.md` manually while preserving existing table structure.

Stop condition:
- merge failed or has not been verified

## Phase 10: Worktree Cleanup

Goal: optionally remove the task worktree after a clean merge.

If the worktree is clean:

```bash
git worktree remove <current_worktree_path>
git -C <trunk_path> worktree prune
```

Windows fallback:

```bash
git worktree remove --force <current_worktree_path>
cmd /c rmdir /S /Q <current_worktree_path>
git -C <trunk_path> worktree prune
```

Cleanup is optional:
- skip if the worktree is dirty
- skip if the user wants to keep it

## Completion

Output:

```text
✅ wt-dev complete for <task_id>

  Task:     <task description>
  Status:   DONE
  Merged:   <current_branch> → <trunk>
  Cleanup:  worktree removed / kept (reason)
```

Do not append stack-specific smoke-test examples copied from unrelated repos.

## Completion Semantics

Keep these states distinct:

- `implementation complete`
  - code is written
  - relevant automated checks passed
  - manual verification passed
  - merge and `DONE` update have not happened yet

- `task complete`
  - merge back to trunk succeeded
  - `plans/todo_current.md` is marked `DONE`

Only the final completion signal is:

```text
✅ wt-dev complete for <task_id>
```

## Conflict Triage Protocol

If `git merge` reports conflicts, do not auto-resolve globally.

Required diagnostics:

```bash
git status --short
git diff --name-only --diff-filter=U
git diff --merge
```

Decide file by file:

| 文件类型 | 决策 | 理由 |
|----------|------|------|
| 当前任务专属文件 | feature branch | 这是当前任务的成果 |
| 共享基础或集成文件 | trunk | trunk 更接近最新集成状态 |
| Contract / Schema / Public API 文件 | manual | 需要明确审查 breaking change 风险 |

Never use:
- `git merge -X ours`
- `git merge -X theirs`

Report every conflicted file with:
- chosen side: `feature` / `trunk` / `manual`
- one-line reason

## Safety Rules

- 禁止 `git reset --hard` 或 `git checkout -- <path>`
- 任何 commit 或 merge 前必须检查 `git status`
- 不可跳过人工验证暂停
- 不可跳过最终 trunk re-sync
- 标记 `DONE` 前必须完成 merge 验证
- 任务级 workplan 只允许使用 `plans/workplans/<task_id>/` 目录结构
