Use `discuss-ledger` orchestrated auto-discussion for the requested target.

If the user provides a project root and target document/topic, run:

```bash
python <discuss-ledger-skill-dir>/scripts/discuss_orchestrator.py --root <project-root> --topic <target-document-or-topic>
```

Defaults are `agents=codex,claude`, `max-rounds=5`, and `timeout-s=300`; do not ask for confirmation when root and target are clear. After the run, report the ledger path, convergence summary, open/deadlocked points, and whether user裁决 is needed.
