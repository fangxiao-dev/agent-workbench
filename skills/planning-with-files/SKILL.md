---
name: planning-with-files
version: "2.10.0"
description: Implements Manus-style file-based planning for complex tasks, especially in repos that track tasks in plans/todo_current.md and store workplans in per-task directories under plans/workplans.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebFetch
  - WebSearch
hooks:
  PreToolUse:
    - matcher: "Write|Edit|Bash|Read|Glob|Grep"
      hooks:
        - type: command
          command: "python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . view-active 2>/dev/null || true"
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "echo '[planning-with-files] File updated. Sync task status in plans/todo_current.md when phase changes.'"
  Stop:
    - hooks:
        - type: command
          command: |
            SCRIPT_DIR="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/planning-with-files}/scripts"

            IS_WINDOWS=0
            if [ "${OS-}" = "Windows_NT" ]; then
              IS_WINDOWS=1
            else
              UNAME_S="$(uname -s 2>/dev/null || echo '')"
              case "$UNAME_S" in
                CYGWIN*|MINGW*|MSYS*) IS_WINDOWS=1 ;;
              esac
            fi

            if [ "$IS_WINDOWS" -eq 1 ]; then
              if command -v pwsh >/dev/null 2>&1; then
                pwsh -ExecutionPolicy Bypass -File "$SCRIPT_DIR/check-complete.ps1" 2>/dev/null ||
                powershell -ExecutionPolicy Bypass -File "$SCRIPT_DIR/check-complete.ps1" 2>/dev/null ||
                sh "$SCRIPT_DIR/check-complete.sh"
              else
                powershell -ExecutionPolicy Bypass -File "$SCRIPT_DIR/check-complete.ps1" 2>/dev/null ||
                sh "$SCRIPT_DIR/check-complete.sh"
              fi
            else
              sh "$SCRIPT_DIR/check-complete.sh"
            fi
---

# Planning with Files

Work like Manus: Use persistent markdown files as your "working memory on disk."

## Project Customization

This skill is often used inside WT-PM-style repositories and assumes one directory-based workplan layout.

Common repo facts:

- Task source of truth is often `plans/todo_current.md`
- Status lifecycle is often `UNPLANNED -> PLANNED -> DONE`
- Workplan files live under `plans/workplans/<task_id>/`
- Each task directory contains `task_plan.md`, `findings.md`, and `progress.md`

Use these fast trigger phrases:

1. `/planning-with-files 规划还未规划的task`
   - Read all unfinished tasks (`UNPLANNED + PLANNED`).
   - If user specifies scope, use that scope directly.
   - If scope is not specified, agent auto-selects one task using dependency/risk/conflict/impact heuristics and records rationale in that task's `findings.md`.
   - Update the selected task to `PLANNED` in `plans/todo_current.md`.
2. `/planning-with-files 读取当前未完成的task progress继续实现`
   - Continue one `PLANNED` task.
   - If no explicit task is given, pick the first `PLANNED` task in `plans/todo_current.md`.

Recommended local commands:

```powershell
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . list
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-plan
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-resume
```

## FIRST: Check for Previous Session (v2.2.0)

**Before starting work**, check for unsynced context from a previous session:

```bash
# Linux/macOS
$(command -v python3 || command -v python) ${CLAUDE_PLUGIN_ROOT}/scripts/session-catchup.py "$(pwd)"
```

```powershell
# Windows PowerShell
& (Get-Command python -ErrorAction SilentlyContinue).Source "$env:USERPROFILE\.claude\skills\planning-with-files\scripts\session-catchup.py" (Get-Location)
```

If catchup report shows unsynced context:
1. Run `git diff --stat` to see actual code changes
2. Read current planning files
3. Update planning files based on catchup + git diff
4. Then proceed with task

## Important: Where Files Go

- **Templates** are in `${CLAUDE_PLUGIN_ROOT}/templates/`
- **Your planning files** go in **`plans/workplans/`** for this project

| Location | What Goes There |
|----------|-----------------|
| Skill directory (`${CLAUDE_PLUGIN_ROOT}/`) | Templates, scripts, reference docs |
| Your project directory | Task workplan directories under `plans/workplans/` |

## Quick Start

Before ANY complex task:

1. Ensure the repo uses `plans/workplans/<task_id>/` directories for task workplans
2. Use `python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-plan --task-id <task_id>` to create the task directory and three files
3. Ensure the current task's `task_plan.md`, `findings.md`, and `progress.md` exist under `plans/workplans/<task_id>/`
4. Keep `plans/todo_current.md` in sync (`PLANNED` / `DONE` states)
5. **Re-read plan before decisions** — Refreshes goals in attention window
6. **Update after each phase** — Mark complete, log errors

