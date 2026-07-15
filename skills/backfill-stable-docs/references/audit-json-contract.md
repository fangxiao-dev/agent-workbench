# Audit JSON Contract

`audit.json` 是同一次 audit 的 canonical machine record；`human-report.md` 只负责 owner 阅读。二者的基线、结论与计数必须一致。

## Minimum Shape

```json
{
  "schemaVersion": 1,
  "mode": "audit",
  "methodActivation": {
    "plugin": "stable-docs-backfill",
    "version": "0.1.0"
  },
  "project": {
    "repository": "owner/repository",
    "sourceHead": "full commit",
    "projectSourceWatermark": "full ancestor commit",
    "dirtyPaths": []
  },
  "configSha256": "sha256",
  "moduleCoverage": [
    {
      "module": "module-name",
      "result": "candidate",
      "itemIds": ["SDB-0123456789ab"]
    }
  ],
  "items": [
    {
      "id": "SDB-0123456789ab",
      "source": "docs/implementations/example/spec.md",
      "destination": "docs/canonical/example.md",
      "statement": "Atomic current contract.",
      "disposition": "candidate",
      "authority": ["approved-design", "current-test"],
      "evidence": ["path:line or Git blob identity"],
      "risk": "Why an incorrect promotion matters.",
      "confidence": "high"
    }
  ],
  "pending": [],
  "carryForward": [],
  "removedPackages": [],
  "blockers": []
}
```

## Invariants

- `methodActivation` 必须与当前 Plugin manifest 一致，不能存本机路径或 checkout commit。
- `sourceHead`、watermark 与 `configSha256` 固定本次 evidence universe；audit 后的新 commit 不属于本报告。Verify 同时收到显式 Source HEAD 时，两者必须解析到同一 commit。
- `items[].id` 由 source、destination 和规范化 statement 通过 `make_item_id.py` 生成；ID 唯一且不按排序重编号。
- `disposition` 只使用 `candidate`、`already-covered`、`conflict`、`no-delta`。
- `moduleCoverage` 必须覆盖配置的 module inventory；每个 item ID 必须被且只能被一个 coverage row 引用，coverage 不得引用未知 item。
- `pending`、`carryForward`、`removedPackages` 和 `blockers` 即使为空也必须存在，避免“未扫描”和“扫描后为空”无法区分。
- `pending` 使用 ID 字符串或含 `id`/`pendingId` 的对象；每个 ID 必须存在于配置的 pending register。`carryForward` 使用 package ID 字符串或含 `packageId`/`id` 的对象，并与 compaction state 的 `carry_forward` 对账。
- Human report 可以省略内部 ID/hash，但不得省略 owner decision、blocker 或改变计数。
