---
name: do-review
description: Orchestrate independent leaf reviewer agents for PR/code review, N-round review, loop/until-converged review, custom reviewer selection, and closure verification. Pins a committed comparison HEAD first; must use a leaf subagent for every selected track. Uses Grok for finding closure and the selected leaf agents for review tracks.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Do Review

`do-review` is the sole orchestrator: one immutable ReviewRun, topology resolution, parallel leaf dispatch, one canonical ledger, convergence control, and a fail-closed report. The main session is not another reviewer.

## Gate 0（判断）
Commit the complete review unit to pin `HEAD` before ReviewRun creation; uncommitted review-relevant changes block it and leftover dirty files are recorded out of scope. Every selected track dispatches its matching leaf (the leaf definition carries its declared skill and isolation); if a leaf is unavailable or unauthorized, stop before ReviewRun creation and ask (stop, or authorize an exact named degraded list) — never infer degradation.

## 判断启发式（保留）
- **Safety admission**: applicable when the diff touches auth/sessions/credentials, authorization/permissions/tenant isolation, data integrity/durable writes/reconciliation/money/orders/customer state, concurrency/transactions/idempotency/locking/retries, schema migration/backfill/rollback, or external side effects (payments/webhooks/jobs/remote storage/third-party mutation). Keywords are cues, not evidence — record the matched boundary and the diff/contract fact. Safety applicable but omitted from an explicit `terminal-final` list → coverage `INCOMPLETE`, cannot support terminal PASS.
- **Finding acceptance/dedup/classification**: leaf output is candidate evidence until the parent records its decision in the one canonical ledger. Deduplicate by broken invariant or observable failure, not path/reviewer. blocker = business data/money/inventory/order/customer state/security/runtime-visible product data risk; follow-up = real but non-blocking; backlog = non-urgent cleanup. Insufficient evidence → disputed/downgraded/out of scope/`UNCERTAIN`, never a verified blocker.
- **Track C source recheck**: after a finding is accepted and classified as Spec fidelity, run the one-shot source recheck before implementation handoff (one fresh independent reviewer, limited to the accepted finding + immutable Decision/Spec/`contract-design.md` when present at the fixed head); record the result once, never dispatch a second check. Conclude: sources uniquely decide → req-align → owner decision; an unavailable/incomplete reviewer blocks the handoff instead of skipping it. A missing `contract-design.md` in an untouched legacy package is not by itself a gap.
- **Loop clean & convergence**: only the parent may call a track clean (after dedup/evidence verification/classification, no distinct new accepted blocker/follow-up); two consecutive clean rounds → dormant; a new accepted finding resets its track to active. Convergence = no new accepted in the latest round and every selected track dormant.
- **Closure ≠ terminal**: `finding-closure` verifies only its named findings and cannot stand in for `terminal-final`; terminal requires `terminal-final` on the final implementation `HEAD` with the complete applicable topology.
- 带到达路径的 claim，reviewer 要检查证据是否真的走过该路径：有没有连真实依赖、有没有过 composition root。只审单层文件不能替代这项路径证据检查。

## 机制指针（承接处）
Topology: default tracks read from [reviewer-registry.json](references/reviewer-registry.json); phase routing and Loop lifecycle per [review-topology.md](references/review-topology.md). Briefs (common + phase templates + anti-duplicate addendum) from [subagent-briefs.md](references/subagent-briefs.md); ReviewRun creation via `scripts/review_ledger.py`; parallel fresh-leaf dispatch with structured output (`verdict | coverage | findings`) via native subagents; ledger fields, classification and report templates per [output-templates.md](references/output-templates.md); fail-closed aggregation and report rendering by the orchestrator.

## Guardrails
Do not mutate code/issues/data/external systems; reviewers never mutate Git state. Do not broaden closure into unrelated hunting or hide unavailable/incomplete topology. Do not create/request/infer owner approval — a GO attempt returns findings to `/impl-package:dev-with-track`; direct invocation stops at the review checkpoint. Revise reviewer responsibility/topology only when that reviewer skill definition changes.
