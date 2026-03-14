---
name: wt-plan
description: Trunk-phase skill for WT-PM workflow. Handles task definition dialogue, plan file creation, plan commit to trunk, worktree creation, and config sync. Run this on the trunk (dev) branch before switching to the task worktree.
user-invokable: true
---

# wt-plan: Task Planning & Worktree Setup (Trunk Phase)

Trunk-side skill for the WT-PM lifecycle. Run this from the **trunk (`dev`) branch terminal**.

Covers:
1. Multi-round task definition dialogue
2. Update `plans/todo_current.md`
3. Create plan three-files (via `quick-plan`)
4. Commit plan artifacts to trunk
5. Create task worktree + sync shared config

For the implementation phase (worktree terminal), use `wt-dev`.

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
- `trunk` (optional, default: `dev`)
- `worktree_path` (optional, default: `../wt-<task_id>`)
- `apply_sync` (optional, default: `true`)

Derived:
- `feature_branch = feat/<task_id>-<slug>`
- `plan_id`: from `quick-plan` output (format: `YYYYMMDD-HHmm`)

---

## Phase 0: Task Definition Dialogue (pre-commit gate)

Goal: reach shared understanding on task scope before writing anything to disk.

**When to run:**
- If the user says "确认task" or equivalent trigger without a clear task description already in context, enter dialogue mode.
- If the user's request already contains a clear task description, `task_id`, and `slug`, skip to Phase 1.

**Dialogue checklist (ask the user until all are answered):**

1. Task goal: What problem does this task solve?
2. Scope: Frontend only / backend only / full-stack?
3. Acceptance criteria: How do we know it's done?
4. Dependencies: Blocked by or blocks other tasks?
5. `task_id` and `slug`: Confirm or propose.

Once all five are clear, announce: "Task definition confirmed. Proceeding to plan creation."

**Stop condition:** If user cannot answer acceptance criteria after two rounds, stop and ask them to clarify before continuing.

---

## Phase 1: Update `plans/todo_current.md`

Goal: ensure task entry exists with correct status before creating plan files.

```bash
python scripts/plan_tracker.py list
```

Rules:
- If `task_id` does not exist: add `UNPLANNED` entry manually or via script, then proceed.
- If `task_id` exists with `UNPLANNED`: proceed to Phase 2.
- If `task_id` exists with `PLANNED`: confirm with user whether to create a new plan or resume the existing one. If resuming, switch to `wt-dev` instead.
- If `task_id` exists with `DONE`: stop. Task is already complete.

---

## Phase 2: Create Plan Three-Files

Goal: generate structured plan artifacts and bind them to the task.

```bash
python scripts/plan_tracker.py quick-plan --task-ids <task_id>
```

This command:
- Creates `plans/workplans/task_plan.<plan_id>.md`
- Creates `plans/workplans/findings.<plan_id>.md`
- Creates `plans/workplans/progress.<plan_id>.md`
- Updates `plans/todo_current.md` status to `PLANNED` with `plan_id`

After running, verify three files exist under `plans/workplans/` and `todo_current.md` shows `PLANNED`.

Fill in the plan files with content from the Phase 0 dialogue:
- `task_plan.<plan_id>.md`: goal, acceptance criteria, implementation phases
- `findings.<plan_id>.md`: scope decision rationale, known dependencies, risks
- `progress.<plan_id>.md`: initial entry noting plan created, start timestamp

**Stop condition:** If any file is missing after `quick-plan`, stop and report.

---

## Phase 3: Commit Plan Artifacts to Trunk

Goal: persist planning snapshot to trunk before worktree creation.

Pre-conditions (must all be true):
- Currently on trunk branch (`dev` by default).
- All three plan files exist and are non-empty.
- `plans/todo_current.md` shows `PLANNED` status for `task_id`.

Commands:

```bash
git add plans/todo_current.md \
        plans/workplans/task_plan.<plan_id>.md \
        plans/workplans/findings.<plan_id>.md \
        plans/workplans/progress.<plan_id>.md
git commit -m "<task_id>: add planning docs for <slug>"
```

Rules:
- Stage only the four listed paths. Do not include unrelated changes.
- If any file is missing or not staged, stop and list the missing items.
- After successful commit, proceed to Phase 4.

---

## Phase 4: Create Task Worktree + Sync Config

Goal: create an isolated task branch/worktree and sync shared config files.

### 4a. Check if worktree already exists

```bash
git worktree list
```

- If `../wt-<task_id>` already exists: skip `git worktree add`, go straight to sync.
- If not: run `git worktree add`.

### 4b. Create worktree (if new)

```bash
git worktree add -b feat/<task_id>-<slug> ../wt-<task_id> <trunk>
```

Rules:
- Default path: `../wt-<task_id>` (sibling directory, visible).
- Do not create under hidden folders (e.g. `.worktrees/`).
- If branch/worktree creation fails due to permission/sandbox lock, stop and report.
- Do not change the `feat/<task_id>-<slug>` naming convention.

### 4c. Sync shared config (dry-run then apply)

Run from trunk worktree root (the current directory — sync direction is **current → other**):

```bash
bash scripts/sync_worktree_config.sh
bash scripts/sync_worktree_config.sh --apply
```

Windows fallback (when `bash` is unavailable):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_worktree_config.ps1
powershell -ExecutionPolicy Bypass -File scripts/sync_worktree_config.ps1 -Apply
```

Rules:
- Dry-run is mandatory before apply. Never skip dry-run.
- If both `.sh` and `.ps1` paths fail, stop immediately. Do not continue.
- If `apply_sync=false`, skip apply and report explicitly.

### 4d. Post-check (mandatory)

Verify the following exist in the task worktree (`../wt-<task_id>`):
- `.agents/` directory (report file count)
- `.claude/rules/` directory (report file count)
- `.claude/skills/` directory (report file count)
- `.env` file (verify content hash matches trunk)
- `frontend/.env.local` file (verify content hash matches trunk)

**Output summary (required):**
- Created branch: `feat/<task_id>-<slug>`
- Created worktree path: `../wt-<task_id>`
- Sync method: `bash` or `powershell`
- Sync dry-run result
- Sync apply result (or `skipped`)
- Post-check result: each item ✅ or ❌ with detail

---

## Completion

After Phase 4 passes, output:

```
✅ wt-plan complete for <task_id>

  Branch:   feat/<task_id>-<slug>
  Worktree: ../wt-<task_id>
  Plan ID:  <plan_id>

Next step: Open a terminal in ../wt-<task_id> and say "开工" to start wt-dev.
```

---

## Safety Rules

- Never use `git reset --hard` or `git checkout -- <path>`.
- Always verify dirty-tree before any branch/worktree mutation.
- Only stage the four plan-related paths in Phase 3.
- Do not proceed to the next phase if any phase fails.
