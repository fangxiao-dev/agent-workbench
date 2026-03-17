# WT Compatibility Pressure Tests

Use these scenarios to pressure-test `wt-pm`, `wt-plan`, `wt-dev`, and `planning-with-files` after directory-only workplan edits.

When these tests accompany a workflow-skill contract change, also run the `normative contraction review` described in `writing-skills` so the skill chain, references, scripts, and validation notes are checked together.

## Goal

Verify that the workflow reads repo facts first and does not regress to the old assumptions:
- trunk is always `dev`
- task branches always use `feat/`
- all repos can invent their own workplan layout
- every repo has standard setup and regression commands

## Scenario 1: Master trunk + codex branch prefix

Prompt:

```text
开始一个新任务 LR-009，仓库当前 trunk 是 master。之前已有 worktree 和分支都用 codex/LR-xxx-... 的格式。请帮我走 WT-PM。
```

Expected behavior:
- routes to `wt-plan`
- treats `master` as valid trunk
- proposes branch name with `codex/` prefix
- does not tell the user to switch to `dev`

Failure signal:
- any instruction that says trunk must be `dev`
- any forced output of `feat/LR-009-...`

## Scenario 2: Directory-only workplan consistency

Prompt:

```text
wt-plan。请按 WT-PM 规范为 LR-011 创建任务计划，并说明 planning-with-files 应该把文件放在哪里。
```

Expected behavior:
- requires `plans/workplans/LR-011/`
- requires `task_plan.md` / `findings.md` / `progress.md`
- uses the same directory wording as `planning-with-files`

Failure signal:
- says layout can be detected or chosen dynamically
- gives a file pattern based on `plan_id`

## Scenario 3: Reject legacy flat naming drift

Prompt:

```text
wt-plan。这个仓库以前有人用 `task_plan.20260316-1404.md` 这种扁平命名。现在怎么办？
```

Expected behavior:
- acknowledges the legacy files may exist
- directs the user back to `plans/workplans/<task_id>/`
- does not extend WT-PM to keep supporting legacy plan-id naming

Failure signal:
- proposes continuing with flat naming
- presents flat naming as a supported option

## Scenario 4: wt-dev in a WeChat Mini Program repo

Prompt:

```text
开工。当前分支是 codex/LR-002-feature-module-home。仓库没有 uv / pnpm frontend 这些标准命令，验证主要靠 WeChat DevTools。
```

Expected behavior:
- parses `LR-002` from `codex/...`
- loads the correct workplan from `plans/workplans/LR-002/`
- does not run unrelated Python/web stack commands by default
- requires manual verification in WeChat DevTools

Failure signal:
- tries `uv sync`, `uv run pytest`, or `pnpm --dir frontend test` without repo justification
- rejects the branch because it is not `feat/...`

## Scenario 5: Existing worktree already owns the branch

Prompt:

```text
wt-pm。LR-010 已经有 worktree 目录，分支也已经被那个 worktree 占用。我现在想继续做这个任务。
```

Expected behavior:
- instructs the user to open the existing worktree
- does not propose a second handoff or duplicate worktree

Failure signal:
- tells the user to checkout the branch in trunk
- tells the user to create another worktree for the same branch

## Scenario 6: planning-with-files and wt-plan wording match

Prompt:

```text
/planning-with-files 规划还未规划的task
```

Expected behavior:
- requires `plans/workplans/<task_id>/task_plan.md`
- requires `plans/workplans/<task_id>/findings.md`
- requires `plans/workplans/<task_id>/progress.md`
- does not mention layout detection

Failure signal:
- describes a different path contract from `wt-plan`
- refers to a runtime-chosen layout or alternative file naming scheme

## Static Checks For This Iteration

Use these quick checks after editing the skills:

```powershell
Get-ChildItem -Recurse -File D:\CodeSpace\agent-workbench\skills\wt-plan,D:\CodeSpace\agent-workbench\skills\wt-dev,D:\CodeSpace\agent-workbench\skills\planning-with-files,D:\CodeSpace\agent-workbench\skills\wt-pm | Select-String -Pattern "trunk \\(`dev`\\)|feat/<task_id>|plans/workplans/<task_id>/task_plan.md|uv run pytest tests/test_api_schema_v1.py|pnpm --dir frontend test"
```

Expected result:
- no hardcoded workflow assumptions remain unless they appear only as legacy examples or negative examples
- no supported flat-layout wording remains
