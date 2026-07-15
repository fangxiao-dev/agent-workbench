# Audit JSON Contract

`audit.json` 是同一次 audit 的 canonical machine record；`human-report.md` 只负责 owner 阅读。二者的基线、结论与计数必须一致。

## Minimum Shape

```json
{
  "schemaVersion": 2,
  "mode": "audit",
  "methodActivation": {
    "repository": "owner/agent-workbench",
    "commit": "full method commit"
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
      "evidence": [{"path": "docs/implementations/example/spec.md", "blob": "full Git blob ID"}],
      "canonicalOwner": "module-knowledge-owner",
      "fingerprint": "sha256:item-local-fingerprint",
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

- `schemaVersion: 1` 是 legacy provenance，不能作为新的 apply 输入；新 audit 一律写 `schemaVersion: 2`。
- `methodActivation` 必须使用 public Skill 的 `repository + commit`，不能存本机路径或 Plugin-era `plugin + version`。Apply 要求 repository 与当前方法相同；同 repository 的 method commit 漂移不让整份报告失效。
- `project.repository` 与 `configSha256` 是全局 fail-closed context：不同项目 repository 或配置摘要不兼容。`sourceHead` 仍固定 audit evidence universe，但 apply 可在它的 descendant 上逐项复验，不要求全局 HEAD 等值。
- `items[].id` 由 source、destination 和规范化 statement 通过 `make_item_id.py` 生成；ID 唯一且不按排序重编号。
- 每个 item 必须有唯一 `canonicalOwner`、非空 authority 与带 project-relative `path` 和完整 Git `blob` ID 的 evidence。`fingerprint` 是 `source`、`destination`、规范化 statement、排序后的 authority、item-local evidence identities 与 canonicalOwner 的 SHA-256；它不包含 method commit、全局 Source HEAD 或 config digest。
- Apply 在当前 Source HEAD（必须等于或是 audit Source HEAD 的 descendant）重新解析每个 evidence path 的 blob 并重算 fingerprint。只将 fingerprint 不变的批准 item 视为可 apply；缺失或改变的 evidence、canonical owner 不匹配或 fingerprint 不匹配的 item 保持 pending，不使其他 item 失效。
- `disposition` 只使用 `candidate`、`already-covered`、`conflict`、`no-delta`。
- `moduleCoverage` 必须覆盖配置的 module inventory；每个 item ID 必须被且只能被一个 coverage row 引用，coverage 不得引用未知 item。
- `pending`、`carryForward`、`removedPackages` 和 `blockers` 即使为空也必须存在，避免“未扫描”和“扫描后为空”无法区分。
- `pending` 使用 ID 字符串或含 `id`/`pendingId` 的对象；每个 ID 必须存在于配置的 pending register。`carryForward` 使用 package ID 字符串或含 `packageId`/`id` 的对象，并与 compaction state 的 `carry_forward` 对账。
- Human report 可以省略内部 ID/hash，但不得省略 owner decision、blocker 或改变计数。
