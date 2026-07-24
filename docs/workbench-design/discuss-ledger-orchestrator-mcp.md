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
  --topic "Plan review"
```

Defaults:

- `--agents codex,claude`
- `--max-rounds 5`
- `--timeout-s 300` per agent turn

Path resolution:

- when `--topic` points to an existing file, the orchestrator uses the nearest ancestor containing `.git` as the effective `--root`
- it then stores/passes the topic as a path relative to that detected root
- this is intentionally layout-agnostic and covers normal clones, Git worktrees, `.worktrees/<name>/...`, and other checkout directories

Strategy:

- round-robin across `codex` and `claude`
- orchestrator calls `set_next` before every agent turn
- agents return structured JSON and never choose the next speaker
- prompts ask agents to prefer Chinese for summaries, arguments, and convergence lines unless the task explicitly requires another language
- stop on `已达成一致`, `僵局`, or `--max-rounds`

Deadlock definition:

- a point becomes `僵局` when it is contested with `movement=false` and its elapsed-round count reaches 2 or more
- the whole ledger becomes `僵局` only after no point remains open and at least one point is `僵局`

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

## Proposed discussion router and shared executors

`discuss-ledger` will evolve from a single discussion workflow into a router for
three explicitly selected modes. Existing normal-ledger behavior remains the
default for existing triggers and invocations.

This evolution does not use, extend, or require MCP. The existing MCP server is
outside this change and remains an optional interactive ledger interface. The
compatibility baseline is the current normal Discuss Ledger workflow: its
prompt, state-machine rules, CLI behavior, and fake-mode smoke path must remain
available after the executor extraction.

| Mode | Use case | Orchestration |
|---|---|---|
| Blind Opening | Independent brainstorming, option discovery, or risk discovery | Every participant receives only the original target and the blind-opening output contract; no participant receives another participant's result. The workflow may end after a consolidated result. |
| Discuss Ledger | Live disagreement, convergence, or a decision trail | The existing round-robin ledger state machine runs unchanged. |
| Blind Opening + Ledger | Open-ended design work that must later resolve material disagreements | Run Blind Opening, consolidate its independent findings into initial ledger points, then invoke the unchanged Discuss Ledger workflow. |

The skill's `SKILL.md` is a thin router: it selects one of these modes from
explicit user intent, reads only that mode's reference, and asks one clarifying
question when the requested mode is ambiguous. Detailed operating instructions
live in separate references for Blind Opening, normal Ledger discussion, and
the combined workflow. `loop-mode.md` remains an optional upper-level control
for bounded repeated reviews.

Blind Opening is not a special first turn in the existing ledger state machine.
It is an independent capability with its own prompt and result schema. In the
combined mode, its consolidated output is the only hand-off to Ledger: duplicate
findings may be merged, but conflicting recommendations and their supporting
evidence must be retained as initial open points. The normal ledger prompt,
CLI, and state machine do not learn about or depend on Blind Opening.

### Shared CLI executors

`call-codex` and `call-claude` will be separate repository-wide foundation
skills, usable by `discuss-ledger` and future skills. They own only the
model-specific execution boundary:

- command-line construction and stdin/file prompt input;
- process lifetime, timeout, cancellation, and error classification;
- host-specific structured-output parsing and retries;
- one common JSON result envelope containing at least `ok`, `status`, `text`,
  `usage`, `exit_code`, and `error`.

They do not define task roles, generate task prompts, choose permissions, or
interpret a caller's business schema. A caller explicitly supplies its model
configuration (for example Codex sandbox/config/model or Claude tools,
system prompt, effort, and schema). This keeps the existing discuss-ledger
read-only behavior as an upstream choice while allowing another skill to use
the same executor for an implementation task.

The existing `discuss_orchestrator.py` adapters will be reduced to calls to
these executors while preserving its current discussion prompt, state-machine
rules, and command-line semantics. A separate `blind_opening.py` will build
only blind-opening prompts and invoke the same executors. A combined
orchestration layer connects their artifacts without duplicating either
workflow.

The minimum implementation scope is therefore limited to the two generic
executors, the three-mode skill router and references, the independent
Blind-Opening workflow, and the thin combined hand-off. It excludes MCP changes,
new role presets, loop-mode changes, and changes to the normal Ledger design.

## Registration

MCP registration is independent from the main `install.sh` / `install.ps1` host installer. Use:

```bash
bash /path/to/agent-workbench/scripts/install-discuss-ledger-mcp.sh /path/to/project codex claude
```

```powershell
powershell -ExecutionPolicy Bypass -File D:\path\to\agent-workbench\scripts\install-discuss-ledger-mcp.ps1 D:\path\to\project codex claude
```

Codex registration writes project-local `.codex/config.toml` only when no conflicting `discussLedger` server exists. Claude registration prefers `claude mcp add --scope project`; if `claude` is unavailable, the script prints a `.mcp.json` snippet and exits successfully. Both registrations start the server with `uv run python` from the workbench root so `mcp[cli]` resolves from `pyproject.toml` / `uv.lock`.
