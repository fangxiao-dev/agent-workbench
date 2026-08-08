---
name: call-grok
description: Run one short-lived, non-interactive Grok CLI task for a caller that supplies its own prompt and model configuration.
---

# call-grok

Use `scripts/grok_task.py` when a skill needs one bounded Grok CLI invocation.

The caller owns the task prompt, tool policy, model configuration, and
interpretation of the returned text. This skill provides no task presets,
roles, or prompt templates. The only intentional runtime default is
`--always-approve` (on) so headless calls do not block on permission prompts;
pass `--no-always-approve` to disable.

**调用流程：**启动 `grok_task.py` 后让它后台运行，主 session 立即继续执行不冲突工作，不要同步等待其最终 JSON。
只有在依赖 Grok 结果或到达验证控制点时才轮询/读取完成状态。

## Invoke

```powershell
python "<repo>\skills\call-grok\scripts\grok_task.py" `
  --cwd "<target-repo>" `
  --executable "<grok-executable>" `
  --prompt-file "<prompt-file>" `
  --max-run 100 `
  --overall-timeout-sec 600 `
  --model "grok-4.5" `
  --effort high `
  --tools "grep,list_dir,run_terminal_cmd,read_file,search_replace" `
  --no-subagents
```

Provide exactly one of `--prompt-file` (preferred, especially background) or
`--prompt` (short foreground exception). `--executable` (or `GROK_EXECUTABLE` /
legacy `GROK_BIN`) pins a CLI. All model, tool, worktree, and rule flags are
optional and are forwarded only when supplied. Each invocation starts a new
Grok process and never resumes a session.

Wrapper `--prompt-file` is passed through to Grok as `--prompt-file` (no full
prompt on argv). Long `--prompt` values are spilled to a temp file automatically.

## Output contract

stdout is exactly one JSON envelope with `ok`, `status`, `text`, `usage`,
`exit_code`, and `error`. Diagnostics and heartbeats go to stderr. Callers
validate business schema and choose retry policy themselves.

## Background launch

When launching with PowerShell `Start-Process`, put the wrapper script first in
the Python argument list and prefer `--prompt-file`. Use invocation-unique temp
files under `$env:TEMP` or a writable worktree path. Full flag table, timeout
caps, and Windows quoting notes: [caller contract](references/caller-contract.md).
