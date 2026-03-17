---
name: wt-plan
description: Use when preparing a tracked WT-PM task on the repository trunk before implementation, especially when the repo may use different trunk branches or task branch prefixes.
user-invocable: true
---

# wt-plan: Task Planning & Worktree Handoff

**REQUIRED SUB-SKILL:** Use `planning-with-files` when creating or updating WT-PM task plans.

Trunk-side skill for the WT-PM lifecycle. Run this from the repository trunk terminal before entering a task worktree.

Covers:
1. Detect repo conventions from repo facts instead of hardcoded defaults
2. Pre-check task status and conflict state
3. Update `plans/todo_current.md`
4. Create or update task plan artifacts
5. Commit plan artifacts on trunk
6. Prepare branch/worktree handoff without doing task-local setup

For the implementation phase inside a task worktree, use `wt-dev`.

## Core Rule

Do not assume:
- trunk is `dev`
- task branches use `feat/`

Always detect actual repo conventions first from:
1. `AGENTS.md`
2. `CLAUDE.md`
3. current git branches and worktrees
4. `plans/todo_current.md`

If repo documents conflict with observable repo state, surface the conflict and follow observable repo state.

## Trigger Phrases

- `确认task`
- `task已确认`
- `写plan`
- `创建wt`
- `plan done create wt`
- `wt-plan`
- `规划并建wt`

## Runtime Parameters

Parse from user request, or derive interactively:

- `task_id` (required): e.g. `TC-107`
- `slug` (required): e.g. `receiver-mapping-ui`
- `trunk` (derived): detected repo trunk branch
- `branch_prefix` (derived): detected task branch prefix such as `codex/` or `feat/`
- `worktree_path` (optional): existing path or recommended path for manual `git worktree add`

Derived:
- `feature_branch = <branch_prefix><task_id>-<slug>`

## Convention Detection Pass

Run this before any workflow phase.

### 1. Detect trunk branch

Inspect in this order:
- `AGENTS.md` / `CLAUDE.md` for explicit trunk wording
- `git branch --list`
- `git symbolic-ref refs/remotes/origin/HEAD` if available

Rules:
- Prefer an explicitly documented trunk branch if it exists
- Otherwise accept `master`, `main`, or `dev`
- If multiple plausible trunk branches exist, stop and surface candidates

### 2. Detect task branch prefix

Inspect:
- `git branch --list`
- `git worktree list`

Rules:
- If active task branches already use a consistent prefix such as `codex/` or `feat/`, reuse it
- If no task branches exist, default to `feat/`
- Preserve the slash if the prefix includes one

### 3. Detect task-local setup boundary

Inspect `AGENTS.md` / `CLAUDE.md`.

If repo instructions say trunk must not perform task-local setup, preserve that rule. `wt-plan` never installs dependencies or prepares local env.

## Phase 0: Pre-Check

### 0a. Confirm current branch is trunk

```bash
git branch --show-current
```

Stop condition:
If current branch is not the detected trunk branch, stop and report:

```text
⚠️  当前分支是 <branch>，不是 trunk（<detected_trunk>）。
wt-plan 必须在 trunk 终端执行。请切换到 trunk 后重试。
```

### 0b. Check task status

Preferred:

```bash
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . list
```

If tracker output is unavailable, fall back to reading `plans/todo_current.md` directly.

Rules by status:

| 状态 | 行动 |
|------|------|
| 不存在 | 正常进入 Phase 1 |
| `UNPLANNED` | 告知任务已存在但未规划，确认是否继续规划 |
| `PLANNED` | 询问用户要续做已有 task workplan 还是重新规划 |
| `DONE` | 停止。告知任务已完成，不需要重新规划 |

If the task already has a live worktree, recommend opening that worktree instead of creating a second one.

## Phase 1: Task Definition Dialogue

Goal: reach shared understanding on task scope before writing anything to disk.

Dialogue checklist:
1. Task goal
2. Scope
3. Acceptance criteria
4. Dependencies
5. `task_id` and `slug`
6. Relevant higher-level plan under `docs/plans/` or equivalent

Stop condition:
If acceptance criteria remain unclear after two rounds, stop and ask the user to clarify first.

## Phase 2: Update `plans/todo_current.md`

Goal: ensure task entry exists with the correct status before creating plan files.

Preferred:

```bash
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . list
```

If the tracker cannot safely manage the repo's observable layout, update `plans/todo_current.md` manually while preserving existing column names and casing.

Rules:
- Add `UNPLANNED` if the task does not exist yet
- Continue if the task is `UNPLANNED`
- Reconfirm if the task is already `PLANNED`
- Stop if the task is `DONE`

## Phase 3: Create Plan Artifacts

Goal: generate structured plan artifacts and bind them to the task.

Before creating or updating files, invoke `planning-with-files` and follow its file-based planning rules.

Preferred:

```bash
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-plan --task-id <task_id>
```

Required artifacts:
- `plans/workplans/<task_id>/task_plan.md`
- `plans/workplans/<task_id>/findings.md`
- `plans/workplans/<task_id>/progress.md`

Populate them with:
- goal
- acceptance criteria
- implementation phases
- dependencies and risks
- initial progress entry

Stop condition:
If the three task files cannot be located after creation, stop and report the missing paths.

## Phase 4: Commit Plan Artifacts to Trunk

Goal: persist the planning snapshot to trunk before worktree creation.

Pre-conditions:
- current branch is the detected trunk branch
- task plan artifacts exist and are non-empty
- `plans/todo_current.md` shows the task as `PLANNED`

Stage only:
- `plans/todo_current.md`
- `plans/workplans/<task_id>/task_plan.md`
- `plans/workplans/<task_id>/findings.md`
- `plans/workplans/<task_id>/progress.md`

Commit message:

```bash
git commit -m "<task_id>: add planning docs for <slug>"
```

Rules:
- Do not stage unrelated changes

## Phase 5: Prepare Branch / Worktree Handoff

Goal: finish trunk-side planning and hand off into a task worktree without doing task-local setup on trunk.

Required outputs:
- detected trunk branch
- feature branch name: `<branch_prefix><task_id>-<slug>`
- existing or recommended worktree path
- clear note that task-local setup belongs in the task worktree, not trunk

Handoff modes to support:
- reuse an existing worktree if the task already owns one
- create a fresh worktree manually with `git worktree add`
- create a fresh worktree through Codex app handoff

Rules:
- never switch trunk into an already-owned task branch
- Codex app handoff is only for a fresh task worktree
- if an existing task worktree is present, tell the user to open it directly

## Completion

Output:

```text
✅ wt-plan complete for <task_id>

  Trunk:    <detected_trunk>
  Branch:   <branch_prefix><task_id>-<slug>
  Worktree: <existing path or recommended path>
Next step: Enter the task worktree, then use wt-dev for implementation and task-local setup.
```

## Safety Rules

- 禁止 `git reset --hard` 或 `git checkout -- <path>`
- 任何 branch/worktree 变更前必须确认 dirty-tree 状态
- trunk 阶段只处理任务上下文和计划文件，不做 task-local install/setup
- 任务级 workplan 只允许使用 `plans/workplans/<task_id>/` 目录结构
- 任何阶段失败时，不继续进入下一阶段
