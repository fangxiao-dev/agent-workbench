# Blind Opening + Ledger

Use this mode when a problem first needs unconstrained independent exploration and then requires a durable resolution of material disagreements.

```powershell
python <skill>\scripts\discuss_router.py `
  --mode combined `
  --root <target-project-root> `
  --topic <target-document-or-topic> `
  --agents full `
  --claude-effort medium `
  --max-rounds 5
```

The workflow is deliberately two-stage:

1. Run Blind Opening exactly as specified in [blind-opening.md](blind-opening.md). Participants remain mutually blind; the user-visible Markdown is written to `%TEMP%\discuss-ledger`.
2. Initialize a fresh normal ledger from the consolidated initial points, then invoke the unchanged normal `discuss_orchestrator.py` workflow. The ledger has the supplied model participants only; source attribution stays in point bodies。调用方选择的 `--claude-effort` 在两个阶段保持一致。

Never use an existing ledger or overwrite an existing Blind artifact/ledger in this mode. A prior result must be reviewed or rerun under a new slug/run, rather than silently continued with stale or partially visible context.
