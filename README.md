# agent-workbench

Personal agent workflow assets and bootstrap tooling for Codex, Claude, and Gemini.

## What v1 includes

- A unified first-party skill: `agent-workbench-manager`
- Personal-use bootstrap CLI with `apply`, `verify`, `pull`, and `push`
- Project-local and user-global skill installation
- Smoke verification for rendered templates, installed skills, and `plan_tracker.py`
- First-party assets that can be pulled into a business repository and pushed back to the tool repo

## Recommended workflow

1. Manually clone your personal `agent-workbench` repo to a local path.
2. Add `agent_assets.yaml` to the business repository.
3. Sync the `agent-workbench-manager` skill into the project or your global skill directory.
4. Use natural language to drive management actions, for example:
   - ???????? agent assets ????
   - ??????????? assets?
   - ?????????? skills ???????

The CLI remains available as the execution layer and fallback:

```bash
python -m agent_workbench.cli apply --target ../my-project
python -m agent_workbench.cli verify --target ../my-project
python -m agent_workbench.cli pull --target ../my-project
python -m agent_workbench.cli push --target ../my-project --skill wt-dev
```

## Consumer manifest

```yaml
source_repo: ../agent-workbench
agents:
  - codex
  - claude
skills:
  - agent-workbench-manager
  - planning-with-files
  - name: wt-plan
    scope: global
templates:
  - codex
  - claude
verify:
  - templates
  - project_skills
  - global_skills
  - plan_tracker
```

Skill defaults:
- `scope`: `project`
- `mode`: `sync`

Installation behavior:
- Project-level skills are always installed to `.agents/skills/`
- If `claude` is enabled, the same project-level skills are also installed to `.claude/skills/`
- Global skills are installed to `~/.claude/skills/`, `~/.codex/skills/`, or `~/.gemini/skills/` depending on enabled agents

Notes:
- `task_prefix` is optional and only matters if your project wants to reuse task-tracker conventions.
- `push` no longer reads a `pushable` flag; you choose what to push by passing `--skill <name>`.
