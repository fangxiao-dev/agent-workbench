# Caller contract

`call-grok` is a thin, short-lived Grok CLI executor. The caller supplies the
complete task prompt and any desired Grok configuration.

## Minimal invocation

```powershell
python "D:\CodeSpace\agent-workbench\skills\call-grok\scripts\grok_task.py" `
  --cwd "D:\path\to\repo" `
  --prompt-file "<unique-temp-prompt-file>"
```

Provide exactly one of `--prompt-file` or `--prompt`. The default caller flow
creates one invocation-unique UTF-8 temporary file and passes it with
`--prompt-file`. Do not reuse that file across concurrent calls; remove it only
after the task has finished and its JSON result has been read.

`--prompt` remains supported for a direct foreground invocation with a short,
single-line prompt when the caller can reliably preserve quoting. Do not pass a
multiline `--prompt` through Windows `Start-Process -ArgumentList`: PowerShell
may split it into extra process arguments before `grok_task.py` can parse it.

## Public flags

| Flag | Default | Meaning |
|---|---:|---|
| `--cwd` | process cwd | Working directory for Grok |
| `--prompt-file` / `--prompt` | required | Caller-owned task text; unique temporary `--prompt-file` is the default transport |
| `--max-run` | 100 | Maps to Grok `--max-turns` |
| `--model` | CLI default | Model id |
| `--effort` | CLI default | Reasoning effort |
| `--tools` | `grep,list_dir,run_terminal_cmd,read_file,search_replace` | Grok CLI tool allowlist; explicit values replace the default. `todo_write` remains opt-in. |
| `--allow` / `--deny` | unset | Repeatable Grok permission rules |
| `--always-approve` / `--no-always-approve` | on | Pass through Grok `--always-approve` by default; use `--no-always-approve` to disable |
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

## Source-reading and response discipline

For repository tasks, prefer `grep` to locate symbols and
`run_terminal_cmd` with bounded line ranges to inspect source. Avoid returning
complete large files, raw command output, or raw logs. The caller prompt should
ask for a concise summary of changes, tests and results, blockers, and evidence
paths so that only the useful result is returned to the caller context.

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
