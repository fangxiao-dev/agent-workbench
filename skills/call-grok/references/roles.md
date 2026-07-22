# Role presets

Maps `--role` to Grok CLI tool/permission policy and the prompt envelope injected by `scripts/grok_task.py`.

## Shared defaults

| Setting | Value |
|---------|--------|
| `max-run` → `--max-turns` | `15` for `reviewer`; `120` for other roles unless overridden |
| Subagents | Off (`--no-subagents` + `--disallowed-tools Agent`) unless `--allow-subagents` |
| Output | Always `--output-format streaming-json` (wrapper parses it) |

## `explore`

| Item | Value |
|------|--------|
| Tools | `--tools read_file,grep,list_dir,web_search,web_fetch` |
| Always-approve | No |
| Intent | Read-only investigation; paths + findings; no edits |

Use when the parent agent needs a short map of a module, search result, or doc trail.

## `reviewer`

| Item | Value |
|------|--------|
| Tools (default) | `--tools read_file,grep,list_dir` |
| Tools (`--allow-git-shell`) | add `run_terminal_cmd`, `--allow Bash(git *)`, deny `git push*` |
| Always-approve | No |
| Intent | Defect-first review; findings with severity/location/evidence and an explicit PASS/findings/PARTIAL completion state |

Use for PR/diff/plan review. Do not use for applying patches. A parent may attach a free-form context file and a review-round label; they guide scope and continuation without restricting the reviewer's own reasoning. The wrapper records a labelled session and allows resume only for the same round/cwd.

## `implement`

| Item | Value |
|------|--------|
| Tools | Default Grok toolset (minus subagents unless opted in) |
| Always-approve | Yes (`--always-approve`) |
| Intent | Minimal plan-bounded patch; report files + verify + residual risk |

Prefer `--plan-file` and/or `--worktree` for risky changes. Parent must still own merge/push authorization.

## Choosing a role

| Need | Role |
|------|------|
| “What is in X / how does Y work?” | `explore` |
| “What is wrong with this change/plan?” | `reviewer` |
| “Apply this small plan slice” | `implement` |

Never use `implement` for pure review. Never use `explore` when write access is required.