> **Note:** Planning files go in `plans/workplans/` in your project, not the skill installation folder.

## The Core Pattern

```
Context Window = RAM (volatile, limited)
Filesystem = Disk (persistent, unlimited)

→ Anything important gets written to disk.
```

## File Purposes

| File | Purpose | When to Update |
|------|---------|----------------|
| `plans/workplans/<task_id>/task_plan.md` | Phases, progress, decisions | After each phase |
| `plans/workplans/<task_id>/findings.md` | Research, discoveries | After ANY discovery |
| `plans/workplans/<task_id>/progress.md` | Session log, test results | Throughout session |
| `plans/todo_current.md` | Task lifecycle | On every status change |

## Critical Rules

### 1. Create Plan First
Never start a complex task without a `task_id` and `plans/workplans/<task_id>/task_plan.md`. Non-negotiable.

### 2. The 2-Action Rule
> "After every 2 view/browser/search operations, IMMEDIATELY save key findings to text files."

This prevents visual/multimodal information from being lost.

### 3. Read Before Decide
Before major decisions, read the plan file. This keeps goals in your attention window.

### 4. Update After Act
After completing any phase:
- Mark phase status: `in_progress` → `complete`
- Log any errors encountered
- Note files created/modified

### 5. Log ALL Errors
Every error goes in the plan file. This builds knowledge and prevents repetition.

```markdown
## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| FileNotFoundError | 1 | Created default config |
| API timeout | 2 | Added retry logic |
```

### 6. Never Repeat Failures
```
if action_failed:
    next_action != same_action
```
Track what you tried. Mutate the approach.

## The 3-Strike Error Protocol

```
ATTEMPT 1: Diagnose & Fix
  → Read error carefully
  → Identify root cause
  → Apply targeted fix

ATTEMPT 2: Alternative Approach
  → Same error? Try different method
  → Different tool? Different library?
  → NEVER repeat exact same failing action

ATTEMPT 3: Broader Rethink
  → Question assumptions
  → Search for solutions
  → Consider updating the plan

AFTER 3 FAILURES: Escalate to User
  → Explain what you tried
  → Share the specific error
  → Ask for guidance
```

## Read vs Write Decision Matrix

| Situation | Action | Reason |
|-----------|--------|--------|
| Just wrote a file | DON'T read | Content still in context |
| Viewed image/PDF | Write findings NOW | Multimodal → text before lost |
| Browser returned data | Write to file | Screenshots don't persist |
| Starting new phase | Read `plans/workplans/<task_id>/task_plan.md` and `findings.md` | Re-orient if context stale |
| Error occurred | Read relevant file | Need current state to fix |
| Resuming after gap | Read the task row in `plans/todo_current.md` plus that task's workplan directory | Recover state |

## The 5-Question Reboot Test

If you can answer these, your context management is solid:

| Question | Answer Source |
|----------|---------------|
| Where am I? | Current phase in `plans/workplans/<task_id>/task_plan.md` |
| Where am I going? | Remaining phases |
| What's the goal? | Goal statement in the plan |
| What have I learned? | `plans/workplans/<task_id>/findings.md` |
| What have I done? | `plans/workplans/<task_id>/progress.md` |

## When to Use This Pattern

**Use for:**
- Multi-step tasks (3+ steps)
- Research tasks
- Building/creating projects
- Tasks spanning many tool calls
- Anything requiring organization

**Skip for:**
- Simple questions
- Single-file edits
- Quick lookups

## Templates

Copy these templates to start:

- [templates/task_plan.md](templates/task_plan.md) — Phase tracking
- [templates/findings.md](templates/findings.md) — Research storage
- [templates/progress.md](templates/progress.md) — Session logging

## Scripts

Helper scripts for automation:

- `python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . list` — Show current task table
- `python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-plan --task-id <task_id>` — Create one task workplan
- `python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-resume` — Pick one PLANNED task to continue
- `scripts/session-catchup.py` — Recover context from previous session (v2.2.0)

## Advanced Topics

- **Manus Principles:** See [reference.md](reference.md)
- **Real Examples:** See [examples.md](examples.md)

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Use TodoWrite for persistence | Use `plans/todo_current.md` + `plans/workplans/<task_id>/` |
| State goals once and forget | Re-read active plan files before decisions |
| Hide errors and retry silently | Log errors to plan file |
| Stuff everything in context | Store large content in files |
| Start executing immediately | Create plan file FIRST |
| Repeat failed actions | Track attempts, mutate approach |
| Create files in skill directory | Create files in your project (`plans/workplans/`) |
