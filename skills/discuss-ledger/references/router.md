# Router Contract

`discuss_router.py` selects a workflow and its participants; it does not define model roles, prompts, permissions, or executor behavior.

| Setting | Default | Accepted values | Effect |
| --- | --- | --- | --- |
| `--mode` | `ledger` | `ledger`, `blind`, `combined` | Select normal discussion, independent discovery, or Blind Opening followed by normal Ledger. |
| `--agents` | `codex,claude` | `full`, or exactly two distinct names from `codex`, `claude`, `grok` | Select participants independently of the workflow. `full` expands to `codex,claude,grok`. |

The Router dispatches without changing the selected workflow's semantics:

- `ledger` → `discuss_orchestrator.py`; `--max-rounds` defaults to five full participant cycles.
- `blind` → `blind_opening.py`; it writes only the independent-opening artifacts.
- `combined` → `blind_opening_then_ledger.py`; it runs Blind Opening, then hands its consolidated points to the unchanged Ledger workflow.

Use the lower-level scripts only when a caller deliberately needs their implementation-level flexibility. The public Router rejects one-participant and literal three-participant lists so its externally visible choices remain “default pair”, “an explicit pair”, or `full`.
