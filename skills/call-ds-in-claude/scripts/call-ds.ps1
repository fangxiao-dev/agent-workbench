<#
.SYNOPSIS
  Run one `claude -p` task on DeepSeek and stream a readable process log (no thinking).
  Env overrides are scoped to this process; the parent session is untouched.
#>
param(
  [string]$PromptFile,
  [string]$Prompt,
  [string]$Cwd = (Get-Location).Path,
  [string]$Model = "deepseek-v4-flash",
  [string]$Resume,                       # session_id from a previous [done] line
  [string]$CliModel,                    # optional --model alias (sonnet/opus/haiku) to verify mapping
  [string]$Permission = "acceptEdits",   # use bypassPermissions to let it run Bash unattended
  [string]$Tools,                        # e.g. "Read,Grep,Glob"; omit for all default tools
  [int]$ClipChars = 400,                 # per-tool-result clip in the log
  [int]$IdleTimeoutSec = 900,            # kill the child if no output line for this long; 0 = never
  [int]$HeartbeatSec = 60                # print [hb] after this much silence; 0 = off
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

if ($PromptFile) { $Prompt = Get-Content -LiteralPath $PromptFile -Raw -Encoding UTF8 }
if (-not $Prompt) { throw "Provide -Prompt or -PromptFile." }

$key = $env:DEEPSEEK_API_KEY
if (-not $key) { $key = (Get-Content -LiteralPath "$HOME\.claude\secrets\deepseek.key" -Raw).Trim() }

# PATH claude first; fall back to the newest desktop-bundled binary (Volta shim may be broken).
$exe = $env:CLAUDE_EXE
if (-not $exe) {
  $c = Get-Command claude -ErrorAction SilentlyContinue
  if ($c -and $c.Source -notmatch 'Volta') { $exe = $c.Source }
  else {
    $exe = Get-ChildItem "$env:APPDATA\Claude\claude-code" -Filter claude.exe -Recurse -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
    if (-not $exe -and $c) { $exe = $c.Source }
  }
}
if (-not $exe) { throw "claude executable not found; set CLAUDE_EXE." }

$vars = @{
  ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"; ANTHROPIC_AUTH_TOKEN = $key; ANTHROPIC_API_KEY = $null
  ANTHROPIC_MODEL = $Model; ANTHROPIC_SMALL_FAST_MODEL = $Model
  ANTHROPIC_DEFAULT_HAIKU_MODEL = $Model; ANTHROPIC_DEFAULT_SONNET_MODEL = $Model; ANTHROPIC_DEFAULT_OPUS_MODEL = $Model
  CLAUDE_CODE_SUBAGENT_MODEL = $Model; CLAUDE_CODE_MAX_CONTEXT_TOKENS = "1000000"
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
}
# Desktop host injects its own Claude login via CLAUDE_CODE_*; drop it so it never reaches DeepSeek.
Get-ChildItem Env: | Where-Object { $_.Name -match '^(CLAUDE_(CODE|AGENT)_|CLAUDECODE$)' -and -not $vars.ContainsKey($_.Name) } |
  ForEach-Object { $vars[$_.Name] = $null }
$saved = @{}
foreach ($k in @($vars.Keys)) { $saved[$k] = [Environment]::GetEnvironmentVariable($k, "Process"); [Environment]::SetEnvironmentVariable($k, $vars[$k], "Process") }

function Clip($s) { $s = "$s" -replace '\s+', ' '; if ($s.Length -gt $ClipChars) { $s.Substring(0, $ClipChars) + '...' } else { $s } }
$cliArgs = @('-p', '--permission-mode', $Permission, '--strict-mcp-config', '--output-format', 'stream-json', '--verbose')
if ($Tools) { $cliArgs += "--tools=$Tools" }
if ($Resume) { $cliArgs += @('--resume', $Resume) }   # same -Cwd as the original run
if ($CliModel) { $cliArgs += @('--model', $CliModel) }   # alias check: sonnet/opus/haiku all resolve to $Model

$script:session = $null; $script:gotResult = $false; $script:lastLine = ''
function Handle($line) {
  if ("$line" -match 'claude\.ai connectors are disabled|unrecognized_model') { return }   # known harmless notices
  if ("$line" -notmatch '^\s*\{') { "[cli] $line"; return }   # non-JSON line = CLI warning/error text
  $script:lastLine = Clip $line
  $j = "$line" | ConvertFrom-Json
  if ($j.session_id) { $script:session = $j.session_id }
  switch ($j.type) {
    'system'    { if ($j.subtype -eq 'init') { "[init] model=$($j.model) cwd=$($j.cwd)" } }
    'assistant' { foreach ($b in $j.message.content) {
                    if ($b.type -eq 'text') { "[text] $($b.text)" }
                    elseif ($b.type -eq 'tool_use') { "[tool] $($b.name) $(Clip ($b.input | ConvertTo-Json -Compress -Depth 5))" } } }
    'user'      { foreach ($b in $j.message.content) { if ($b.type -eq 'tool_result') {
                    $t = if ($b.content -is [string]) { $b.content } else { ($b.content | ForEach-Object { $_.text }) -join ' ' }
                    "[result] $(Clip $t)" } } }
    'result'    { $script:gotResult = $true
                  "[done] $($j.duration_ms)ms models=$(($j.modelUsage.PSObject.Properties.Name) -join ',') error=$($j.is_error) session=$($j.session_id)"
                  "---"; $j.result }
  }
}

$psi = [Diagnostics.ProcessStartInfo]::new($exe)
foreach ($a in $cliArgs) { $psi.ArgumentList.Add($a) }
$psi.WorkingDirectory = $Cwd
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
$utf8 = [Text.UTF8Encoding]::new($false)
$psi.StandardInputEncoding = $utf8; $psi.StandardOutputEncoding = $utf8; $psi.StandardErrorEncoding = $utf8

$p = $null; $exitCode = 0; $sw = [Diagnostics.Stopwatch]::StartNew(); $events = 0
try {
  $p = [Diagnostics.Process]::Start($psi)
  $p.StandardInput.Write($Prompt); $p.StandardInput.Close()
  $readers = @{ out = $p.StandardOutput; err = $p.StandardError }
  $pending = @{ out = $readers.out.ReadLineAsync(); err = $readers.err.ReadLineAsync() }
  $lastEvent = [Diagnostics.Stopwatch]::StartNew(); $lastHb = 0
  while ($pending.Count -gt 0) {
    $tasks = [Threading.Tasks.Task[]]@($pending.Values)
    [void][Threading.Tasks.Task]::WaitAny($tasks, 1000)
    foreach ($k in @($pending.Keys)) {
      if (-not $pending[$k].IsCompleted) { continue }
      $line = $pending[$k].Result
      if ($null -eq $line) { $pending.Remove($k); continue }   # stream closed
      $pending[$k] = $readers[$k].ReadLineAsync()
      $events++; $lastEvent.Restart(); $lastHb = 0
      Handle $line
    }
    $idle = [int]$lastEvent.Elapsed.TotalSeconds
    if ($IdleTimeoutSec -gt 0 -and $idle -ge $IdleTimeoutSec) {
      "[timeout] no output for ${idle}s; killing child. session=$script:session last=$script:lastLine"
      $exitCode = 2; break
    }
    if ($HeartbeatSec -gt 0 -and $idle -ge $HeartbeatSec -and ($idle - $lastHb) -ge $HeartbeatSec) {
      $lastHb = $idle
      "[hb] elapsed=$([int]$sw.Elapsed.TotalSeconds)s idle=${idle}s events=$events"
    }
  }
  if ($exitCode -eq 0) { [void]$p.WaitForExit(10000) }
}
finally {
  if ($p -and -not $p.HasExited) { try { $p.Kill($true) } catch {} }   # whole process tree
  if (-not $script:gotResult) {
    $ec = if ($p -and $p.HasExited) { $p.ExitCode } else { 'killed' }
    "[done] $([int]$sw.Elapsed.TotalMilliseconds)ms error=True no-result exit=$ec session=$script:session"
    if ($exitCode -eq 0) { $exitCode = 1 }
  }
  foreach ($k in @($vars.Keys)) { [Environment]::SetEnvironmentVariable($k, $saved[$k], "Process") }
}
exit $exitCode
