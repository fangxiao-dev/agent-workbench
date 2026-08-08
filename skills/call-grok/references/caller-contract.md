# Caller contract

`call-grok` is a thin, short-lived Grok CLI executor. The caller supplies the
complete task prompt and any desired Grok configuration.

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

The wrapper passes `--prompt-file` through to Grok CLI (no full prompt on the
child argv). `--prompt` remains for short foreground prompts; values longer
than the inline limit are spilled to a temp file and sent via `--prompt-file`.

Do not pass a multiline `--prompt` through Windows `Start-Process -ArgumentList`:
PowerShell may split it into extra process arguments before `grok_task.py` can
parse it.

## Public flags

| Flag | Default | Meaning |
|---|---:|---|
| `--cwd` | process cwd | Working directory for Grok |
| `--prompt-file` / `--prompt` | required | Caller-owned task text; unique temporary `--prompt-file` is the preferred transport |
| `--max-run` | 100 | Maps to Grok `--max-turns` |
| `--model` | CLI default | Model id |
| `--effort` | CLI default | Reasoning effort |
| `--tools` | unset (not passed) | Grok CLI tool allowlist; omit for CLI-native defaults. Example coding set: `grep,list_dir,run_terminal_cmd,read_file,search_replace` |
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

No prompt envelope, role, or task template is injected. The sole intentional
runtime permission default is `--always-approve` (headless). Tool policy is
caller-owned: omit `--tools` unless you need a specific allowlist.

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
  '--overall-timeout-sec', '600',
  '--model', 'grok-4.5',
  '--effort', 'high',
  '--no-subagents'
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
  "error": null
}
```

`error`, when present, has stable `code` and diagnostic `message`. Statuses are
`completed`, `dry_run`, `max_turns`, `stalled`, `timeout`, `cancelled`,
`preflight_failed`, or `error`. stderr is reserved for `[heartbeat]`,
`[liveness]`, `[grok-stderr]`, `[grok-stdout-raw]`, and related diagnostics.

Each call starts a fresh Grok process. The wrapper does not resume sessions;
callers that need previous context must include it in a new prompt.

Timeouts default to 600 seconds (10 minutes). Callers may increase either
timeout for a larger task, but the runner rejects values above 1800 seconds (30
minutes). `--max-run` is a Grok turn limit, not a seconds-based timeout.
