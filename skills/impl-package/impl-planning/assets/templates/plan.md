# [Attempt Name] Implementation Plan

Created:
Attempt ID: <initial | YYYYMMDD-HHMM-patch-topic>
Design Revision: D<n>
Spec Revision: S<n>
Plan Revision: P<n>
Composition: tickets=<true|false>, dag=<true|false>
Package ID:
Binding Validation at Publication: Pending | Passed
Design: [design.md](design.md) | lightweight Design record in spec
Spec: [spec.md](spec.md)
Gate Ledger: [gate.md](gate.md)

> design/spec 是当前 contract SoT。本 plan 只记录本 attempt 的执行策略、验证计划和过程证据。terminal gate verdict 后冻结。

## Summary

## Inputs And Authority

- Requirement / patch source:
- Current module knowledge checked:
- Focused code/test facts:
- D/S gate evidence:
- Previous terminal gate entry (patch only):
- Module Knowledge Watermark（本 attempt 打开时，design/spec 引用的每份 module-knowledge 文件的 `git log -1` commit SHA；下次 attempt 打开时用来对账是否已被别的改动推进）：

## Composition Decision

- Tickets earned: yes | no
- Tickets rationale:
- DAG earned: yes | no
- DAG rationale:
- Execution-state source:
- Acceptance-state source:

## Execution Strategy

- Ordered implementation approach:
- Concrete migration/integration operations:
- Rollout/rollback operations:
- Dependencies and prerequisites:
- Target branch:
- Integration order: gate-before-merge | owner-approved pre-gate integration
- Pre-gate integration owner decision evidence: <N/A | evidence>

<!-- 稳定 interface、seam contract、compatibility、global constraints 和 Acceptance Semantics 不写在这里；缺失时先修订 spec。 -->

## Planned Verification

| Policy / scenario source | Selected check | Expected result | Evidence owner |
| --- | --- | --- | --- |

<!-- 引用权威 policy；不要复制通用 Data Safety、UI Evidence、Real Route Safety checklist。 -->

## Execution Record

<!-- Append-only。旧 entry 不改；补证新增 ER-n。 -->

### ER-<n>

- Recorded at:
- Design / Spec / Plan revision:
- Check or command:
- Result:
- Evidence path:
- Residual risk / follow-up:

## Attempt Artifact Handoff

- Ticket set: <paths | N/A>
- DAG: <dag.md or patch-dag path | N/A>
- Progress ledger: <path | N/A until trigger>
- Findings inbox: [findings.md](findings.md)

## Plan Revision History

<!-- Current and historical P content bindings live in the internal .impl-package/revision-bindings.json sidecar. Do not require the owner to read it. Any earned ticket/DAG still citing a superseded P<n> here is NEEDS-REVALIDATION until reconciled. -->

| Previous | New | Strategy/Composition/verification change | Reason | Artifact relocation | Date |
| --- | --- | --- | --- | --- | --- |

## Patch Delta

<!-- Initial attempt 删除本节。 -->

- Previous terminal gate entry:
- Drift classification: implementation-only | behavior contract | design direction
- Reused or updated D/S revisions:
- Delta from accepted behavior:
- Regression scope:
