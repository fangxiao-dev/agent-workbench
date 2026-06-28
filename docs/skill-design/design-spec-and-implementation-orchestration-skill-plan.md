# Design Spec And Implementation Orchestration Skill Plan

Date: 2026-06-28

## Goal

Split the current spec-plus-implementation-planning workflow into two lean skills:

1. A durable design-spec skill that captures business semantics, state machines, crash points, and observable invariants without producing a full implementation plan.
2. A lean implementation orchestration skill that turns an approved design spec into issues and an orchestration plan by delegating definition-heavy work to `to-issues` and `orchestrator`.

The intended workflow is:

```text
design-spec
  -> design review
  -> implementation-orchestration
  -> to-issues
  -> orchestrator
  -> implementation
  -> review against design-spec invariants
```

## Proposed Skill 1: `design-spec`

### Purpose

Create a durable product/engineering design contract before implementation planning.

This skill answers:

- What business capability are we changing?
- What domain states exist?
- What transitions are allowed?
- What invariants must never be violated?
- What crash points exist?
- What can readers observe after each crash point?
- What retry, compensation, and reconciliation semantics are required?
- What adapter contract must Lark/local/future PostgreSQL satisfy?
- What old-data, migration, and cutover boundaries are explicitly accepted?
- What acceptance probes prove the design is respected?

### Non-Goals

This skill must not produce a full implementation plan.

It must not include:

- File-by-file change lists.
- Function-level instructions.
- Worker assignment.
- GitHub issue breakdown.
- Worktree orchestration.
- Local helper names that encode a specific adapter implementation.
- Long code snippets or mock implementations.
- Commit sequencing.

### Independence Rule

The new skill should be treated as a standalone skill. Its `SKILL.md` should not reference or depend on the existing `feature-impl-planing` skill.

The migration history may be documented outside the skill, but the runtime skill contract should present `design-spec` as a new first-class workflow.

### Output Contract

The skill writes one durable Markdown document, preferably under a project design/spec path chosen by the repository.

Spec filenames should be stable and should not include a timestamp. A durable design spec is expected to be revised in place as the long-lived contract for the feature.

Suggested default:

```text
docs/func-design/<feature>-design-spec.md
```

If the repository has no design folder, fallback:

```text
docs/design-specs/<feature>-design-spec.md
```

Required sections:

```markdown
# <Feature> Design Spec

## Problem And Scope

## Domain Model

## State Machines

## Observable Invariants

## Crash Point Matrix

## Retry / Compensation / Reconciliation

## Reader Visibility Contract

## Adapter Contract

## Environment And Cutover Matrix

## Old Data / Migration Policy

## Acceptance Probes

## Open Owner Decisions
```

### Numbered Invariant Style

Every durable rule should get a stable ID, so issues and reviews can cite it without copying prose:

```text
INV-STOCK-001: A lifecycle marker may only represent side effects that completed.
INV-STOCK-002: Sold Base Qty must not increase unless Locked Base Qty covers the amount.
VIS-PC-001: Readers must see either the old active Product Component structure or the new active structure, never a mixed commit.
CRASH-ADJ-001: If a stock movement succeeds but adjustment persistence fails, reconciliation evidence must identify the movement keys and affected record IDs.
ENV-PC-001: local, smoke, preview, prod-like, and production must agree on Product Components runtime mode semantics.
```

### Crash Point Matrix Shape

Each write flow must include a crash matrix:

```markdown
| Step | Durable state before step | Side effect | If crash happens here | Reader-visible state | Retry behavior | Reconciliation evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Create pending intent | none | pending record | no business mutation | old active state | safe retry | none |
| Apply movement | pending intent | inventory changed | pending/review-needed | old or explicitly blocked | retry checks before/after | movement key + record id |
| Commit active | pending intent + verified side effects | active visible | old active or new active only | idempotent no-op or CAS retry | active record id |
```

### Adapter Contract Shape

The design spec owns semantic contracts, not adapter mechanics:

