# Normal Discuss Ledger

Use normal Ledger when two or more parties must answer live disagreements, converge a plan/design/spec, or explicitly continue an existing discussion. This is the compatibility-default path for existing `discuss-ledger` requests.

The source of truth is a Markdown ledger under `docs/exchange/discuss/discuss-<slug>.md`. The deterministic writer owns YAML, point IDs, tables, round progression, convergence, and deadlock status. Do not hand-edit those structures.

Read the applicable detail before acting:

- [ledger-cli.md](ledger-cli.md) for exact ledger mutations and status commands;
- [orchestrator.md](orchestrator.md) before automated Codex/Claude orchestration;
- [loop-mode.md](loop-mode.md) only for an explicitly bounded loop;
- [claude-code-noninteractive.md](claude-code-noninteractive.md) only for Claude CLI availability/auth issues.

For a normal discussion turn, read the target and current ledger, promote genuinely settled points first, respond only to live disagreements with evidence, add only material new disagreements, then end the turn. Converged points remain context; reopen only for new evidence, a material newly discovered risk, implementation feedback, or an explicit continuation request.

The orchestrator retains its existing round-robin prompt, CLI, state-machine, fake-mode and exit semantics. It invokes `call-codex` / `call-claude` only as downstream process executors; those skills do not decide discussion behavior.

The participant prompt is the editable [ledger-participant-prompt.md](ledger-participant-prompt.md) reference. The orchestrator only injects current topic, target, schema, and ledger state into its placeholders.
