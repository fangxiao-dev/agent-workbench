# Stable Docs Backfill Apply Record

- Phase: `apply`
- Applied:
- Project:
- Source audit report:
- Source HEAD at apply time:
- Owner approval: `<audit/report path>` + exact item IDs

## Applied Items

| Item ID | Origin | Result | Durable home | `_pending.md` closure |
| --- | --- | --- | --- | --- |

`Origin` 是 `pending-registry` 或 `gap-catching`；`pending-registry` item 必须同时关闭来源 `_pending.md` 里对应的登记行，`gap-catching` item 必须先补一条登记再关闭——两者在这张表的最后一列都要写明关闭结果，不能只写自己的 `done.json` 而不动 `_pending.md`。

## Deferred / Conflict / Rejected

| Item ID | Disposition | Reason | `_pending.md` state |
| --- | --- | --- | --- |

## Destructive Apply（如适用）

| 路径 / Package ID | 操作 | Owner 授权引用 | 执行前重新核对结果 |
| --- | --- | --- | --- |

只在有独立 destructive-apply 授权时填写；普通 item 批准不能覆盖这类操作。

## Verification

- Approved item to diff mapping:
- Canonical owner / pointer check:
- Link / anchor checks:
- Project-specific checks:
- `git diff --check`:

## Scope Attestation

Only owner-approved report item IDs were applied. Destructive operations were only executed against an independent, path/package-id-scoped destructive-apply approval. Unapproved items were not included.
