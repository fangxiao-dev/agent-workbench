# WT Compatibility Validation 2026-03-17

## Scope

Validated the compatibility-oriented edits for:
- `wt-plan`
- `wt-dev`
- `planning-with-files`
- `wt-pm`
- `using-git-worktrees`

## What Was Verified

Static review confirmed that the updated skills now describe:
- trunk detection from repo facts instead of assuming `dev`
- task branch compatibility for both `codex/` and `feat/`
- directory-only task workplans under `plans/workplans/<task_id>/`
- repo-directed setup and regression gates instead of cross-project hardcoded commands
- `using-git-worktrees` defaulting to `create-only`

## What Was Not Verified

Not yet pressure-tested with live subagents:
- trigger quality under ambiguous user prompts
- whether agents consistently reject legacy flat naming drift
- whether a caller will actually honor `create-only` without drifting into setup

## Suggested Next Validation Step

Run the scenarios in:
- `wt-compat-pressure-tests.md`
- `C:\Users\Xiao\.codex\superpowers\skills\using-git-worktrees\pressure-tests.md`

and record pass/fail plus any new rationalizations that appear.

For future workflow-skill contract edits, pair this validation with the `normative contraction review` in `writing-skills` so legacy wording, adjacent skill drift, and helper-script help text are reviewed together.
