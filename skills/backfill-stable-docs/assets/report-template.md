# Stable Docs Backfill Audit Report

- Phase: `audit`
- Generated:
- Project:
- Source HEAD / dirty baseline:
- Target branch / resolved commit:
- Config source / digest:
- `_pending.md` roots discovered:
- Config gaps (ambiguous/missing `_pending.md`):
- System pending cold-start owner decisions:

## Executive Decision

- Candidates from `_pending.md` (primary channel):
- Candidates from gap-catching (fallback):
- Already covered:
- Conflicts:
- No-delta modules:
- Recommended apply boundary:

## Stable Authority Coverage

| Layer | Stable root / owner | Pending path | Discovery status | Result | Candidate IDs | Evidence note |
| --- | --- | --- | --- | --- | --- | --- |

每个 configured system/context/module stable root 必须出现；省略的 `contextKnowledge` 不生成虚拟行。多个 root 共用一个 pending register 时保留各 root 的 coverage，但登记候选只消费一次。Discovery status 使用 `ok`、`cold-start`、`missing`、`ambiguous`；`cold-start` 是非阻塞 owner decision，不算 config gap。Result 仅用 `candidate`、`already-covered`、`conflict`、`no-delta`。

## Candidate Deltas

| ID | Origin | Module | Destination | Pending ref (if any) | Statement | Current evidence | Existing coverage | Risk | Recommendation | Confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

`Origin` 只用 `pending-registry`（来自 `_pending.md` 主渠道）或 `gap-catching`（gate 已 terminal 但没有对应登记，重新发现）。`pending-registry` 行必须填 `Pending ref`，指向来源 `_pending.md` 文件和其中的登记行。

## Pending Register Cross-Check

| `_pending.md` 路径 | 登记条目数（未关闭） | 已核验仍成立 | 需要 owner 裁决 |
| --- | --- | --- | --- |

## Gap-Catching Findings

| Source package | 为何没有对应登记 | Affected module | 建议 disposition |
| --- | --- | --- | --- |

## Package Retirement Candidates

| Package ID | Gate ledger 终态 | Target branch Git evidence | Pending closure | 吸收去向 | Inbound references | 剩余目录内容 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |

只报告候选，不在 audit 里清理；执行见 [package retirement runbook](../references/package-retirement-runbook.md)。

## Conflicts And Owner Decisions

| ID | Competing authorities | Safe invariant | Decision needed |
| --- | --- | --- | --- |

## Current System Knowledge Boundary

| Affected stable doc path | Current contract disposition | Retirement / future decision | Verification |
| --- | --- | --- | --- |

Canonical system docs 不保留历史/退役能力的兼容说明。只有 owner 已批准的 future capability 才可登记 TODO，且必须明确为非当前合同、写明目标与前提。

## Proposed Apply Order

仅列 item ID、目标和依赖；audit 不执行。破坏性操作（含 Package Retirement）单独列出，需要独立的 destructive-apply 批准。

## Read-only Attestation

除本报告文件（写入配置 `records.reports` 目录）或用户明确指定的外部 output directory 外，未修改 stable docs、`_pending.md`、`done.json`、source packages 或代码。
