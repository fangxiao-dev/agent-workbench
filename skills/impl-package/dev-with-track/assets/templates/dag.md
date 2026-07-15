# [Implementation Name] DAG

> Create this artifact only when `Composition: ..., dag=true`. Its field semantics,
> readiness and validation are defined by the shared
> [Impl-Package Composition Contract](../../../skills/impl-package/references/impl-package-composition-contract.md).

状态：[PENDING / READY / RUNNING / NEEDS_SEAM / BLOCKED / FAILED / NEEDS-REVALIDATION / DONE / WAIVED / SUPERSEDED / RETIRED]
创建：[YYYY-MM-DD]
Attempt ID：
Plan Revision：P<n>
<!-- plan 升级到更新的 P 号后，本 DAG 若仍标着旧 P 号，视为 NEEDS-REVALIDATION。先按 P delta 定位受影响节点；未受影响节点可批量确认后机械更新本字段，不重画整张 DAG。 -->
Spec：[spec.md](spec.md)
Plan：[current attempt plan](<plan-path>)
Findings：[findings.md](findings.md)
Gate：[gate.md](gate.md)

`dag.md` is the canonical execution-state source only for an earned DAG. It is not a ticket acceptance source. If tickets are also earned, any ticket state below is a read-only projection that names its `tickets/<ticket>.md` source.

## Contract References

- Shared composition contract: [impl-package-composition-contract.md](../../../skills/impl-package/references/impl-package-composition-contract.md)
- Spec revision and seam IDs:
- [DTO / route prop / external smoke protocol source]

## Task Records

### T1: [task title]

- Depends on: [Tn / none]
- Document order: [number]
- Owner: [main session / named owner]
- Status: [PENDING / READY / RUNNING / NEEDS_SEAM / BLOCKED / FAILED / NEEDS-REVALIDATION / DONE / WAIVED / SUPERSEDED]
- Done when: [specific evidence]
- contributes-to: [<ticket-id>:<AC-id> / spec:<AC-id>]
- enables: [<acceptance-target> / none]
- seam: [none / <seam-id>]
- seam execution owner: [main session / named owner; `none` only when seam is none]
- Progress ledger: [tasks/T1-progress.md / N/A]

`contributes-to`, `enables`, and seam fields are validated against the shared contract; do not duplicate a spec seam contract or acceptance owner here.

## DAG Board

| Task | Depends on | Owner | Status | Readiness / blocker | Evidence | Progress | Seam |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | [Tn / none] | [owner] | [state] | [prerequisite] | [path/link] | [ledger/N/A] | [seam ID/none] |

## Ticket Status Projection (only tickets=true)

> Projection only. Acceptance fact source remains the linked ticket file; update it there.

| Ticket | Acceptance source | Projected execution view | Last checked |
| --- | --- | --- | --- |
| [ticket-id] | [tickets/<ticket>.md](tickets/<ticket>.md) | [state] | [YYYY-MM-DD] |

## Verification Gates

<!-- 只记录 task/DAG 特有的前置条件与到 plan Planned Verification 的指针；不要复制通用 policy checklist。 -->

- Plan verification source: [current attempt plan](<plan-path>#planned-verification)
- Task/DAG-specific prerequisite or external gate:

## Validation and Last Update

- [ ] All `Depends on` references resolve and the task graph is acyclic.
- [ ] Every task acceptance target resolves to a ticket/spec AC.
- [ ] Every execution seam has a matching spec seam contract and execution owner.
- [YYYY-MM-DD] [meaningful status/evidence/revalidation change]
