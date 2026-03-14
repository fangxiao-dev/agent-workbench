---
name: wt-dev
description: Worktree-phase skill for WT-PM workflow. Auto-detects current task from branch name, loads plan context, runs environment init, implements features, pauses for manual testing, runs regression gate, merges back to trunk, then marks DONE — all from within the task worktree terminal.
user-invokable: true
---

# wt-dev: Task Implementation & Integration (Worktree Phase)

Worktree-side skill for the WT-PM lifecycle. Run this from the **task worktree terminal** (branch `feat/<task_id>-<slug>`).

Covers:
1. Auto-detect current task from branch name
2. Load plan context (three-files)
3. Environment initialization (first run only)
4. Sync trunk + regression gate
5. Implementation
6. **[PAUSE]** Wait for manual testing confirmation
7. Final regression gate
8. Update plan files (pre-merge evidence)
9. Merge back to trunk (via `git -C`, no terminal switch needed)
10. Mark DONE + worktree cleanup

For the planning/setup phase (trunk terminal), use `wt-plan`.

## Trigger Phrases

- `开工`
- `继续开发`
- `开始`
- `start task`
- `resume wt`
- `wt-dev`
- `继续TC-<id>`

---

## Phase 0: Auto-Detect Current Task

Goal: identify `task_id`, `slug`, and `plan_id` from the current environment without requiring user input.

```bash
git branch --show-current
```

Expected output format: `feat/<task_id>-<slug>` (e.g. `feat/TC-107-receiver-mapping-ui`)

Parse:
- `task_id` = e.g. `TC-107`
- `slug` = e.g. `receiver-mapping-ui`

Then look up `plan_id`:

```bash
python scripts/plan_tracker.py list
```

Find the row for `task_id`. Extract `plan_id` from that row.

**Stop condition:**
- If branch name does not match `feat/<task_id>-<slug>` pattern: stop and report current branch.
- If `task_id` is not found in `plans/todo_current.md`: stop and report.
- If `task_id` status is `DONE`: stop. Task is already complete. Suggest switching to trunk.
- If `task_id` status is `UNPLANNED`: stop. Run `wt-plan` first on the trunk terminal.

---

## Phase 1: Load Plan Context

Goal: restore full task context before taking any action.

Read all three plan files:

```
plans/workplans/task_plan.<plan_id>.md
plans/workplans/findings.<plan_id>.md
plans/workplans/progress.<plan_id>.md
```

Required: always read these files before proceeding, regardless of whether this is a fresh start or a resume. This is the "load save file" step.

After reading, output a brief context summary:
- Task goal (from task_plan)
- Current phase / last completed step (from progress)
- Any known blockers or risks (from findings)

---

## Phase 2: Environment Initialization (first run only)

Goal: prepare runnable backend and frontend environments in the task worktree.

**Skip this phase if:** `progress.<plan_id>.md` records that environment init was already completed.

Commands:

```bash
uv sync --extra web
corepack enable
corepack prepare pnpm@latest --activate
pnpm --dir frontend install
```

Minimal verification checks:

```bash
uv run python -c "import bills_analysis"
pnpm --dir frontend test
```

**Stop condition:** If any install or verification command fails, stop and report the exact failing command with its error output. Do not proceed to Phase 3.

Update `progress.<plan_id>.md` after successful init.

---

## Phase 3: Sync Trunk + Initial Regression Gate

Goal: integrate latest trunk changes and verify no regressions before implementing.

```bash
git fetch origin <trunk>
git merge origin/<trunk>
```

Fallback if remote is unavailable:

```bash
git merge <trunk>
```

If merge conflict occurs: execute **Conflict Triage Protocol** (see below). Do not auto-resolve.

Regression gate (run in order):

```bash
uv run pytest tests/test_api_schema_v1.py -q
pnpm --dir frontend test
```

Optional:

```bash
uv run pytest tests/test_api_e2e_smoke.py -q
```

**Stop condition:** If any required regression command fails, stop. Do not enter Phase 4 until regression is green.

Update `progress.<plan_id>.md` with sync + regression results.

---

## Phase 4: Implementation

Goal: execute the task plan phases in order.

Process:
1. Read `task_plan.<plan_id>.md` to get the implementation phases.
2. For each phase: implement, then immediately update `progress.<plan_id>.md` marking it complete.
3. Record any discoveries or decisions in `findings.<plan_id>.md` as they arise.
4. Follow API contract rules: never break `v1` frozen fields. Schema changes must be committed before consumer changes.

After all implementation phases are complete, run unit tests relevant to the changes:

```bash
uv run pytest tests/test_api_schema_v1.py -q
pnpm --dir frontend test
```

If tests fail, fix before proceeding to Phase 5.

---

## Phase 5: [PAUSE] Manual Testing Confirmation

Goal: give the human a clear stop point to verify the feature works end-to-end before merging.

Output a **testing checklist** based on the task's acceptance criteria from `task_plan.<plan_id>.md`. Example format:

```
⏸  Implementation complete. Please test the following before I continue:

  Core flows:
  [ ] <acceptance criterion 1>
  [ ] <acceptance criterion 2>

  Adjacent regression check:
  [ ] <related feature that might be affected>

  To continue: reply with your test result (pass / fail / partial).
  To abort:    reply with "abort" and describe what failed.
```

