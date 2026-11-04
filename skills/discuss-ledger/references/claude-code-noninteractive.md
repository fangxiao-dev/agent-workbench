# Claude Code Noninteractive Environment

Use this when the orchestrator reports Claude auth/login trouble, or `claude -p` hangs after warnings while the user says Claude Code is already logged in. Do not tell the user to log in again first; this is usually environment drift in the subprocess:

- Interactive shell aliases (e.g. `claude --dangerously-skip-permissions`) are not inherited by `subprocess`.
- `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL` and related `ANTHROPIC_*` variables make Claude Code prefer a third-party provider over the Claude.ai login.
- Typical symptom: an auth-source warning, `duration_api_ms=0`, 0 tokens, a hang, or an `AUTH` classification.

Diagnose without printing values, then probe with the provider variables removed (PowerShell shown; in zsh use `env -u NAME ...`):

```powershell
Get-Command claude -All | Select-Object CommandType, Source
Get-ChildItem Env: | Where-Object Name -match '^ANTHROPIC' | Select-Object -ExpandProperty Name
Get-ChildItem Env: | Where-Object Name -match '^ANTHROPIC' | ForEach-Object { Remove-Item "Env:$($_.Name)" }
'Return {"ok":true} only.' | claude -p --no-session-persistence --effort low --disable-slash-commands --tools "" --output-format json
```

If the probe succeeds, run the orchestrator from that same shell so it inherits the cleaned environment. Only classify the issue as missing auth after the clean probe also fails. Never print env values, tokens, keys, signed URLs or provider endpoints.

If `claude` itself fails to start (not an auth error), check that `Get-Command claude` resolves to a working executable; a stale package-manager shim is a common cause.
