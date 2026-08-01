---
name: call-grok
description: Run one short-lived, non-interactive Grok CLI task for a caller that supplies its own prompt and model configuration.
---

# call-grok

Use `scripts/grok_task.py` when a skill needs one bounded Grok CLI invocation.

The caller owns the task prompt, tool and permission policy, model configuration,
and interpretation of the returned text. This skill provides no task presets,
templates, or default tool policy.

```powershell
python "<repo>\skills\call-grok\scripts\grok_task.py" `
  --cwd "<target-repo>" `
  --executable "<grok-executable>" `
  --prompt-file "<prompt-file>" `
  --max-run 100 `
  --overall-timeout-sec 600 `
  --model "grok-4.5" `
  --effort high `
  --tools "read_file,grep,list_dir" `
  --allow "Bash(git *)" `
  --deny "Bash(git push*)" `
  --no-subagents
```

Provide exactly one of `--prompt` or `--prompt-file`. `--executable` (or
`GROK_EXECUTABLE` in the repository-local `.env` or process environment) pins
a CLI; the legacy `GROK_BIN` environment name remains supported. All model,
tool, permission, worktree, and rule flags are optional and are forwarded only
when explicitly supplied. Each invocation launches a new Grok process and never
resumes or shares a session.

The example model is the current standard environment model, `grok-4.5`. If a
caller needs to override it, first run `grok models` and pass an id listed as
available by that CLI.

The runner defaults to a 600-second (10-minute) stall and wall-clock timeout.
For a larger task, callers may raise the relevant timeout explicitly, up to
1800 seconds (30 minutes); values above that limit fail closed. `--max-run`
controls Grok turns and is independent of the timeout in seconds.

The wrapper emits exactly one JSON envelope on stdout with `ok`, `status`,
`text`, `usage`, `exit_code`, and `error`; diagnostics, heartbeats, and liveness
messages go to stderr. Callers validate any business schema and choose retry
policy themselves. See [caller contract](references/caller-contract.md) for the
full flag and status table.
