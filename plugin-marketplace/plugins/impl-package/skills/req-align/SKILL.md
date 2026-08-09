---
name: req-align
description: 当新增或变更 requirement 需要在 feature decision、specification 或 implementation planning 前完成对齐时使用；拥有必过的 Decision/Spec gates 及其 decision.md/spec.md artifact。
---

# Requirement Alignment

Run Decision, then Spec, for every contract-impacting change. The gates are equal requirements: a missing standalone `decision.md` never means a skipped Decision. `contract impact=none` exits through the fast path before either gate; it reuses an already valid contract rather than skipping validation.

## Routes and ownership

This skill owns the package's current `decision.md`, `spec.md`, and readable D/S aliases under the configured implementations root (default `docs/implementations/`). It does not create a tracker spec, a second behavior contract, or a plan. `/impl-package:impl-planning` consumes the gated `spec.md`.

- **No-contract fast path:** When business result, Acceptance Semantics, security/data constraints, and mutation authority are unchanged, reuse current D/S and route directly to the owning skill. Do not run brainstorming, either Gate, or Grill; do not create or expand D/S or other package state. Report why the existing contract still holds. If deletion changes a promise or acceptance boundary, it is contract-impacting.
- **Initial or follow-up:** Before Focused PRD work, classify the request and read [references/requirement-inputs.md](references/requirement-inputs.md). An initial request may begin with confirmed oral conversation, screenshots, documents, or repository facts. A follow-up starts from current D/S and treats the incoming request as a delta unless the owner explicitly declares full replacement.
- **Package lifecycle:** For a new package, a revision, or package closure, read [references/package-lifecycle.md](references/package-lifecycle.md) before acting.

Use [assets/templates/decision.md](assets/templates/decision.md) and [assets/templates/spec.md](assets/templates/spec.md). Use the proposal template only when a contract-impacting change enters Decision.

## Gate sequence

1. **Decision first.** Before drafting an earned Focused PRD or evaluating the Decision Gate, read [references/decision-gate.md](references/decision-gate.md) and [references/focused-prd.md](references/focused-prd.md). Decision is `BLOCKED` when destination, repository fit, material choices, source-input reconciliation, Core/Capability boundary, or blocking uncertainty is unresolved. Do not create `spec.md` while blocked.
2. **Spec second.** Only after Decision `PASSED`, read [references/spec-gate.md](references/spec-gate.md), synthesize the behavior contract, and evaluate Spec. Do not hand off to planning while Spec is blocked.
3. **Plan last.** After both gates pass and lifecycle registration validates, hand the same `spec.md` to `/impl-package:impl-planning`.

Lightweight corrections under an existing product definition may omit standalone `decision.md` only after Decision passes; their minimum evidence lives in `spec.md`'s Decision Gate Record. A new feature, material experience change, or business capability change normally earns `decision.md`.

## Common workflow

1. Classify contract impact. Take the fast path when eligible; otherwise identify new versus follow-up package work and read the applicable lifecycle rules.
2. Discover repository instructions, project context, authority sources, relevant code/tests, and expected knowledge that is absent. For follow-up work, read current D/S before interpreting the new request. If durable project knowledge should change, propose the change against a discovered authoritative source and wait for owner approval; never invent a long-lived destination.
3. Triage unknowns under the Decision reference. Perform permitted read-only investigation; record a `BLOCKED` Decision when a required investigation needs owner authorization, side effects, cost, or scope expansion.
4. Prepare the [Alignment Proposal template](assets/templates/alignment-proposal.md). It is working output, not a new durable artifact. Ask one focused question only when discovery and permitted investigation cannot resolve an intent, scope, trade-off, or owner decision.
5. Reconcile initial product promises or the follow-up delta, then run Decision research and Gate. Persist an earned or blocked `decision.md`; do not manufacture a duplicate PRD for the lightweight path.
6. After Decision passes, create or revise `spec.md`, evaluate the conditional evidence-integrity contract and risk-driven Grill only when their signals apply, then run Spec Gate.
7. Keep D/S aliases consistent in the current package, record the Git commit used for module-knowledge/code comparison, and complete the Decision/Spec gates. Do not create runtime state before an implementation attempt is approved.
8. When reporting any Decision or Spec result, including `BLOCKED`, read [references/handoff.md](references/handoff.md) and report the most specific status derived from recorded gate and downstream evidence.

## Output contract

For a contract-impacting request, state the focused requirement, selected direction, gate results, blockers/owner decisions, and next valid step in business language. After artifact writes, report canonical package identity, D/S aliases, evidence locations, and changed `execution-findings.md` only when it was appended. Do not paste full artifacts.

Package ID 一经创建不得改名。后续 requirement delta 先按 implementation-only / behavior-contract / decision-direction 分类，再只使受影响下游范围失效。