**Wait for user reply.** Do not continue until a response is received.

Interpreting the reply:
- Affirmative (e.g. "通过", "OK", "passed", "没问题", "looks good"): proceed to Phase 6.
- Negative or partial (e.g. "有bug", "failed", "有问题", "不对"): stop, ask user to describe the issue, help fix it, then re-run Phase 4 and return to Phase 5.
- "abort": stop entirely. Update `progress.<plan_id>.md` with abort reason.

---

## Phase 6: Final Regression Gate

Goal: confirm the full test suite is green after implementation + manual test sign-off.

```bash
uv run pytest tests/test_api_schema_v1.py -q
pnpm --dir frontend test
```

**Stop condition:** If any test fails, do not proceed to Phase 7. Fix the failures, re-run, and confirm green before continuing.

---

## Phase 7: Update Plan Files (Pre-Merge)

Goal: persist completion evidence before merging, but do not mark DONE yet.

Required updates:

1. `plans/workplans/progress.<plan_id>.md`: add final execution summary, test results, and completion timestamp.
2. `plans/workplans/findings.<plan_id>.md`: record any final decisions, risks found, or notable implementation details.
3. Ensure `plans/todo_current.md` remains `PLANNED` until merge succeeds.

**Stop condition:** If any required planning file is not updated, Phase 8 is forbidden.

---

## Phase 8: Merge Back to Trunk (no terminal switch required)

Goal: merge validated task branch into trunk from within the worktree terminal.

### 8a. Find trunk worktree path

```bash
git worktree list
```

Identify the trunk worktree path (the entry with branch `dev` or configured `trunk`). This is `<trunk_path>`.

### 8b. Commit any outstanding changes

```bash
git status --short
```

If there are uncommitted changes, stage and commit:

```bash
git add -p   # or stage specific files
git commit -m "<task_id>: <description of final changes>"
```

### 8c. Merge into trunk

```bash
git -C <trunk_path> merge --no-ff feat/<task_id>-<slug>
```

If merge conflict occurs: execute **Conflict Triage Protocol** (see below).

**Stop condition:** If regression gate (Phase 6) was not green, this step is forbidden.

### 8d. Verify merge on trunk

```bash
git -C <trunk_path> log --oneline -5
git -C <trunk_path> status --short
```

Confirm the merge commit appears and trunk is clean.

---

## Phase 9: Mark DONE (Post-Merge Gate)

Goal: update task tracker to `DONE` only after trunk merge succeeds.

Run after Phase 8 merge verification passes:

```bash
python scripts/plan_tracker.py set-status --task-id <task_id> --status DONE --plan-id <plan_id>
```

Verify `plans/todo_current.md` shows `DONE` for `task_id`.

**Stop condition:** If Phase 8 merge failed or is unverified, this step is forbidden.

---

## Phase 10: Worktree Cleanup

Goal: remove the task worktree after a clean merge.

Check worktree is clean:

```bash
git status --short
```

If clean:

```bash
git worktree remove ../wt-<task_id>
git -C <trunk_path> worktree prune
```

Windows fallback (when symlinks or `node_modules` prevent removal):

```bash
git worktree remove --force ../wt-<task_id>
cmd /c rmdir /S /Q ../wt-<task_id>
git -C <trunk_path> worktree prune
```

**Cleanup is optional:** if the worktree is not clean or the user wants to keep it, skip cleanup and report.

---

## Completion

After Phase 10, output:

```
✅ wt-dev complete for <task_id>

  Task:     <task description>
  Status:   DONE
  Merged:   feat/<task_id>-<slug> → <trunk>
  Cleanup:  worktree removed / kept (reason)

Recommended next step: run a manual smoke test on trunk to confirm end-to-end behavior.
  uv run invoice-web-api   (or docker compose up for M2+)
```

---

## Conflict Triage Protocol

When `git merge` reports conflicts, do not auto-resolve.

Required diagnostic steps:

```bash
git status --short
git diff --name-only --diff-filter=U
git diff --merge
```

Decision rules (apply file by file):

| File Type | Decision | Rationale |
|-----------|----------|-----------|
| Task-scoped files (progress/findings for current plan, feature code mainly in this branch) | Prefer feature branch | These are this task's work |
| Shared baseline/integration files (CI config, lock files, shared config not tied to this task) | Prefer trunk | Trunk has the mature version |
| Contracts/schemas/public API files | Manual review required | Breaking changes need explicit rationale |

Forbidden:
- Do not use `git merge -X ours` or `git merge -X theirs` without per-file analysis.
- Do not apply one-shot branch-wide preference.

Required output:
- List each conflicted file.
- State per-file decision: `feature` / `trunk` / `manual`.
- Provide one-line rationale per file before resolving.

---

## Safety Rules

- Never use `git reset --hard` or `git checkout -- <path>`.
- Always check `git status` before any commit or merge.
- Do not merge (Phase 8) unless Phase 6 regression gate is green.
- Do not mark DONE before Phase 8 merge verification passes.
- Do not mark DONE (Phase 9) without updating both `progress` and `findings` files.
- Do not skip Phase 5 (manual testing pause). Automated tests do not replace human verification.
- If task worktree is dirty at Phase 10, skip cleanup rather than force-delete uncommitted work.
