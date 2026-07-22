---
name: call-grok
description: >
  Wrap the local Grok CLI as a short-task worker for other agents. Use when a parent
  agent (Claude, Codex, Cursor, or Grok) needs to spawn Grok headless for review,
  explore/codebase map, or a plan-bounded small patch; or when the user says
  call-grok, grok-cli-runtime, spawn grok worker, grok reviewer, grok explorer,
  or grok implementer. Prefer this over inventing raw `grok -p` flags. Slash: /call-grok.
---

# call-grok

Spawn a **short-lived Grok CLI worker** via `scripts/grok_task.py`. Do not re-derive headless flags by hand.

## When to use

- Another agent needs Grok for a **bounded** task: review, explore, or small plan-based implement.
- You want bounded `max-run` (→ `--max-turns`) with reviewer rounds defaulting to **15** and **liveness** (stream heartbeats + stall/timeout).

Do **not** use for multi-hour ownership, interactive TUI sessions, or replacing this host’s internal `spawn_subagent` when an in-process subagent is enough.

## Invoke

```powershell
python "$env:USERPROFILE\.grok\skills\call-grok\scripts\grok_task.py" `
  --role <explore|reviewer|implement> `
  --cwd "<repo>" `
  --prompt "<task>"
```

Unix:

```bash
python ~/.grok/skills/call-grok/scripts/grok_task.py \
  --role <explore|reviewer|implement> \
  --cwd "<repo>" \
  --prompt "<task>"
```

Required: `--role` and exactly one of `--prompt` / `--prompt-file`.
Recommended: `--cwd` pointing at the target repo.

## Role selection

| Goal | `--role` |
|------|----------|
| Map code/docs, answer “where/how” | `explore` (read-only tools) |
| Defect-first review of diff/plan/code | `reviewer` (read-only; optional `--allow-git-shell`) |
| Apply a small plan slice | `implement` (**always-approve** writes) |

For implement of non-trivial patches, prefer `--plan-file` and consider `--worktree`.

## Defaults you must know

| Knob | Default |
|------|---------|
| `--max-run` | **15** for `reviewer`; **120** for `explore` and `implement`; override when needed |
| Stall | 180s without stream events |
| Overall timeout | 2400s |
| Heartbeat | stderr every 15s |
| Subagents | off unless `--allow-subagents` |

Full flag table: [references/caller-contract.md](references/caller-contract.md).
Role tool policy: [references/roles.md](references/roles.md).

## Output contract

- **stdout**: one JSON object (`ok`, `status`, `text`, `sessionId`, `num_turns`, `max_run`, `liveness`, `exit_code`, …).
- **stderr**: `[heartbeat]` / `[liveness]` / child diagnostics — use for progress, not as the answer body.

Exit codes: `0` completed · `2` max_turns · `3` stalled · `4` timeout · `5` cancelled · `1` error/preflight.

On `2`/`3`/`4`/`5`, if `sessionId` is present, prefer:

```text
--resume <sessionId> --prompt "Continue and finish only the remaining work."
```

instead of a cold restart when context matters. For a multi-round review, resume only to finish the same interrupted round; start the next round as a fresh worker with the parent's reviewed context. With `--review-round`, the wrapper records the session's round/cwd and rejects a resume from a different round or worktree.

## Safety

- Do not use `implement` for pure review.
- Do not put secrets in the prompt.
- Child success is **not** push/merge/deploy authorization.
- Optional: `--preflight` to require `auth.json` or `XAI_API_KEY` before spending a run.
- `--dry-run` prints the would-be command without calling the model.

## Completion

You have used this skill correctly when:

1. You invoked `scripts/grok_task.py` (not a hand-rolled `grok -p` soup).
2. You chose the role that matches write intent.
3. You returned or acted on the JSON `text` / `status` (and resume when appropriate).
