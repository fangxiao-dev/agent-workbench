# Stable Docs Backfill Verification Record

- Phase: `verify`
- Project:
- Config source / digest:
- Audit/apply evidence referenced:

## Result

- Checks:
- Passed:
- Failed:
- Verdict: `passed` / `failed`

## Deterministic Checks

| Check | Result | Evidence / failure |
| --- | --- | --- |

`configured-paths`、`pending-discovery`、`canonical-links`、`audit-contract`（如提供 `--audit-json`）、`inventory-candidates` 各占一行。

## Semantic Checks

| Item / boundary | Result | Evidence / owner decision |
| --- | --- | --- |

## `_pending.md` Reconciliation

- 各处 `_pending.md` 是否仍能唯一定位（无歧义/缺失）：
- 未关闭登记数：
- 未解决 owner decision 或 evidence gap：

## Package Retirement Candidates Surfaced

| Package ID | 结构性条件（gate 终态 + 无未关闭登记 + 已在 done record）是否满足 | 仍需 agent 核实的第三条 |
| --- | --- | --- |

## Remaining Blockers

列出失败检查与仍需 owner 决策的条目。Verify 通过不自动表示整个开发任务、合入或发布 closed，也不表示 Package Retirement 候选已经可以清理。
