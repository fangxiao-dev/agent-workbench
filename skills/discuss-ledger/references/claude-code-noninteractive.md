# Claude Code Noninteractive Environment Fix

Use this reference when the orchestrator says Claude requires login/authentication, or `claude -p` hangs after warnings while the user says Claude Code / Claude Pro is already logged in.

Do **not** immediately tell the user to log in again. This is often a false failure caused by noninteractive subprocess environment drift:

- `subprocess.Popen(["claude", ...])` does not inherit interactive zsh aliases such as `claude --dangerously-skip-permissions`.
- `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, or related `ANTHROPIC_*` variables can make Claude Code prefer a third-party Anthropic-compatible provider over the user's Claude.ai login.
- Typical symptom: a warning about auth sources or disabled connectors, `duration_api_ms=0`, 0 tokens, hanging, or an orchestrator `AUTH` / login classification.

Before declaring Claude unavailable, run the diagnosis for the current shell without printing secret values.

### macOS and Linux (zsh)

```bash
zsh -lic 'printf "which claude: "; which claude; printf "alias claude: "; alias claude 2>/dev/null || true; printf "ANTHROPIC env names:\n"; env | cut -d= -f1 | rg "^ANTHROPIC" | sort'
```

Then run a minimal clean-environment probe:

```bash
zsh -lic 'unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY ANTHROPIC_BASE_URL ANTHROPIC_MODEL ANTHROPIC_DEFAULT_HAIKU_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL ANTHROPIC_DEFAULT_SONNET_MODEL ANTHROPIC_REASONING_MODEL; printf %s "Return {\"ok\":true} only." | claude --dangerously-skip-permissions -p --no-session-persistence --effort low --disable-slash-commands --tools "" --system-prompt "Return only JSON." --output-format json'
```

If the probe succeeds, Claude Code is usable. Run the orchestrator with the same provider overrides removed from its process environment:

```bash
env \
  -u ANTHROPIC_AUTH_TOKEN \
  -u ANTHROPIC_API_KEY \
  -u ANTHROPIC_BASE_URL \
  -u ANTHROPIC_MODEL \
  -u ANTHROPIC_DEFAULT_HAIKU_MODEL \
  -u ANTHROPIC_DEFAULT_OPUS_MODEL \
  -u ANTHROPIC_DEFAULT_SONNET_MODEL \
  -u ANTHROPIC_REASONING_MODEL \
  python <skill>/scripts/discuss_orchestrator.py --root <target-project-root> --topic <target-doc-or-topic>
```

### Windows (PowerShell)

Run the following in a new PowerShell window. It lists only command resolution and `ANTHROPIC_*` variable *names*, never their values:

```powershell
Write-Output 'claude commands:'
Get-Command claude -All -ErrorAction SilentlyContinue | Select-Object CommandType, Name, Source, Definition
Write-Output 'claude alias:'
Get-Alias claude -ErrorAction SilentlyContinue | Select-Object Name, Definition
Write-Output 'ANTHROPIC env names:'
Get-ChildItem Env: | Where-Object { $_.Name -match '^ANTHROPIC' } | Select-Object -ExpandProperty Name | Sort-Object
```

Use the same new window for the clean-environment probe. These removals affect only that PowerShell process and its child processes; they do not change user or system environment settings:

```powershell
$anthropicVariables = @(
  'ANTHROPIC_AUTH_TOKEN',
  'ANTHROPIC_API_KEY',
  'ANTHROPIC_BASE_URL',
  'ANTHROPIC_MODEL',
  'ANTHROPIC_DEFAULT_HAIKU_MODEL',
  'ANTHROPIC_DEFAULT_OPUS_MODEL',
  'ANTHROPIC_DEFAULT_SONNET_MODEL',
  'ANTHROPIC_REASONING_MODEL'
)
foreach ($name in $anthropicVariables) {
  Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
}
'Return {"ok":true} only.' | claude --dangerously-skip-permissions -p --no-session-persistence --effort low --disable-slash-commands --tools "" --system-prompt 'Return only JSON.' --output-format json
```

If the probe succeeds, run the orchestrator from that same PowerShell window so it inherits the cleaned provider environment:

```powershell
python <skill>\scripts\discuss_orchestrator.py --root <target-project-root> --topic <target-doc-or-topic>
```

Only classify the issue as real missing auth after the clean probe also fails. Never print env values, tokens, API keys, signed URLs, or provider endpoints while debugging this.
