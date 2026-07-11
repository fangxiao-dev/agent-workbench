# [Implementation Name] DAG

> Create this artifact only when `Composition: ..., dag=true`. Its field semantics,
> readiness and validation are defined by the shared
> [Impl-Package Composition Contract](../../skill-design/references/impl-package-composition-contract.md).

状态：[PENDING / READY / RUNNING / NEEDS_SEAM / BLOCKED / FAILED / NEEDS-REVALIDATION / DONE / WAIVED / SUPERSEDED]
创建：[YYYY-MM-DD]
Spec：[spec.md](spec.md)
Plan：[plan.md](plan.md)
Findings：[findings.md](findings.md)
Gate：[gate.md](gate.md)

`dag.md` is the canonical execution-state source only for an earned DAG. It is not a
ticket acceptance source. If tickets are also earned, any ticket state below is a
read-only projection that names its `tickets/<ticket>.md` source.

## Shared Contracts

- Shared composition contract: [impl-package-composition-contract.md](../../skill-design/references/impl-package-composition-contract.md)
- [contract / DTO / route prop / external smoke protocol]

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

`contributes-to`, `enables`, and seam fields are validated against the shared contract;
do not duplicate a seam contract or acceptance owner here.

## DAG Board

| Task | Depends on | Owner | Status | Readiness / blocker | Evidence | Progress | Seam |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | [Tn / none] | [owner] | [state] | [prerequisite] | [path/link] | [ledger/N/A] | [seam ID/none] |

## Ticket Status Projection (only tickets=true)

> Projection only. Acceptance fact source remains the linked ticket file; update it there.

| Ticket | Acceptance source | Projected execution view | Last checked |
| --- | --- | --- | --- |
| [ticket-id] | [tickets/<ticket>.md](tickets/<ticket>.md) | [state] | [YYYY-MM-DD] |

## Validation and Last Update

- [ ] All `Depends on` references resolve and the task graph is acyclic.
- [ ] Every task acceptance target resolves to a ticket/spec AC.
- [ ] Every execution seam has a matching plan seam record and execution owner.
- [YYYY-MM-DD] [meaningful status/evidence/revalidation change]
