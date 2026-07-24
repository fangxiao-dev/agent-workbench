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
  --max-run 120 `
  --model "grok-4" `
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

The wrapper emits exactly one JSON envelope on stdout with `ok`, `status`,
`text`, `usage`, `exit_code`, and `error`; diagnostics, heartbeats, and liveness
messages go to stderr. Callers validate any business schema and choose retry
policy themselves. See [caller contract](references/caller-contract.md) for the
full flag and status table.
