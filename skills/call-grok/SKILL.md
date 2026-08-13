---
name: call-grok
description: Run one short-lived, non-interactive Grok CLI task for a caller that supplies its own prompt and model configuration.
---

# call-grok

When referenced by Impl-Package as `$grok-worker`, this skill is the logical
worker adapter: the caller supplies the bounded brief and omits model and
effort overrides. Direct `call-grok` users may still use the adapter's
documented options.

Use `scripts/grok_task.py` when a skill needs one bounded Grok CLI invocation.

The caller owns the task prompt, tool policy, model configuration overrides, and
interpretation of the returned text. When the caller does not override them, the
wrapper uses `grok-4.6` with `effort=high`. This skill provides no task presets,
roles, or prompt templates. Runtime defaults are `grok-4.6`/`high`, a 20-minute
no-stream stall window with no hard overall timeout, Grok subagents enabled, and
`--always-approve` on so headless calls do not block on permission prompts. Pass `--no-subagents` or
`--no-always-approve` only when the caller needs those restrictions.

**调用流程：**启动 `grok_task.py` 后让它后台运行，主 session 立即继续执行不冲突工作，不要同步等待其最终 JSON。轮询时读取 stderr heartbeat/liveness；heartbeat 只报告状态，只有 Grok child stdout activity 重置 stall window。只有在依赖 Grok 结果或到达验证控制点时才读取完成状态。timeout/stall 后必须采信 terminal envelope 与 process exit，不能把 partial text 当作成功。

## Invoke

```powershell
python "<repo>\skills\call-grok\scripts\grok_task.py" `
  --cwd "<target-repo>" `
  --executable "<grok-executable>" `
  --prompt-file "<prompt-file>" `
  --max-run 100 `
  --model "grok-4.6" `
  --effort high `
  --tools "grep,list_dir,run_terminal_cmd,read_file,search_replace"
```

Provide exactly one of `--prompt-file` (preferred, especially background) or
`--prompt` (short foreground exception). `--executable` (or `GROK_EXECUTABLE` /
legacy `GROK_BIN`) pins a CLI. `--model` and `--effort` default to `grok-4.6`
and `high`; other tool, worktree, and rule flags are optional and are forwarded
only when supplied. Each invocation starts a new Grok process. The default is a
fresh session; pass `--resume <session-id>` to continue a previous chat. Store
`session_id` from the envelope — the wrapper does not remember the last id.

Wrapper `--prompt-file` is passed through to Grok as `--prompt-file` (no full
prompt on argv). Long `--prompt` values are spilled to a temp file automatically.

## Output contract

stdout is exactly one JSON envelope with `ok`, `status`, `text`, `usage`,
`exit_code`, `session_id`, and `error`. `session_id` is the Grok session UUID
when the child reported one, otherwise `null` (including preflight and dry-run).
Diagnostics and heartbeats go to stderr. Callers validate business schema and
choose retry policy themselves.

## Background launch

When launching with PowerShell `Start-Process`, put the wrapper script first in
the Python argument list and prefer `--prompt-file`. Use invocation-unique temp
files under `$env:TEMP` or a writable worktree path. Full flag table, timeout
caps, and Windows quoting notes: [caller contract](references/caller-contract.md).
