# [Attempt ID | Task ID | Ticket ID] Progress Ledger

> This is an earned recovery ledger, not a second status or acceptance fact source. See
> [Impl-Package Composition Contract](../../../skills/impl-package/references/impl-package-composition-contract.md).

Kind：[attempt / task / ticket]
创建：[YYYY-MM-DD]
Attempt ID：
Canonical execution source：[this attempt recovery ledger / dag.md / patch DAG / tickets/<ticket>.md]
Acceptance source：[tickets/<ticket>.md / spec.md + plan Execution Record + gate.md]

Create `tasks/<attempt-id>-progress.md` with `Kind: attempt` only for a tickets=false, dag=false attempt whose interruption, independent handoff, external gate or blocker earns recovery state. Create task ledgers as `tasks/Tn-progress.md`; create a whole-ticket ledger as `tasks/<ticket-id>-progress.md` only under its recovery/transfer trigger. An attempt ledger must not invent T<n>, duplicate plan verification, or become an acceptance conclusion.

## Restore Context

- Owner / handoff target:
- Last meaningful update:
- Canonical status at restore:
- Evidence reconciled:
- Open prerequisite / external gate:

## Evidence

- [command / observation / smoke marker / record ID / cleanup]

## Revalidation

- Upstream rework or reopened input:
- Affected dependent evidence:
- Required recheck before dependency may release:

## Next

1. [next action]
