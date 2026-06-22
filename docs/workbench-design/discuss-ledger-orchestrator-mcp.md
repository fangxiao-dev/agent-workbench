# Discuss Ledger MCP + Local Orchestrator MVP

`skills/discuss-ledger` keeps the Markdown ledger as the source of truth, but its implementation is now shared by three entry points:

- CLI: `skills/discuss-ledger/scripts/discuss_ledger.py`
- MCP server: `skills/discuss-ledger/mcp_server.py`
- Local orchestrator: `skills/discuss-ledger/scripts/discuss_orchestrator.py`

The shared core lives under `skills/discuss-ledger/src/discuss_ledger_core/` and owns the existing Markdown format, frontmatter state machine, point table updates, convergence section, and turn lifecycle.

## MCP Server

The server uses the official Python FastMCP SDK from the workbench `uv` environment:

```bash
cd /path/to/agent-workbench
uv run python skills/discuss-ledger/mcp_server.py --root /path/to/project
```

It defaults to stdio transport and accepts:

- `--root`: target project root
- `--dir`: ledger directory relative to root, default `docs/exchange/discuss`

Tools:

- `init_ledger`
- `get_status`
- `add_point`
- `contest_point`
- `converge_point`
- `end_turn`
- `record_agent_turn`

Resources:

- `ledger://{slug}/state`
- `ledger://{slug}/markdown`
- `ledger://{slug}/open-points`
- `ledger://{slug}/convergence`

`record_agent_turn` writes in discuss-ledger order: convergences first, contests second, new points last. It does not end the turn unless `end_turn_after` is true.

`set_next` remains a CLI/core operation for the user or an orchestrator. It is intentionally not registered as an agent-visible MCP tool, because next-speaker selection is outside an individual participant's authority. The MCP server is project-local and assumes the host process is trusted; it does not provide per-caller identity or authorization for mutating tools.

## Local Orchestrator

The MVP orchestrator supports only Codex and Claude Code:

```bash
python /path/to/agent-workbench/skills/discuss-ledger/scripts/discuss_orchestrator.py \
  --root /path/to/project \
  --topic "Plan review" \
  --agents codex,claude
```

Strategy:

- round-robin across `codex` and `claude`
- orchestrator calls `set_next` before every agent turn
- agents return structured JSON and never choose the next speaker
- prompts ask agents to prefer Chinese for summaries, arguments, and convergence lines unless the task explicitly requires another language
- stop on `已达成一致`, `僵局`, or `--max-rounds`

Real adapters:

- Codex: `codex exec --json --output-schema <schema> --sandbox read-only --cd <root> -`
- Claude: `claude -p --output-format json <prompt>` with local schema-shape validation

Claude gets one JSON repair retry if the first response is not valid JSON. Adapter blockers are reported as clean `AUTH`, `PERMISSION`, or `BINARY_NOT_FOUND` errors where possible.

Test mode:

```bash
python /path/to/agent-workbench/skills/discuss-ledger/scripts/discuss_orchestrator.py \
  --root /tmp/project \
  --topic "Smoke" \
  --slug smoke \
  --fake \
  --max-rounds 2
```

The fake mode does not require CLI auth and is intended for installation and CI smoke checks.

## Registration

MCP registration is independent from the main `install.sh` / `install.ps1` host installer. Use:

```bash
bash /path/to/agent-workbench/scripts/install-discuss-ledger-mcp.sh /path/to/project codex claude
```

```powershell
powershell -ExecutionPolicy Bypass -File D:\path\to\agent-workbench\scripts\install-discuss-ledger-mcp.ps1 D:\path\to\project codex claude
```

Codex registration writes project-local `.codex/config.toml` only when no conflicting `discussLedger` server exists. Claude registration prefers `claude mcp add --scope project`; if `claude` is unavailable, the script prints a `.mcp.json` snippet and exits successfully. Both registrations start the server with `uv run python` from the workbench root so `mcp[cli]` resolves from `pyproject.toml` / `uv.lock`.
