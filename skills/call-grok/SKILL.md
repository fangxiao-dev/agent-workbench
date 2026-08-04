---
name: call-grok
description: Run one short-lived, non-interactive Grok CLI task for a caller that supplies its own prompt and model configuration.
---

# call-grok

Use `scripts/grok_task.py` when a skill needs one bounded Grok CLI invocation.

The caller owns the task prompt, tool and permission policy overrides, model
configuration, and interpretation of the returned text. By default, the
wrapper passes the bounded Grok CLI tool allowlist
`grep,list_dir,run_terminal_cmd,read_file,search_replace`; callers can replace
it with `--tools`. This skill provides no task presets or templates.

For source reading, workers should use `grep` to locate relevant symbols and
`read_file` or `run_terminal_cmd` to read bounded source ranges. Do not dump
complete large files or raw command logs into the worker response. The task
prompt should require a concise change/test summary, blockers, and
evidence paths. `todo_write` remains opt-in for tasks that genuinely need it.

**调用流程：**启动 `grok_task.py` 后让它后台运行，主 session 立即继续执行不冲突工作，不要同步等待其最终 JSON。
只有在依赖 Grok 结果或到达验证控制点时才轮询/读取完成状态。

**默认 prompt 传输：**每次调用先创建一个 invocation-unique 的 UTF-8
临时 prompt 文件，再通过 `--prompt-file` 启动后台任务。不要在 Windows
`Start-Process -ArgumentList` 中传递多行 `--prompt`；PowerShell 重新拼接命令行时
可能把它按空白拆成多个参数，导致 wrapper 在参数解析阶段失败。并发调用不得复用同一
临时文件；任务结束且结果已读取后再删除该文件。`--prompt` 仅保留给调用者能够可靠
控制 quoting 的直接前台、单行短 prompt。

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

`--always-approve` is **on by default** (headless calls should not wait for interactive permission prompts). Pass `--no-always-approve` only when you intentionally want Grok's normal permission mode.

Provide exactly one of `--prompt-file` (the default) or `--prompt` (the
foreground single-line exception). `--executable` (or
`GROK_EXECUTABLE` in the repository-local `.env` or process environment) pins
a CLI; the legacy `GROK_BIN` environment name remains supported. All model,
tool, permission, worktree, and rule flags are optional and are forwarded only
when explicitly supplied. Each invocation launches a new Grok process and never
resumes or shares a session.

The example model is the current standard environment model, `grok-4.5`. If a
caller needs to override it, first run `grok models` and pass an id listed as
available by that CLI.

The default tool IDs follow the installed Grok CLI's `--tools` allowlist:
`grep` locates text, `list_dir` lists directories,
`run_terminal_cmd` runs bounded shell commands, `read_file` reads files, and
`search_replace` writes or edits files. These are CLI tool IDs, not display
names. `todo_write` remains opt-in through an explicit `--tools` value.

The runner defaults to a 600-second (10-minute) stall and wall-clock timeout.
For a larger task, callers may raise the relevant timeout explicitly, up to
1800 seconds (30 minutes); values above that limit fail closed. `--max-run`
controls Grok turns and is independent of the timeout in seconds.

## Windows PowerShell background launch

When launching the wrapper in the background on Windows, use `--prompt-file`
and build one quoted argument line for `Start-Process`; do not pass an
argument array that PowerShell can re-tokenize. Keep the prompt, stdout, and
stderr files under `$env:TEMP` or a worktree directory that has first been
confirmed writable. Do not hard-code `C:\tmp`.

```powershell
$tempRoot = $env:TEMP
$promptPath = Join-Path $tempRoot 'grok-<unique-invocation>.prompt.txt'
$resultPath = Join-Path $tempRoot 'grok-<unique-invocation>.result.json'
$errorPath = Join-Path $tempRoot 'grok-<unique-invocation>.stderr.log'

$argumentLine = @(
  ('"{0}"' -f $runner)
  '--cwd'
  ('"{0}"' -f $targetRepo)
  '--prompt-file'
  ('"{0}"' -f $promptPath)
  '--max-run 100'
  '--overall-timeout-sec 600'
  '--model grok-4.5'
  '--effort high'
  '--tools "grep,list_dir,run_terminal_cmd,read_file"'
  '--no-subagents'
) -join ' '

$process = Start-Process -FilePath 'python' -ArgumentList $argumentLine `
  -RedirectStandardOutput $resultPath `
  -RedirectStandardError $errorPath `
  -WindowStyle Hidden -PassThru
```

For read-only investigation, use only `grep`, `list_dir`, and
`run_terminal_cmd` in `--tools`; omitting `search_replace` keeps the worker
from editing files. Keep the invocation-specific prompt until the result has
been read, then remove the prompt and log files.

The wrapper emits exactly one JSON envelope on stdout with `ok`, `status`,
`text`, `usage`, `exit_code`, and `error`; diagnostics, heartbeats, and liveness
messages go to stderr. Callers validate any business schema and choose retry
policy themselves. See [caller contract](references/caller-contract.md) for the
full flag and status table.
