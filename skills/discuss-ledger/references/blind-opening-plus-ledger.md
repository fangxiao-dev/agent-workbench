# Blind Opening + Ledger

Use this mode when a problem first needs unconstrained independent exploration and then requires a durable resolution of material disagreements.

```powershell
python <skill>\scripts\blind_opening_then_ledger.py `
  --root <target-project-root> `
  --topic <target-document-or-topic> `
  --agents codex,claude,grok `
  --max-rounds 5
```

The workflow is deliberately two-stage:

1. Run Blind Opening exactly as specified in [blind-opening.md](blind-opening.md). Participants remain mutually blind; the user-visible Markdown is written to `%TEMP%\discuss-ledger`.
2. Initialize a fresh normal ledger from the consolidated initial points, then invoke the unchanged normal `discuss_orchestrator.py` workflow. The ledger has the supplied model participants only; source attribution stays in point bodies.

Never use an existing ledger or overwrite an existing Blind artifact/ledger in this mode. A prior result must be reviewed or rerun under a new slug/run, rather than silently continued with stale or partially visible context.
