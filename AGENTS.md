# AGENTS.md

This repository is a multi-host agent-workbench for `codex`, `claude`, and `grok`.

## Source Of Truth

- Use this file as the single instruction source.
- If host-specific entry files are required (`CLAUDE.md`), make them aliases to this file when possible.

## Working Rules

- Keep changes host-neutral unless a host-specific behavior is required.
- Unless the user explicitly specifies a remote branch, branch references mean local branches; for example, "merge into `develop`" means the local `develop` branch.
- Do not mutate user-level host state (`~/.claude`, `~/.codex`, `~/.grok`) unless the task explicitly asks for it.
- Prefer updating skill-link installer logic and docs together so behavior and guidance stay aligned.
- Preserve non-destructive skill linking: skip conflicts and report clearly.
- To expose a standalone skill on a host, use `scripts/link_skill.py` (Windows junction / Unix symlink), not whole-tree `skills/` takeover.
- Keep multi-skill suites in `plugin-marketplace/plugins/<name>/`; install them through each host's native marketplace/plugin commands.

## Skill-Driven Workflow

- Use `audit-agent-setup` when reviewing instruction files or cross-host setup quality.
- Use [setup-workbench](skills/setup-workbench/SKILL.md) after pulling workbench changes or when inspecting, updating, or applying the repository-managed Codex setup.
- Use `find-skills` before introducing external skills.
- When writing PowerShell scripts, use [$powershell-windows](D:\CodeSpace\agent-workbench\skills\powershell-windows\SKILL.md).
- Use `import-third-party-skill` for third-party skill governance:
  - review upstream first
  - install or copy a standalone approved skill into `skills/<name>/` or a plugin-owned skill into `plugin-marketplace/plugins/<plugin>/skills/<name>/`
  - register it in `registry/third-party-skills.md`

## Delegation Workflow

- Use `$dispatcher` for upstream controller scheduling: Topic-first admission, coherent current steps, current batch, dispatch receipt, worker return, Topic lifecycle, and idle.
- Use `$task-queue` only for explicit `task-queue.json`, `depOn`, `get-next-tasks`, or queue CLI requests; it persists Dispatcher-admitted baby steps.
- Use `/impl-package:subagent-driven-development` for the downstream bounded worker method: Topic, dependency class, investigate/implement/fix/verify mode, work/review/test execution lane, lifecycle, and review requirement. Dispatcher and SDD are peer guidance for upstream scheduling and downstream work.
- For independent read-only review, use the thin `reviewer` contract; `do-review` owns review topology and finding closure.

## Implementation Expectations

- When adding a host for skill linking, update:
  - `scripts/link_skill.py` (`HOST_NAMES` / path mapping)
  - `tests/test_link_skill.py`
- Keep user docs in sync:
  - `README.md`
  - `docs/workbench-design/04-install-spec.md`

## Validation

- For standalone Skill additions or changes, stop after two verification layers unless the Owner explicitly requests broader coverage or the results expose a cross-module risk:
  - **L0:** the changed Skill's focused tests, syntax/static checks, and Skill validator.
  - **L1:** tests for directly referenced Skills and adjacent routing/contracts.
- Do not run an undifferentiated full-repository test command after L0 and L1 pass. Keep broader required gates for installer, registry, manifest, or other cross-module changes.
- Run skill-link tests after installer changes:
  - `python -m pytest tests/test_link_skill.py -q`
  - or `powershell -ExecutionPolicy Bypass -File tests/install.ps1` (wrapper)
- If third-party registry logic changed, also run:
  - `powershell -ExecutionPolicy Bypass -File skills/import-third-party-skill/scripts/test-import-third-party-skill.ps1`
- After plugin manifest or marketplace changes, validate both host manifests without installing into user-level host state.
