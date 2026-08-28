---
name: call-grok
description: Run one bounded, non-interactive Grok CLI task with a built-in THINK → IMPLEMENT → VERIFY workflow, caller-owned scope, self-verification, and Grok subagents available by default.
---

# call-grok

Use `scripts/grok_task.py` for one bounded Grok invocation. Impl-Package may
reference this adapter as `$grok-worker`; that caller supplies the bounded brief
and leaves model/effort at the adapter defaults.

The wrapper prepends its execution protocol to both `--prompt` and
`--prompt-file`; callers should not restate it.

## Invoke

Prefer an invocation-unique UTF-8 prompt file:

```powershell
python "<repo>\skills\call-grok\scripts\grok_task.py" `
  --cwd "<target-repo>" `
  --prompt-file "<prompt-file>" `
  --model "grok-4.6" `
  --effort high
```

Defaults are `grok-4.6`/`high`, Grok subagents enabled, `--always-approve`, a
30-minute no-stream stall window, and no hard overall timeout. Use
`--no-subagents` only for an explicit constrained invocation. Every call is
fresh unless the caller passes the returned `session_id` with `--resume`.

Run background invocations without blocking the main session. A read-only
monitor may report terminal process/envelope facts; it does not judge task
success. Resume a timed-out or stalled session when continuation is appropriate
instead of starting a duplicate task.

Stdout is one JSON envelope with `ok`, `status`, `text`, `usage`, `exit_code`,
`session_id`, and `error`; diagnostics stay on stderr. The caller validates the
business result and arranges any external review. See
[caller contract](references/caller-contract.md) for flags, Windows launch, and
terminal-status handling.
