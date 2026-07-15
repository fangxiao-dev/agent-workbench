# Stable Docs Backfill Report

- Mode: `report`
- Generated:
- Project:
- Branch / HEAD:
- Dirty baseline:
- Method Activation Ref:
- Project Source Watermark:
- Source HEAD:
- Carry-forward input:
- Module inventory source:
- Sources inspected:

## Executive Decision

- Candidates:
- Already covered:
- Conflicts:
- No-delta modules:
- Recommended apply boundary:

## Module Coverage

| Module | Result | Candidate IDs | Evidence note |
| --- | --- | --- | --- |

每个 module 必须出现一次。Result 仅用 `candidate`、`already covered`、 `conflict`、`no delta`。

## Candidate Deltas

| ID | Module | Destination | Constraint class | Statement | Source / authority | Current evidence | Existing coverage | Risk | Recommendation | Confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Pending Register

| Pending ID | Proposed destination | Decision | Reason / missing authority |
| --- | --- | --- | --- |

## Gate Omissions And Unowned Commits

| Source | Affected module | Durable delta | Disposition |
| --- | --- | --- | --- |

## Carry-Forward Sources

| Package ID | Reason | Tree / evidence identity | Next disposition gate |
| --- | --- | --- | --- |

## Conflicts And Owner Decisions

| ID | Competing authorities | Safe invariant | Decision needed |
| --- | --- | --- | --- |

## Current Top-Level Knowledge Boundary

| Affected top-level path | Current contract disposition | Retirement / future decision | Verification |
| --- | --- | --- | --- |

`CONTEXT.md` 与 `docs/top-level-knowledge/**` 不保留历史/退役能力的兼容说明。只有 owner 已批准的 future capability 才可登记 TODO，且必须明确为非当前合同、写明目标与前提。

## Tombstones And References

| Source path | Final target | Status | Recommendation |
| --- | --- | --- | --- |

## Proposed Apply Order

仅列 item ID、目标和依赖；report 不执行。

## Watermark

- Current:
- Audited through:
- Proposed next watermark after approved apply:
- Carry-forward after proposed advancement:
- Blockers:

## Read-only Attestation

除本报告文件外，未修改 module docs、pending、watermark、source packages 或代码。
