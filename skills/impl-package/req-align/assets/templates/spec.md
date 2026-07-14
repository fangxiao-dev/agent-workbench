# [Implementation Name] Specification

Status: Draft | Spec Gate Passed | Spec Gate Blocked
Created:
Design Revision: D<n>
Spec Revision: S<n>
Requirement source:
Topic slug:
Package ID:
Canonical package: `docs/implementations/<package-id>/`
Design: [design.md](design.md) | No standalone design file

## Design Gate Record

<!-- Complete only after Design PASSED. Without design.md, this is the canonical minimal evidence that the mandatory lightweight Design step occurred. A Design BLOCKED path uses design.md and does not generate this spec. Therefore the Design Gate Result in an existing spec can only be PASSED. Status: Spec Gate Passed requires the Spec Gate Result PASSED; Status: Spec Gate Blocked requires the Spec Gate Result BLOCKED. -->

- Result: PASSED
- Destination and intended outcome:
- Authority/current-state evidence:
- Selected direction and rationale:
- Open Questions disposition:
- Owner Decisions (resolved / outstanding):
- Evidence location: design.md | this record
- Assessed by / date:

## Spec Gate Record

- Result: PASSED | BLOCKED
- Eight sections complete:
- Acceptance evidence mapped:
- Blocking decisions / ambiguity:
- Approved by / date:

## 1. Scope / Authority / Non-goals

- Scope:
- Authority and source precedence:
- Non-goals:
- Assumptions requiring confirmation:

## 2. Terms / Data Contracts

- Domain terms:
- Inputs, outputs, identities, and invariants:
- Schema, normalization, precision, and ownership semantics:
- Conditional evidence-integrity contract (only when an acceptance conclusion depends on authoritative evidence, publication/consumption state, compatibility projection, external side effect, or state-dependent public output): primary assertion and comparison unit; source authority and private-field exclusions; actual-versus-declared bounds; complete frozen-format admission; reader authority after incomplete publication; expected operational failure surface and stable public shape.

## 3. Behavior / State Machine / Workflow

| Actor / System | Condition / State | Action / Event | Result / Next State |
| --- | --- | --- | --- |

## 4. Module Boundaries / Dependencies

- Owning modules and responsibilities:
- Interfaces and seams:
- Upstream/downstream dependencies:
- Compatibility or migration window:

## 5. Error Boundaries / Failure Recovery

| Failure mode | Observable effect | Containment | Retry / Compensation / Recovery | Owner |
| --- | --- | --- | --- | --- |

## 6. Constraint Contracts

- Prohibited behavior:
- Trust and permission boundaries:
- Precision / normalization obligations:
- External provider obligations:
- Negative dependencies (must not depend on):

## 7. Acceptance Semantics / Verification Evidence

| AC ID | Promised outcome / constraint | Evidence producer or manual owner | Passing evidence |
| --- | --- | --- | --- |

<!-- When the conditional evidence-integrity contract applies, include only relevant false-PASS counterexamples here: e.g. comparison drift hidden by normalization, failure after a side effect, rollback/invalidation failure, incompatible projected input, or state-shape drift. These are examples, not mandatory scenarios. -->

## 8. Contract Coherence

- Cross-section consistency:
- Interface/seam ownership:
- Acceptance coverage:
- Remaining non-blocking assumptions:

## Revisions

<!-- Current and historical D/S content bindings live in the internal .impl-package/revision-bindings.json sidecar; do not put this file's own hash here or require the owner to read the sidecar. -->

| Previous | New | Contract change | Reason / authority | Date | Superseded note |
| --- | --- | --- | --- | --- | --- |
