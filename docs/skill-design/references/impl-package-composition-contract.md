# Impl-Package Composition Contract

> **Normative shared contract.** This file encodes the approved implementation
> rules in `2026-07-10-impl-package-system-design.md` for use by the main-chain
> skills. `create-task-dag`, `impl-planning`, and `dev-with-track` must
> reference it and must not redefine these semantics locally.

## 1. Package identity

For a new implementation package, `req-align` creates an immutable package-id
in the form `YYMMDD-<topic-slug>` from the UTC creation date, with a `-02`, `-03`… suffix only when the
exact name already exists. The package root is `docs/implementations/<package-id>/`.
`topic-slug` is a human-readable subject label; package-id is the identity that paths,
truth pointers, handoffs, and cross-package references must use. Existing directories
without the timestamp are legacy package-ids and remain valid; a post-gate patch reuses
the owning package-id rather than creating a second package.

## 2. Composition and canonical status homes

`spec.md` records exactly one composition declaration:

```text
Composition: tickets=<true|false>, dag=<true|false>
```

| Composition | Execution-state fact source | Ticket-acceptance fact source | Allowed projection |
| --- | --- | --- | --- |
| `tickets=false, dag=false` | `plan.md` checklist; a justified task progress ledger may hold local recovery evidence | N/A; acceptance evidence is in `spec.md` / `gate.md` | None |
| `tickets=true, dag=false` | ticket files and justified progress ledgers | `tickets/<ticket>.md` | No `dag.md` may be created only as a ticket index |
| `tickets=false, dag=true` | `dag.md`; justified task progress ledgers hold detailed recovery evidence | N/A; acceptance evidence is in `spec.md` / `gate.md` | None |
| `tickets=true, dag=true` | `dag.md`; justified task progress ledgers hold detailed recovery evidence | `tickets/<ticket>.md` | `dag.md` may show a read-only ticket-status projection, labelled as a projection |

One state has one fact source. A projection must name its source and must never
overwrite an acceptance conclusion. Cross-session recovery earns a progress ledger,
not a DAG; a DAG is earned only when execution dependencies or coordination need an
explicit graph.

### Dispatch shorthand (non-authoritative alias)

For faster human dispatch, four optional shorthand names may expand to a composition.
They are aliases only, never a sizing gate. The `Composition:` line stays the sole source
of truth and the earn conditions decide what actually exists.

| Shorthand | Expands to | Meaning |
| --- | --- | --- |
| `S` | `tickets=false, dag=false` | spec + plan, execute directly — the floor, not a tier |
| `M` | `tickets=true, dag=false` | acceptance slices earned |
| `L` | `tickets=true, dag=true` | slices plus an execution graph |
| `D` | `tickets=false, dag=true` | no slices, but non-trivial execution dependencies |

Authority flows one way: a shorthand expands into `tickets=/dag=`; it never overrides
them. If a requested shorthand and the earned composition disagree — for example `L` was
dispatched but only one acceptance slice is earned — the earn conditions win: correct the
label, never manufacture a ticket or DAG to match the name. `spec.md` always records the
canonical `Composition: tickets=<...>, dag=<...>`, not the shorthand.

## 3. Typed blockers and readiness resolution

Every ticket dependency is typed:

```text
Blocked by:
- implementation: <ticket-id>
- acceptance: <ticket-id>
- release: <ticket-id>
```

At ticket level, only an `implementation` edge determines whether an execution unit
is actionable. A DAG task also has its own `Depends on` edges; ticket readiness never
releases a task dependency by itself. Before selecting work, resolve both static graphs
deterministically:

```text
actionable = unit is not in a completed/cancelled/superseded terminal state
             AND every ticket-level implementation blocker is in a dependency-releasing terminal state
             AND (when unit is a DAG task) every `Depends on` task is in a dependency-releasing DAG state
             AND the unit's owner, external gate, and environment prerequisites hold
```

- A dependency-releasing ticket or DAG state is `DONE`. `WAIVED` or `SUPERSEDED`
  releases it only with replacement evidence and an impact note.
- Non-releasing DAG states are `PENDING`, `READY`, `RUNNING`, `NEEDS_SEAM`,
  `FAILED`, `BLOCKED`, and `NEEDS-REVALIDATION`. `NEEDS-REVALIDATION` is explicit:
  a previously completed output may be inspected or retested, but no dependent may
  proceed on its old evidence until it is returned to a dependency-releasing state.
- Worker return status maps to the DAG state as follows: `DONE` becomes `DONE` only
  after its `Done when` evidence is recorded; otherwise it remains `RUNNING`.
  `DONE_WITH_CONCERNS` becomes `NEEDS-REVALIDATION`; `NEEDS_SEAM` becomes
  `NEEDS_SEAM`; `BLOCKED` becomes `BLOCKED`. A main-session integration or review
  finding may likewise move a task to `NEEDS-REVALIDATION`.
- Publish validates missing references and cycles across typed ticket edges. Before
  execution, DAG validation validates missing `Depends on` references and cycles across
  task edges.
- Multiple actionable units are selected in documented ticket/task order; this is not
  worker allocation, frontier scheduling, leasing, or a concurrency lock.
- When an upstream ticket or task result is reopened or reworked, dependent evidence
  and dependent DAG tasks become `NEEDS-REVALIDATION` until explicitly rechecked.
- Restore reconciles document state against evidence before selecting work; evidence wins
  over a stale status record.

## 4. Task-to-acceptance traceability and seam ownership

`dag.md` task records use these fields:

```markdown
### T<n>: <task title>
- contributes-to: <acceptance-target>[, ...]
- enables: <acceptance-target>[, ...]   # only for infrastructure work
- seam: none | <seam-id>
- seam execution owner: <main session | named owner>
```

Only for the `tickets=false, dag=false` composition, a no-DAG `plan.md` task section
uses the same acceptance fields with `seam: none`; it must not name a seam execution
owner.

For `tickets=true, dag=false`, there is deliberately no task-decomposition artifact and
the plan remains task-free. Each ticket instead carries an AC-level evidence plan:

```markdown
| AC ID | Evidence producer or manual verification owner | Planned evidence |
| --- | --- | --- |
| AC-1 | <implementation evidence | named manual owner> | <test, observation, or record> |
```

This is acceptance traceability, not worker ownership, a task checklist, or a file-level
implementation plan.

Every ticket and a no-ticket spec define stable `AC-<n>` identifiers, unique within that
artifact. An acceptance target uses this grammar:

```text
ticket-id         := [a-z0-9][a-z0-9-]*
ac-id             := AC-[1-9][0-9]*
acceptance-target := <ticket-id>:<ac-id> | spec:<ac-id>
```

Use `<ticket-id>:<AC-id>` when tickets are earned and `spec:<AC-id>` otherwise. A
`contributes-to` / `enables` reference is valid only when its target artifact and AC id
exist. An AC may name a task producer only when a task artifact exists; otherwise it
names ticket-local implementation evidence or a manual owner.

For every seam, record all three owners. `plan.md` uses this canonical seam contract
record:

```markdown
### Seam <seam-id>: <title>
- Seam ID: <seam-id>
- Contract owner: <plan owner or named owner>
- Acceptance owner: <main session or named integration owner>
- Affected acceptance targets: <acceptance-target>[, ...]
- Interface / compatibility window:
- Integration and rollback contract:
```

| Role | Canonical home | Responsibility |
| --- | --- | --- |
| Contract owner | `plan.md` | Interface, compatibility window, integration and rollback contract |
| Execution owner | `dag.md` task | Makes the seam change and records local evidence |
| Acceptance owner | main session or named integration owner | Maps seam evidence to every affected acceptance target |

The plan seam record is the canonical home for `Seam ID`, contract owner, acceptance
owner, and affected acceptance targets. A DAG task records only the matching seam ID
and its seam execution owner; it must not recreate or replace the plan's contract or
acceptance ownership.

An execution seam always earns `dag=true`; therefore a no-DAG task has `seam: none`.
`plan.md` may still define the seam contract, but it cannot invent a light-weight seam
execution owner outside a DAG.

Validation gates:

1. Before execution starts, every acceptance target has a planned evidence producer or a named
   manual-verification owner.
2. Before a ticket closes, or before a no-ticket package gate closes, every relevant
   acceptance target has direct evidence. All contributing tasks being `DONE` never
   implies acceptance automatically.
3. A ticket or no-ticket package depending on an unaccepted seam cannot close.

## 5. Controlled composition upgrade

Composition may only be upgraded through a recorded migration; it never creates
per-ticket patch plans.

```markdown
## Composition Migration
- Previous: tickets=<true|false>, dag=<true|false>
- New: tickets=<true|false>, dag=<true|false>
- Reason and date:
- Content moved to canonical home:
- Relocation pointer left at:
- Fact-source / dependency / AC-coverage verification:
```

The migration preserves confirmed semantics, moves obsolete task/status content to the
new canonical home, leaves a relocation pointer at the old location, and removes the
old maintenance entry point. It must not leave two writable truth sources.

## 6. Stage 7 durable-delta closing contract

The only durable-delta capture path is:

```text
gate.md Durable Deltas table -> project _pending.md -> backfill report/apply
```

`design.md` Backfill Candidates are non-binding research hints. `spec.md` contains no
stable backfill map or durable-delta queue.

For each durable delta, the gate records `delta-id`, `destination`, `source`,
`statement`, affected modules, `authority`, and `evidence`:

```markdown
| Delta ID | Destination | Source | Statement | Affected modules | Authority | Evidence |
| --- | --- | --- | --- | --- | --- |
```

The matching `_pending.md` entry includes the same `delta-id` and destination. Its
dedupe key is:

```text
<destination>|<delta-id>
```

Before a gate with durable deltas closes, verify all of the following:

1. each gate-table delta is registered in `_pending.md` using the dedupe key;
2. every affected module spec has a `Pending deltas: <package-id>` truth pointer;
3. a missing target module spec has the required stub before the pointer is written.

With no durable delta, the gate records `none` and a reason. Backfill report treats a
missing gate capture, pending entry, or unowned commit as a capture gap, never as proof
of no change.

## 7. Shared validation checklist

Before an affected skill may declare its work ready:

- exactly one composition declaration is present and its artifacts match the four-state
  table;
- all typed ticket dependencies and all DAG `Depends on` references exist, and neither
  graph has a cycle; a task is actionable only when its ticket implementation blockers
  and its DAG dependencies are in dependency-releasing states;
- every ticket AC, and every no-ticket spec AC, has a stable ID and an evidence
  producer/manual owner; every `contributes-to` / `enables` reference parses as an
  acceptance target and resolves to that artifact and AC; every seam plan record has
  its ID, contract owner, acceptance owner, and affected acceptance targets, and every
  execution seam has a DAG execution owner and `dag=true`;
- every composition migration has a relocation pointer and no duplicate writable state;
- each durable delta has a unique `<destination>|<delta-id>` key which matches its
  `_pending.md` entry; a closing gate has either the complete durable-delta path or
  `none` plus a reason.
