# [Task ID or Ticket ID] Progress Ledger

> This is an earned recovery ledger, not a second status or acceptance fact source. See
> [Impl-Package Composition Contract](../../skill-design/references/impl-package-composition-contract.md).

Kind：[task / ticket]
创建：[YYYY-MM-DD]
Canonical execution source：[dag.md / plan.md checklist / tickets/<ticket>.md]
Acceptance source：[tickets/<ticket>.md / spec.md + gate.md]

Create for a task only when the task-ledger trigger applies. Create for a ticket only when
the whole ticket is independently resumed or transferred. A ticket ledger may index tasks
and local recovery context but must not duplicate a task ledger or state an acceptance
conclusion.

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
