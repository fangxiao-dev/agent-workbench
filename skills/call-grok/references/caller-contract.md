# Caller contract

`call-grok` is a bounded, short-lived Grok CLI executor. The caller supplies the
task objective, scope, permissions, acceptance, and desired Grok configuration.
The wrapper composes that task with the Skill's built-in execution workflow.

When the caller uses the logical `$grok-worker` reference, omit `--model` and
`--effort`; the defaults in this skill remain the single model source for that
worker. Direct adapter callers may provide those options explicitly.

## Minimal invocation

```powershell
python "D:\CodeSpace\agent-workbench\skills\call-grok\scripts\grok_task.py" `
  --cwd "D:\path\to\repo" `
  --prompt-file "<unique-temp-prompt-file>"
```

Provide exactly one of `--prompt-file` or `--prompt`. Prefer an
invocation-unique UTF-8 temporary `--prompt-file` for background launches.
Do not reuse that file across concurrent calls; remove it only after the task
has finished and its JSON result has been read.

The wrapper reads either input, prepends its protocol, writes an
invocation-private temporary prompt file, and passes only that path to Grok. It
never edits the caller's file or places the composed prompt on the child argv.

Do not pass a multiline `--prompt` through Windows `Start-Process -ArgumentList`:
PowerShell may split it into extra process arguments before `grok_task.py` can
parse it.

## Public flags

| Flag | Default | Meaning |
|---|---:|---|
| `--cwd` | process cwd | Working directory for Grok |
| `--prompt-file` / `--prompt` | required | Caller-owned task text; wrapper composes it in a private temporary prompt file |
| `--resume` | unset (not passed) | Resume an existing Grok session by id; omit for a fresh session |
| `--max-run` | 100 | Maps to Grok `--max-turns` |
| `--model` | `grok-4.6` | Model id |
| `--effort` | `high` | Reasoning effort |
| `--tools` | unset (not passed) | Grok CLI tool allowlist; omit for CLI-native defaults. Example coding set: `grep,list_dir,run_terminal_cmd,read_file,search_replace` |
| `--allow` / `--deny` | unset | Repeatable Grok permission rules |
| `--always-approve` / `--no-always-approve` | on | Pass through Grok `--always-approve` by default; use `--no-always-approve` to disable |
| `--no-subagents` | off | Disable Grok subagents |
| `--worktree [NAME]` | unset | Pass through Grok worktree option |
| `--rules` | unset | Pass through Grok rules |
| `--stall-timeout-sec` | 1800 (max 1800) | No child stdout activity before declaring a stall |
| `--overall-timeout-sec` | unset (max 1800) | Optional hard wall-clock timeout |
| `--heartbeat-sec` | 15 | Stderr heartbeat interval |
| `--preflight` | off | Also require auth before model execution |
| `--dry-run` | off | Return the redacted would-be command in `text` |

The intentional runtime permission default is `--always-approve` (headless).
Tool policy remains caller-owned: omit `--tools` unless needed.

## Windows PowerShell background launch

Build one argument list with the wrapper path first. Prefer `--prompt-file`.
Keep prompt/stdout/stderr files under `$env:TEMP` or a confirmed-writable
worktree directory. Do not hard-code `C:\tmp`.

```powershell
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$wrapper = Join-Path $repo 'skills\call-grok\scripts\grok_task.py'
$promptPath = Join-Path $env:TEMP 'grok-<unique-invocation>.prompt.txt'
$resultPath = Join-Path $env:TEMP 'grok-<unique-invocation>.result.json'
$errorPath = Join-Path $env:TEMP 'grok-<unique-invocation>.stderr.log'

$wrapperArgs = @(
  $wrapper,
  '--cwd', $targetRepo,
  '--prompt-file', $promptPath,
  '--max-run', '100',
  '--model', 'grok-4.6',
  '--effort', 'high'
)
if ($wrapperArgs[0] -ne $wrapper) { throw 'Wrapper path must be the first Python argument' }

Start-Process -FilePath $pythonExe -ArgumentList $wrapperArgs `
  -RedirectStandardOutput $resultPath `
  -RedirectStandardError $errorPath `
  -WindowStyle Hidden -PassThru
```

## Output contract

stdout is exactly one JSON object:

```json
{
  "ok": true,
  "status": "completed",
  "text": "Grok's final response",
  "usage": {},
  "exit_code": 0,
  "session_id": "0193aaaaaaaaaaaaaaaaaaaaaaaaaa",
  "error": null
}
```

`error`, when present, has stable `code` and diagnostic `message`. Statuses are
`completed`, `dry_run`, `max_turns`, `stalled`, `timeout`, `cancelled`,
`preflight_failed`, or `error`. stderr is reserved for `[heartbeat]`,
`[liveness]`, `[grok-stderr]`, `[grok-stdout-raw]`, and related diagnostics.

Each call starts a fresh Grok process. The default is a new session. To continue
a previous chat, store `session_id` from the envelope and pass it back as
`--resume <session-id>`. The wrapper does not remember the last id. `session_id`
is also returned on incomplete statuses when the child reported one.

The no-stream stall window defaults to 1800 seconds (30 minutes); no hard
overall timeout is applied unless the caller supplies one. Grok subagents are
enabled unless the caller passes `--no-subagents`. The runner rejects explicit
timeouts above 1800 seconds (30 minutes). `--max-run` is a Grok turn limit, not
a seconds-based timeout.

Run the wrapper in the background and use stderr heartbeat/liveness to observe
progress instead of blocking the main session. Wrapper heartbeats do not reset
the stall window; only child stdout activity does. A timeout, stall, cancellation,
max-turns result, non-zero process exit, or malformed envelope is incomplete;
partial `text` must not be interpreted as successful task completion.
