---
name: call-grok
description: Run one short-lived, non-interactive Grok CLI task for a caller that supplies its own prompt and model configuration.
---

# call-grok

Use `scripts/grok_task.py` when a skill needs one bounded Grok CLI invocation.

The caller owns the task prompt, tool and permission policy overrides, model
configuration, and interpretation of the returned text. By default, the
wrapper passes the Grok CLI tool allowlist
`read_file,search_replace,list_dir,grep,run_terminal_cmd,todo_write`; callers
can replace it with `--tools`. This skill provides no task presets or templates.

**调用流程：**启动 `grok_task.py` 后让它后台运行，主 session 立即继续执行不冲突工作，不要同步等待其最终 JSON。
只有在依赖 Grok 结果或到达验证控制点时才轮询/读取完成状态。

```powershell
python "<repo>\skills\call-grok\scripts\grok_task.py" `
  --cwd "<target-repo>" `
  --executable "<grok-executable>" `
  --prompt-file "<prompt-file>" `
  --max-run 100 `
  --overall-timeout-sec 600 `
  --model "grok-4.5" `
  --effort high `
  --tools "read_file,search_replace,list_dir,grep,run_terminal_cmd,todo_write" `
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

The default tool IDs follow the installed Grok CLI's `--tools` allowlist:
`read_file` reads files, `search_replace` writes/edits files, `list_dir` lists
directories, `grep` searches text, `run_terminal_cmd` runs shell commands, and
`todo_write` manages task lists. These are CLI tool IDs, not display names.

The runner defaults to a 600-second (10-minute) stall and wall-clock timeout.
For a larger task, callers may raise the relevant timeout explicitly, up to
1800 seconds (30 minutes); values above that limit fail closed. `--max-run`
controls Grok turns and is independent of the timeout in seconds.

The wrapper emits exactly one JSON envelope on stdout with `ok`, `status`,
`text`, `usage`, `exit_code`, and `error`; diagnostics, heartbeats, and liveness
messages go to stderr. Callers validate any business schema and choose retry
policy themselves. See [caller contract](references/caller-contract.md) for the
full flag and status table.
