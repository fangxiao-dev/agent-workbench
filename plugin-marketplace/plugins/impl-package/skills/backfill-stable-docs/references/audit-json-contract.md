# Audit JSON

```json
{
  "mode": "audit",
  "targetBranchCommit": "<Git commit>",
  "items": [
    {
      "id": "docs/implementations/example::DD-1",
      "origin": "gap-catching",
      "source": "docs/implementations/example/gate.md#durable-deltas",
      "destination": "docs/module-knowledge/example.md",
      "statement": "<durable fact>",
      "comparisonCommit": "<Git commit>",
      "disposition": "candidate",
      "evidence": ["src/example.py", "tests/test_example.py"]
    }
  ],
  "doneFiltered": [
    {
      "id": "docs/implementations/example::DD-0",
      "doneFilterReason": "matched records.done id=... comparisonCommit=..."
    }
  ],
  "blockers": []
}
```

Paths are repository-relative. Item IDs use `<package-path>::<delta-id>`; derive them from the source's stable readable `delta-id`, never from row position or a temporary sequence. `candidate | already-covered | conflict | no-delta` are the only dispositions. Collector inventory may also emit `filtered-by-done` rows for audit visibility; those are not apply dispositions. The file contains current audit conclusions, not migration history.
