# Audit JSON

```json
{
  "mode": "audit",
  "targetBranchCommit": "<Git commit>",
  "items": [
    {
      "id": "docs/implementations/example::DD-1",
      "source": "docs/implementations/example/gate.md#durable-deltas",
      "destination": "docs/module-knowledge/example.md",
      "statement": "<durable fact>",
      "disposition": "candidate",
      "evidence": ["src/example.py", "tests/test_example.py"]
    }
  ],
  "blockers": []
}
```

Paths are repository-relative. `candidate | already-covered | conflict | no-delta` are the only dispositions. The file contains current audit conclusions, not migration history.
