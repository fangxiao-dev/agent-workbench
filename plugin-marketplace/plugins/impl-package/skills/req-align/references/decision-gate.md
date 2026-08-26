# Decision Gate: Boundary, Uncertainty, and Pass Criteria

Read this reference before the initial bundle's Focused PRD research or Decision Gate judgment. Follow-up updates use the initial approval as their governing decision.

## Core / Capability boundary

For every contract-impacting change, make one proportionate boundary judgment:

1. State the stable business Core that changes or is reused, its owner, authority, and invariants. If none exists beyond local behavior, say so rather than inventing an abstraction.
2. State each current Capability, caller, and exact authority exposed.
3. Exclude caller-specific transport, UI, provider, fixture, delivery, and acceptance details from Core semantics.
4. Evaluate reuse from evidence: a second caller should not need to copy Core semantics. Imagined reuse never authorizes premature API, persistence, permission, UI, or delivery infrastructure.
5. Record deferred Capability expansion and its re-entry condition only when it affects scope, authority, migration, recovery, or Acceptance Semantics.

The Decision records why the selected boundary is proportionate; Spec makes it actionable; Plan decomposes it. A material ambiguous boundary, copied Core semantics, or capability expansion justified only by imagined reuse blocks Decision.

## Blocking-decision uncertainty

Classify every unknown. It is **blocking** when a negative, unavailable, or disproving answer would change selected direction, Spec boundary, critical authority, delivery path, or Acceptance Semantics. Record the question, classification, contract impact, evidence required, whether read-only investigation may proceed, and required owner authorization.

Perform ordinary read-only task-scoped investigation directly. If it needs new permission, side effects, material cost, code spike, environment change, or scope expansion, record `Decision Gate: BLOCKED` and the owner decision instead. Put detailed investigation material in an earned investigation file; keep formal documents self-contained. A deferred non-blocking question needs explicit owner, consequence, defer boundary, and proof it cannot affect the contract.

## Decision Gate（仅初始 bundle）

Decision passes only when all are true:

- destination is answerable: outcome, affected boundary, delivery path, and validation limit are explicit;
- an earned Focused PRD passes [focused-prd.md](focused-prd.md)'s stable questions, applicable signal depth, and quality rubric; lightweight work points to its current product definition;
- initial inputs capture every material confirmed promise, and follow-up inputs have reconciled current D/S with the delta without silent omission;
- Core/Capability, repository fit, material choices, and durable owner decisions are evidenced;
- all blocking uncertainty is closed; remaining questions are proven non-blocking for Spec.
- Decision 正文只承载方向与产品控制；Ticket 分解、验证与浏览器策略、证据分配，以及字段与算法级的可观察行为分别由 Spec 和 Plan 承载。

If any condition fails, persist or update `decision.md` as `BLOCKED` with evidence and required owner decision, then stop. `decision.md` owns why the change exists, its user/business result, selected direction, and product control. Field/data contracts, state machines, errors, recovery, and Acceptance Criteria belong to Spec; decomposition and verification commands belong to Plan.
