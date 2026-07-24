---
name: call-codex
description: Run one short-lived, non-interactive Codex CLI task for a caller that supplies its own prompt and model configuration.
---

# call-codex

Use `scripts/call_codex.py` when a skill needs one bounded Codex CLI invocation.

The caller owns the task prompt, output schema, permission/sandbox policy, model configuration, and how to interpret the returned text. This skill does not provide roles or task templates.

```powershell
python "<repo>\skills\call-codex\scripts\call_codex.py" `
  --cwd "<target-repo>" `
  --executable "C:\Users\<user>\AppData\Local\OpenAI\Codex\bin\codex.exe" `
  --prompt-file "<prompt-file>" `
  --timeout-s 900 `
  --model "gpt-5.5" `
  --config 'service_tier="fast"' `
  --sandbox read-only `
  --ephemeral `
  --output-schema "<schema.json>"
```

Pass exactly one of `--prompt` or `--prompt-file`. Repeat `--config` for multiple Codex `-c` settings. `--executable` (or `CODEX_EXECUTABLE` in the repository-local `.env` or process environment) pins a specific CLI; otherwise the wrapper ignores the non-executable WindowsApps package resource and discovers a normal PATH CLI or the newest per-user Desktop CLI. The wrapper emits exactly one JSON envelope on stdout; diagnostics go to stderr. Each invocation launches a new Codex process and never resumes or shares a session.

The envelope contains `ok`, `status`, `text`, `usage`, `exit_code`, and `error`. `text` is the final Codex response; callers validate it against any business schema themselves.
