# Caller contract

`call-grok` is a thin, short-lived Grok CLI executor. The caller supplies the
complete task prompt and any desired Grok configuration.

## Minimal invocation

```powershell
python "D:\CodeSpace\agent-workbench\skills\call-grok\scripts\grok_task.py" `
  --cwd "D:\path\to\repo" `
  --prompt "Summarize this change."
```

Provide exactly one of `--prompt` or `--prompt-file`.

## Public flags

| Flag | Default | Meaning |
|---|---:|---|
| `--cwd` | process cwd | Working directory for Grok |
| `--prompt` / `--prompt-file` | required | Caller-owned task text |
| `--max-run` | 100 | Maps to Grok `--max-turns` |
| `--model` | CLI default | Model id |
| `--effort` | CLI default | Reasoning effort |
| `--tools` | `read_file,search_replace,list_dir,grep,run_terminal_cmd,todo_write` | Grok CLI tool allowlist; explicit values replace the default |
| `--allow` / `--deny` | unset | Repeatable Grok permission rules |
| `--always-approve` | off | Pass through write approval |
| `--no-subagents` | off | Disable Grok subagents |
| `--worktree [NAME]` | unset | Pass through Grok worktree option |
| `--rules` | unset | Pass through Grok rules |
| `--stall-timeout-sec` | 600 (max 1800) | No stream event before declaring a stall |
| `--overall-timeout-sec` | 600 (max 1800) | Hard wall-clock timeout |
| `--heartbeat-sec` | 15 | Stderr heartbeat interval |
| `--preflight` | off | Also require auth before model execution |
| `--dry-run` | off | Return the redacted would-be command in `text` |

No prompt envelope, permission policy, or subagent policy is injected by
default. The default tool allowlist is the value shown above; pass an explicit
`--tools` value when a task needs a narrower or different set. Put task-specific
instructions and context directly in the prompt or prompt file.

## Output contract

stdout is exactly one JSON object:

```json
{
  "ok": true,
  "status": "completed",
  "text": "Grok's final response",
  "usage": {},
  "exit_code": 0,
  "error": null
}
```

`error`, when present, has stable `code` and diagnostic `message`. Statuses are
`completed`, `dry_run`, `max_turns`, `stalled`, `timeout`, `cancelled`,
`preflight_failed`, or `error`. stderr is reserved for `[heartbeat]`,
`[liveness]`, and child diagnostics.

Each call starts a fresh Grok process. The wrapper does not resume sessions;
callers that need previous context must include it in a new prompt.

Timeouts default to 600 seconds (10 minutes). Callers may increase either
timeout for a larger task, but the runner rejects values above 1800 seconds (30
minutes). `--max-run` is a Grok turn limit, not a seconds-based timeout.
