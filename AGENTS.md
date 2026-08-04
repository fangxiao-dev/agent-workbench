# AGENTS.md

This repository is a multi-host agent-workbench for `codex`, `claude`, and `gemini`.

## Source Of Truth

- Use this file as the single instruction source.
- If host-specific entry files are required (`CLAUDE.md`, `GEMINI.md`), make them aliases to this file when possible.

## Working Rules

- Keep changes host-neutral unless a host-specific behavior is required.
- Unless the user explicitly specifies a remote branch, branch references mean local branches; for example, "merge into `develop`" means the local `develop` branch.
- Do not mutate user-level host state (`~/.claude`, `~/.codex`, `~/.gemini`) unless the task explicitly asks for it.
- Prefer updating installer logic and docs together so behavior and guidance stay aligned.
- Preserve non-destructive installation behavior: skip conflicts and report clearly.

## Skill-Driven Workflow

- Use `audit-agent-setup` when reviewing instruction files or cross-host setup quality.
- Use `agent-workbench-manager` for install/reinstall/link-validation tasks.
- Use `find-skills` before introducing external skills.
- When writing PowerShell scripts, use [$powershell-windows](D:\CodeSpace\agent-workbench\skills\powershell-windows\SKILL.md).
- Use `import-third-party-skill` for third-party skill governance:
  - review upstream first
  - install or copy the approved skill into `skills/<name>/` or `skills/<bundle>/<name>/`
  - register it in `registry/third-party-skills.md`
- Use `verify-registry-state` after plugin registry changes.

## Delegation Workflow

- Use `$investigate-before-implement` from `skills/investigate-before-implement/` for bounded investigation or implementation, and `$reviewer` from `skills/reviewer/` for independent read-only review.
- The caller supplies the task-specific objective, scope, worktree, write-set, acceptance, authorization, verification, and output contract; workflow and role definitions do not supply business prompts.

## Implementation Expectations

- When adding a host, update both installers:
  - `install.sh`
  - `install.ps1`
- Keep tests in sync with installer behavior:
  - `tests/install.ps1`
- Keep user docs in sync:
  - `README.md`
  - relevant files under `docs/workbench-design/`

## Validation

- Run installer tests after installer changes:
  - `powershell -ExecutionPolicy Bypass -File tests/install.ps1`
- If third-party registry logic changed, also run:
  - `powershell -ExecutionPolicy Bypass -File skills/import-third-party-skill/scripts/test-import-third-party-skill.ps1`
