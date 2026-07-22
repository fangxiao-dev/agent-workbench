# Caller contract

How foreign agents (Claude, Codex, Cursor, parent Grok) should invoke `call-grok`.

## Resolve skill path

```text
%USERPROFILE%\.grok\skills\call-grok\scripts\grok_task.py
# or
$env:USERPROFILE\.grok\skills\call-grok\scripts\grok_task.py
# Unix:
~/.grok/skills/call-grok/scripts/grok_task.py
```

Override binary with `GROK_BIN` if `grok` is not on `PATH`.

## Minimal invoke

```powershell
python "$env:USERPROFILE\.grok\skills\call-grok\scripts\grok_task.py" `
  --role explore `
  --cwd "D:\path\to\repo" `
  --prompt "Summarize the layout of web/app."
```

```bash
python ~/.grok/skills/call-grok/scripts/grok_task.py \
  --role reviewer \
  --cwd /path/to/repo \
  --prompt-file /tmp/review-prompt.txt \
  --review-round 2 \
  --context-file /tmp/review-context.md
```

## Flags (public)

| Flag | Default | Meaning |
|------|---------|---------|
| `--role` | required | `explore` \| `reviewer` \| `implement` |
| `--prompt` / `--prompt-file` | one required | Task text |
| `--cwd` | process cwd | Repo/workdir for Grok |
| `--max-run` | **15 reviewer; 120 otherwise** | Maps to `grok --max-turns` |
| `--model` | host default | Model id |
| `--effort` | host default | Reasoning effort |
| `--plan-file` | none | Inject plan path + content into prompt |
| `--context-file` | none | Inject free-form parent context; it must be readable or the wrapper fails before model execution |
| `--review-round` | none | Reviewer round label; records session round/cwd and rejects cross-round or cross-cwd resume |
| `--rules` | none | Extra rules text |
| `--resume` | none | Resume Grok session id |
| `--worktree [NAME]` | none | Pass through to Grok |
| `--stall-timeout-sec` | 180 | No stream event ⇒ stall |
| `--overall-timeout-sec` | 2400 | Hard wall clock |
| `--heartbeat-sec` | 15 | Stderr heartbeat period |
| `--allow-git-shell` | off | Reviewer: allow git shell reads |
| `--allow-subagents` | off | Allow nested Grok subagents |
| `--preflight` | off | Also require auth.json or `XAI_API_KEY` |
| `--dry-run` | off | Print argv JSON only |
| `--raw-json` | off | Include raw `end` event object |

## Streams

| Stream | Content |
|--------|---------|
| **stdout** | Exactly one JSON object (result envelope) |
| **stderr** | `[call-grok]`, `[heartbeat]`, `[liveness]`, `[grok-stderr]` |

Do not parse heartbeats from stdout. Treat missing heartbeats longer than `stall-timeout + heartbeat` as a likely dead runner if you wrap the process yourself.

## Result envelope

```json
{
  "ok": true,
  "status": "completed",
  "role": "explore",
  "sessionId": "...",
  "num_turns": 4,
  "max_run": 120,
  "text": "...",
  "stopReason": "EndTurn",
  "liveness": {
    "last_event_type": "end",
    "last_event_age_sec": 0.1,
    "heartbeats": 1,
    "stall_timeout_sec": 180,
    "overall_timeout_sec": 2400,
    "elapsed_sec": 22.4
  },
  "usage": {},
  "exit_code": 0,
  "cmd": ["grok", "-p", "<prompt N chars>", "--max-turns", "120", "..."]
}
```

## Exit codes

| Code | `status` | Caller action |
|------|----------|---------------|
| 0 | `completed` | Use `text` |
| 2 | `max_turns` | Partial; resume with `--resume sessionId` if useful |
| 3 | `stalled` | Partial; resume or re-prompt with tighter scope |
| 4 | `timeout` | Partial; raise overall timeout or shrink task |
| 5 | `cancelled` | Partial; do not treat the text as PASS; resume only to finish the same round |
| 1 | `error` / `preflight_failed` | Fix env/auth/prompt; read `error_message` |

## Resume pattern

```powershell
python "...\grok_task.py" `
  --role implement `
  --cwd $repo `
  --resume $sessionId `
  --prompt "Continue from where you left off. Finish the remaining plan items only."
```

For review, keep a resume inside its original `--review-round`. The wrapper writes minimal session-to-round metadata under Grok's local state and rejects a mismatched resume. Start the next review round without `--resume`, carry only the parent-reviewed context forward, and allow the reviewer to inspect the fixed scope afresh.

## Safety

- Prefer `explore` / `reviewer` when writes are not required.
- For `implement`, prefer `--worktree` when isolation matters.
- Do not put secrets in `--prompt`.
- Do not treat a successful child run as authorization to push/merge/deploy; that stays with the outer user/agent policy.