```markdown
## Adapter Contract

### saveProductComponentStructure(productId, draft)

Semantics:
- Readers see old active structure or new active structure.
- Failure must not expose a half-updated active structure.
- Retry with the same semantic draft is idempotent.
- Concurrent saves must serialize or fail one writer with a clear conflict.

Lark implementation note:
- May use pending/review_needed rows and last-step active switch.
- Must expose reconciliation evidence when Lark cannot preserve the contract.

Future PostgreSQL implementation note:
- Should implement the same semantic contract with a database transaction.
```

### Old Data Policy

This section is required because old-data policy changes blocker classification.

Allowed values:

- `preserve`: old data must remain readable and valid.
- `mark-and-reenter`: old data may be marked for review and manually re-entered.
- `ignore`: old data is explicitly out of scope.

The design spec must state which records are covered by each policy:

```markdown
| Data class | Policy | Required system behavior |
| --- | --- | --- |
| Existing Product rows without component snapshots | mark-and-reenter | checkout may fail closed with review note |
| Existing inactive Product Component rows | ignore | readiness may exclude or report deletable record IDs |
| New Product Components rows after cutover | preserve | must pass all invariants |
```

### Selected Quality Borrowed From `writing-plans`

Keep only the parts useful for durable design:

- No placeholders: no "TBD", "handle edge cases", or undefined states.
- Self-review for coverage: every stated requirement maps to at least one invariant, state transition, or acceptance probe.
- Exact acceptance probes: describe what must be proven, without forcing exact changed files.

Do not copy these heavy implementation-plan requirements into `design-spec`:

- Changed files list.
- Step-by-step tasks.
- Complete code blocks.
- 2-5 minute task granularity.
- Commit-per-task instructions.

### Design Review Gate

Before the spec is considered ready for implementation planning, it must pass a design review checklist:

- Every write flow has a crash point matrix.
- Every marker/status/audit field has clear semantics.
- Every retry path is idempotent or explicitly rejected with reconciliation.
- Reader visibility is specified for each state.
- Old-data policy is explicit.
- Adapter contract is semantic and implementation-agnostic.
- Acceptance probes cover success, failure, retry, and concurrency where relevant.

After the main draft is complete, run a final `grill-me-smartly` review step, matching the review posture of the previous planning workflow while keeping this skill focused on durable design rather than implementation planning.

The `grill-me-smartly` review should challenge:

- Whether the spec states real invariants or only desired happy-path behavior.
- Whether each crash point has observable state, retry behavior, and reconciliation evidence.
- Whether old-data policy is explicit enough to classify blockers.
- Whether adapter contracts are semantic rather than Lark-specific implementation steps.
- Whether the acceptance probes are strong enough to catch the failure classes described by the spec.

If subagents are unavailable or disallowed, run the same checklist inline and record the fallback reason in the output summary. Do not claim `grill-me-smartly` subagent review happened without subagent evidence.

## Proposed Skill 2: `implementation-orchestration`

### Purpose

Create execution artifacts from an approved durable design spec.

This skill is deliberately lean. It does not redefine domain behavior and does not write a bulk implementation plan. It coordinates existing skills:

- `to-issues` owns vertical-slice issue creation.
- `orchestrator` owns scheduler-facing parent plan and issue orchestration.

### When To Use

Use after `design-spec` is approved and the user wants issues, an orchestration plan, or worktree/session execution grouping.

Do not use when:

- There is no durable design spec yet.
- The domain semantics are still undecided.
- The user wants a one-off small fix that does not need orchestration.

### Input Contract

Required input:

- Approved design spec path.
- Target repo/tracker.
- Current implementation baseline, if any.

Optional input:

- Existing issues to reuse.
- Desired grouping, such as A/B/C.
- Known HITL decisions or standing authorizations.

### Workflow

1. Read the approved design spec.
2. Extract stable invariant IDs, state machines, adapter contracts, acceptance probes, and open owner decisions.
3. Run `to-issues` to create vertical-slice issue drafts.
4. Run `orchestrator` to create or update the scheduler-facing parent plan.
5. Ensure every issue references the relevant design-spec invariant IDs.
6. Ensure the parent plan keeps only orchestration-level context.
7. Produce a traceability table from invariant IDs to issue IDs and final gates.

### Output Contract

This skill may create:

```text
docs/impl-plans/YYYY-MM-DD-<feature>-orchestration.md
docs/exchange/issue-drafts/<feature>/*.md
```

Unlike design specs, orchestration plans may keep a timestamp because they are execution artifacts tied to a particular implementation wave.

If issues are published, GitHub issue IDs become the durable execution source.

The orchestration parent plan should include:

- Goal.
- Source design spec path.
- Invariant-to-issue traceability.
- Issue dependency graph.
- Parallelization plan.
- HITL pull-forward decisions.
- Integration checkpoints.
- Final gate.

It should not include:

- Full design-spec content copied inline.
- File-level implementation details.
- Long acceptance criteria for each issue.
- Worker-specific code instructions.

### Issue Body Requirements

Each issue produced through this flow should include:

```markdown
## What to build

## Design Spec Coverage

Covers:
- INV-...
- CRASH-...
- VIS-...

## Acceptance Criteria

## Out Of Scope

## Verification
```

Acceptance criteria should be localized to the issue, but must cite durable design-spec IDs.

### Large Acceptance Standards

This skill owns only big gates, not local task details:

- Every design invariant has at least one issue or explicit exclusion.
- Every crash matrix row is covered by an issue, test, validation gate, or documented manual policy.
- Every adapter contract has at least one conformance test or readiness gate.
- Every old-data policy is reflected in issue acceptance or explicitly excluded.
- Final integration includes review against the design spec, not only green tests.

### Selected Quality Borrowed From `writing-plans`

Use `writing-plans` quality standards only where they improve execution handoff:

- No placeholders in issue acceptance criteria.
- Concrete verification commands or gates where stable.
- Self-review that every spec requirement is covered.

Do not require:

- Complete code blocks in issues.
- Exact changed files for every issue.
- 2-5 minute steps.
- Per-task commits.

Those are too heavy for orchestrator mode and should be left to execution sessions only when they explicitly ask for an implementation plan.

## Boundary Between The Two Skills

| Concern | `design-spec` | `implementation-orchestration` |
| --- | --- | --- |
| Business problem | Owns | References |
| Domain states | Owns | References |
| Observable invariants | Owns stable IDs | Maps to issues |
| Crash matrix | Owns | Maps to gates/issues |
| Adapter semantic contract | Owns | Ensures coverage |
| Old-data policy | Owns | Turns into issue scope/gates |
| Issue slicing | Not allowed | Delegates to `to-issues` |
| Scheduler parent plan | Not allowed | Delegates to `orchestrator` |
| Worker file/task plan | Not allowed | Usually not allowed |
| Changed files list | Not allowed | Avoid unless an issue/gate truly needs it |
| Durable artifact | Design spec | GitHub issues + parent orchestration plan |

## Planned Files To Create Later

Suggested implementation files:

```text
skills/design-spec/SKILL.md
skills/design-spec/templates/design-spec-template.md
skills/design-spec/references/design-review-checklist.md

skills/implementation-orchestration/SKILL.md
skills/implementation-orchestration/templates/orchestration-from-design-spec.md
skills/implementation-orchestration/references/traceability-gate.md
```

Optional follow-up:

```text
docs/workbench-design/06-design-spec-and-implementation-orchestration.md
```

## Migration Plan

1. Create `design-spec` as a new standalone skill.
2. Create `implementation-orchestration` as a lean coordinator over `to-issues` and `orchestrator`.
3. Leave the existing planning skill untouched initially.
4. Update user-facing docs to recommend:

```text
design-spec -> design review -> implementation-orchestration -> implementation
```

5. After the new flow is proven, decide separately whether to deprecate or rename older planning workflows.

## Acceptance Criteria For This Skill Pair

- A user can create a durable design spec without producing an implementation plan.
- The design spec contains state machines, crash points, observable invariants, adapter contracts, old-data policy, and acceptance probes.
- A user can feed the design spec into implementation orchestration and get issues plus an orchestration parent plan.
- Issues cite stable design-spec invariant IDs.
- The orchestration parent plan does not duplicate the design spec or become a bulk implementation plan.
- Heavy `writing-plans` requirements are excluded from design-spec mode and only selectively used as execution quality guidance.
