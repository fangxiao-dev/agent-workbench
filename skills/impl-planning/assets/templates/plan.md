# [Attempt Name] Implementation Plan

Status: Draft | Active | Frozen
Created:
Attempt ID: <initial | YYYYMMDD-HHMM-patch-topic>
Design Revision: D<n>
Spec Revision: S<n>
Plan Revision: P<n>
Composition: tickets=<true|false>, dag=<true|false>
Package ID:
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

| Previous | New | Strategy/Composition/verification change | Reason | Artifact relocation | Date |
| --- | --- | --- | --- | --- | --- |

## Patch Delta

<!-- Initial attempt 删除本节。 -->

- Previous terminal gate entry:
- Drift classification: implementation-only | behavior contract | design direction
- Reused or updated D/S revisions:
- Delta from accepted behavior:
- Regression scope:
