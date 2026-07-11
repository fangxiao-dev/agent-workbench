---
name: requirement-alignment
description: Impl-Package 体系的需求对齐与 Spec 阶段：当新建或变更需求需要在 feature design、specification 或 implementation planning 前完成对齐时使用；拥有必过的 Design / Spec gates 及其 design.md / spec.md。
---

# Requirement Alignment

Run the two mandatory entry gates for an Impl-Package: Design, then Spec. The gates are
equal requirements. Design is never skipped, even when its standalone `design.md` would
be empty ceremony.

Repository instructions and discovered project conventions determine knowledge sources.
Do not assume a product domain or impose another workflow's document destinations.

## Owned Artifacts

Use `docs/implementations/<package-id>/` as the canonical package root. A package-id is
`YYMMDD-<topic-slug>` (UTC creation date), for example
`260711-catalog-readiness`; it is a directory identity, not a mutable title.
This skill owns:

- `design.md`, required whenever Design is blocked and optional only for a lightweight
  Design-passed path whose evidence fits in the spec Design Gate Record;
- `spec.md`, the required point-in-time implementation contract.

Use [assets/templates/design.md](./assets/templates/design.md) and
[assets/templates/spec.md](./assets/templates/spec.md). Do not publish a tracker spec or
create a second spec for the same package. `feature-impl-planning` consumes the gated
`spec.md`; it does not own or synthesize a replacement.

Omitting standalone `design.md` is legal only after Design evaluates `PASSED` and the
lightweight evidence fits in the `Design Gate Record` at the top of `spec.md`. “No design
file” never means “no Design step.” Requirement source and alignment provenance belong in
`design.md`; on the lightweight passed path, preserve their minimum durable form in that
same `Design Gate Record`.

This skill may append to package `findings.md` when research establishes a fact, risk, or
constraint that later stages can reuse. Keep ordinary research narrative in `design.md`;
do not create an empty findings ledger when there is no substantive cross-stage finding.
`dev-with-track` remains the owner of the findings format and final consolidation.

## Package Identity

For a **new** implementation package, choose a short semantic `topic-slug`, then generate
one immutable `package-id` from the current UTC creation date:

```text
<package-id> = YYMMDD-<topic-slug>
```

Record both values in the Design/Spec metadata before creating downstream artifacts. Check
whether the exact directory already exists; if it does, append `-02`, `-03`, and so on
until it is unique. Use the resulting package-id in every package path, cross-package
reference, truth pointer, and handoff. This prevents distinct short-lived changes with the
same topic from sharing a workspace.

For an existing package, retain its current directory name as its legacy or timestamped
package-id. Never rename it merely to add a timestamp. A post-gate patch remains in that
owning package-id; it is not a new implementation package.

## Discover Project Knowledge

1. Read every applicable `AGENTS.md` for the target repository and path.
2. Read the repository's project-context entry point when present or referenced.
3. Follow its routing to relevant product, architecture, domain, integration,
   operational, decision, testing, and nearby implementation records.
4. Inspect focused code and tests where needed to establish current behavior.
5. Record sources checked and expected knowledge that was absent.

Use the repository's vocabulary and source-of-truth hierarchy. If durable project
knowledge should change, propose the change against the discovered authoritative source
and wait for owner approval; never invent a fixed long-lived destination.

## Gate 1: Design (Required)

Design turns the requirement and repository facts into a decision-ready destination. Use
the eight-section Design Research structure in the design template. The analysis and gate
judgment always happen before `spec.md` is created. A passed lightweight Design may omit
the file; a blocked Design may not.

The Design gate passes only when all of these are verifiably true:

- **Destination is answerable:** intended outcome, affected system boundary, and handoff
  to the implementation contract are explicit.
- **Repository fit is evidenced:** authority sources and current-state facts have been
  checked; conflicts and missing knowledge are named.
- **Choices are decided:** material options and trade-offs have a selected direction and
  rationale, or an explicit owner decision blocks the gate.
- **Open Questions are non-blocking for Spec:** every question is resolved, explicitly
  deferred with owner and consequence, or proven not to affect the contract.
- **Owner Decisions are durable:** resolved and outstanding decisions are written in
  `design.md`, or in `spec.md`'s `Design Gate Record` when no design file is earned.

If any criterion fails, create or update `design.md`, record `Design Gate: BLOCKED`, the
missing evidence, and the owner decision required, and do not create `spec.md` or begin
the Spec gate.

### Design Boundary

- `Decisions / Rationale` records choices and why they were selected. Put behavior,
  state, interface, and failure semantics only in `spec.md`; do not copy those contracts
  into design.
- `Backfill Candidates` is a non-binding research hint. It is not a durable-delta
  register, does not authorize stable-document edits, and need not be merged into spec.
  Canonical durable-delta capture happens at the execution gate and downstream backfill.

## Gate 2: Spec (Required)

Start only after the Design gate passes. Synthesize the point-in-time contract from:

- repository facts and authoritative knowledge, distinguishing facts from assumptions;
- user-facing semantics and agreed outcomes, using repository domain language;
- selected seam/interface decisions and the highest practical behavioral testing seams;
- owner decisions from Design, without copying research narration into the contract.

Use the thick eight-section spec template. The Spec gate passes only when:

- all eight contract sections are present and substantive for the change, including
  Error Boundaries / Failure Recovery and Constraint Contracts;
- behavior, state transitions, workflows, boundaries, and failure recovery are
  internally consistent and actionable without reading the plan;
- Acceptance Semantics maps each promised outcome or constraint to observable evidence
  and names any manual verification owner;
- `Composition: tickets=<true|false>, dag=<true|false>` is justified by the two
  independent earn conditions, never by S/M/L sizing;
- blocking owner decisions and unresolved contract ambiguity are zero.

If any criterion fails, record `Spec Gate: BLOCKED` with the exact missing contract or
decision. Do not hand off to planning. A passing spec records `Spec Gate: PASSED`, date,
evidence, and approver/owner.

The spec must not contain a `Stable Doc Backfill Map`, durable-delta queue, worker task
steps, or tracker publication metadata.

## Workflow

1. Announce use of requirement-alignment; for a new package assign a topic slug and an
   immutable date-prefixed package-id, or identify the owning existing package-id for a
   patch/follow-up.
2. Discover authoritative project knowledge before detailed clarification.
3. Ask one focused question at a time for unresolved intent, scope, constraints, success
   criteria, trade-offs, or owner decisions.
4. Run Design Research, present the selected direction plus blockers, and evaluate the
   Design gate before creating `spec.md`.
5. If Design is blocked, create or update `design.md` with provenance, readiness evidence,
   blockers, and owner decisions; stop without creating `spec.md`.
6. If Design passes, either persist its substantive research in `design.md`, or take the
   lightweight path: create `spec.md` and write the minimum provenance, readiness, and
   owner-decision evidence into its Design Gate Record. Append reusable, verified
   cross-stage facts/risks/constraints to an already-needed `findings.md`; do not create
   it for ordinary research narration.
7. Synthesize the eight-section `spec.md` and evaluate the Spec gate. Stop when it is
   blocked.
8. After both gates pass, hand off the same `spec.md` to `feature-impl-planning`; do not
   create another spec or publish to a tracker.

## Alignment Proposal

Before writing artifacts or editing long-lived knowledge, present:

```markdown
## Requirement Alignment Proposal

### Focused Requirement
<requirement using repository terms>

### Authoritative Knowledge Fit
- Product intent fit:
- Architecture and constraints fit:
- Current-state facts:
- Sources checked:
- Expected knowledge not found:

### Drift Or Conflict Check
- Confirmed alignment:
- Possible drift:
- Out of scope:

### Design Direction
- Selected option and rationale:
- Open questions:

### Proposed Durable Knowledge Changes
- File / change / reason, or "None"

### Owner Decisions
- <decision, owner, and blocking effect, or "None">

### Recommended Next Step
- Persist Design gate and proceed to Spec
- Stop for owner decision
```

## User-Facing Output

Return only the topic slug, package-id and package path, both gate results and evidence
locations, changed files (including `findings.md` only when appended), remaining owner
decisions, and whether the package may enter implementation planning. Do not describe a
blocked gate as completed or paste full artifacts after they have been written.

Artifact `Status` and gate `Result` must agree: a Passed status requires `PASSED`, a
Blocked status requires `BLOCKED`, and neither may be inferred from prose alone.
