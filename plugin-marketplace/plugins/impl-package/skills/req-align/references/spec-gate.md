# Spec Gate: Contract Completeness and Conditional Scrutiny

Read this reference only after Decision has passed.

## Spec Gate

Synthesize the point-in-time contract from repository facts, selected user-facing semantics, seam/interface decisions, and Decision outcomes. Use the eight-section Spec template. Spec passes only when all eight sections are substantive; behavior, state/workflow, boundaries, and recovery are internally consistent; Acceptance Semantics maps each promise/constraint to observable evidence and names manual owners; and blocking owner decisions or contract ambiguity are zero.

The Spec must stand without the plan. It must not contain stable-doc backfill maps, durable-delta queues, Composition, worker steps, verification command logs, or tracker publication metadata. If the gate blocks, record the exact missing contract or decision and do not hand off to planning.

## Conditional evidence-integrity contract

Evaluate this only when acceptance depends on evidence whose authority, comparison, publication, compatibility, or consumption can create false PASS: for example external-provider proof, durable current pointers, atomic publish/archive, external mutation, projected schema, or state-varying public payload.

When signaled, use the existing eight sections to define relevant authoritative sources, comparison units/normalization, trusted inputs and revalidation at commit points, post-side-effect failure and compensation/invalidation, complete compatibility admission, safe observable failure surfaces, and stable public shapes. The gate passes only when false-PASS counterexamples are testable. Do not add a ninth section or impose this ceremony on ordinary changes.

## Risk-driven Grill

Run `/impl-package:grill-me-smartly` only when the user asks, or when high-risk signals exist: unresolved material ambiguity, cross-module/external interface, migration/compatibility, security/data authority, destructive external mutation, or evidence-integrity false-PASS risk. It never silently applies clarifications.

The ledger lives in OS temp, not the package. Summarize converged decisions and owner decisions to the user. Any user decision remains a normal blocking owner decision until cleared. Only after user approval may converged clarifications revise Spec through the ordinary S-revision path. After Spec passes, offer `/impl-package:grilling` only as an optional deeper review.
