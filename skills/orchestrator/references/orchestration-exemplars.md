# Orchestration Exemplars

This registry records strong orchestration plan examples found in `D:\CodeSpace\prj-supplyer-webapp` and its worktrees.

Discovery scope:

- Time window: active worktrees with commits from 2026-06-22 through 2026-06-27.
- Project: `D:\CodeSpace\prj-supplyer-webapp`, including `git worktree list --porcelain` entries.
- Method: filter active worktrees by recent git activity, then score tracked/untracked Markdown for orchestration signals such as `AFK`, `HITL`, `Published Issues`, `Dependency Graph`, `Parallel Assignment`, `Handoff`, `Verification Policy`, `Source Context`, and `Current Baseline`.
- Registration rule: keep the best path for each unique plan file; many older plans appear in multiple worktrees.
- Recency note: most registered plans have file-level commits inside the time window. The two older Lexware examples are retained as active-worktree comparative examples because they were still present across recently active worktrees and contain external-side-effect patterns not covered as cleanly by the newer files.

## Registered Exemplars

| Rating | Use | Plan | Best registered path | Last commit |
| --- | --- | --- | --- | --- |
| Excellent | Whole-doc exemplar for modern parent plan with coverage and HITL pull-forward | Product/SKU Components Bundle Orchestration Plan | `D:\CodeSpace\prj-supplyer-webapp\.worktrees\product-package-orchestration\docs\impl-plans\2026-06-27-product-sku-components-bundle-orchestration.md` | `f5608146` `2026-06-27T23:25:56+02:00` `docs(product): link component orchestration issues` |
| Excellent | Whole-doc exemplar for durable execution source and published issue scheduler table | Inventory Item Manufacture Orchestration Plan | `D:\CodeSpace\prj-supplyer-webapp\.worktrees\admin-layout-phase-a-spike\docs\impl-plans\2026-06-21-inventory-item-manufacture-orchestration.md` | `bdee56f0` `2026-06-24T20:22:01+02:00` `Refactor inventory and manufacture workbench (#58)` |
| Excellent | Compact exemplar for a five-slice queue, current baseline, seams, and final gate | Production Request Queue Orchestration Plan | `D:\CodeSpace\prj-supplyer-webapp\.worktrees\admin-layout-phase-a-spike\docs\impl-plans\2026-06-24-production-request-queue.md` | `183dade5` `2026-06-25T01:16:52+02:00` `docs(production): publish request queue issues` |
| Excellent | Clean external-mutation parent plan, good for guardrails and ownership boundaries | Lexware VAT Tax-Free Phase 1 Orchestration Plan | `D:\CodeSpace\prj-supplyer-webapp\.worktrees\admin-layout-phase-a-spike\docs\impl-plans\2026-06-20-lexware-vat-tax-free-phase1-orchestration.md` | `af493c83` `2026-06-20T22:15:27+02:00` `docs(lexware): drop local VAT issue drafts` |
| Excellent, curated excerpts only | External-contract prototype with credentials, provisional fallback, and no-upload boundaries | METRO EDI Generation Prototype Orchestration Plan | `D:\CodeSpace\prj-supplyer-webapp\.worktrees\metro-edi-generation-prototype\docs\impl-plans\2026-06-13-metro-edi-generation-prototype-orchestration.md` | `ad018df9` `2026-06-26T23:11:40+02:00` `fix(metro-edi): align orders format with METRO reply` |
| Excellent, curated excerpts only | Handoff contract, browser evidence, final closure, and residual-risk reporting | Supplier Admin Console Phase 1/2 Readiness Orchestration Plan | `D:\CodeSpace\prj-supplyer-webapp\.worktrees\admin-layout-phase-a-spike\docs\impl-plans\2026-06-24-admin-ui-readiness.md` | `122bf3b5` `2026-06-24T20:55:30+02:00` `feat(admin-ui): prepare supplier admin shell primitives` |
| Useful | Simpler baseline for published issue indexing and conditional dependency graph edges | Inventory UOM SSOT Product Package Structure Orchestration Plan | `D:\CodeSpace\prj-supplyer-webapp\.worktrees\product-package-orchestration\docs\impl-plans\2026-06-26-product-pack-structure.md` | `e73f9265` `2026-06-26T20:48:50+02:00` `docs(inventory): publish package orchestration issues` |
| Useful | Cautionary hybrid with strong out-of-scope and open-decision resolution sections | Inventory Item Recipe Semantics Patch | `D:\CodeSpace\prj-supplyer-webapp\.worktrees\admin-layout-phase-a-spike\docs\impl-plans\2026-06-23-inventory-item-recipe-semantics-patch.md` | `bdee56f0` `2026-06-24T20:22:01+02:00` `Refactor inventory and manufacture workbench (#58)` |
| Useful | Earlier external side-effect decomposition and review-gate example | Lexware Voucher Post-Create Sync Orchestration Plan | `D:\CodeSpace\prj-supplyer-webapp\.worktrees\admin-layout-phase-a-spike\docs\orchestration\2026-06-14-lexware-voucher-post-create-sync.md` | `694c8888` `2026-06-15T14:58:57+02:00` `feat(lexware): sync finalized delivery notes before invoice` |

## Best Patterns To Copy

Use these patterns when creating or reviewing examples, not as mandatory boilerplate for every plan.

- **Execution source callout**: state that the parent plan is scheduler / integrator / validator context and that published GitHub issues are the durable execution source.
- **Source preservation**: record whether the bulk plan was committed, snapshotted, or otherwise preserved before rewriting into orchestration form.
- **Current baseline before slicing**: capture existing runtime behavior that affects issue boundaries, especially state machines, external IDs, authority rules, and current failure modes.
- **Source coverage matrix**: map source requirements to issues, parent-plan context, or explicit exclusions. This is strongest in the 2026-06-27 product bundle plan.
- **Published issues table**: include durable tracker ID, AFK/HITL type, blocker, size/risk, sizing decision, and coverage. After publication, tracker IDs should be canonical; local slice IDs should fade.
- **Dependency graph plus parallel plan**: combine graph shape with scheduling text that says what can run concurrently, what must wait, and where final regression sits.
- **Ownership boundaries**: make each worker's contract surface explicit, including out-of-scope neighboring work.
- **Handoff contract**: require issue URL, changed files, gates run, browser or external evidence, skipped checks, residual risks, side effects touched, and scope exclusions.
- **Seams to watch**: name concrete domain seams, not generic warnings. Good seams cover identity, idempotency, replay, mutation boundaries, partial failure, source of truth, UI loading, and external-read/write separation.
- **Verification policy**: separate focused per-issue gates from final integration gates. Record skipped external checks and residual risk at closure.
- **Review/publication record**: record decomposition review, issue-quality review, owner approval, publication result, and corrections applied.

## HITL And External-Side-Effect Lessons

- Isolate HITL into explicit gates or issues, then state what can proceed AFK.
- Default to local, mock, fixture, or read-only checks. Real writes, uploads, production smoke, Contact mutation, public deployment, and SFTP-like evidence require explicit owner approval.
- Optional real external checks are cleaner as separate HITL issues than hidden steps inside AFK implementation issues.
- Credential and raw-data handling belongs in the parent plan when it changes execution safety: no secrets in commits, sanitized fixtures, raw sample storage location, and revalidation rules.
- Strong plans pull decisions forward with standing authorization packets, fail-closed rules, and explicit remaining owner decisions.

## What Not To Copy

- Dense domain facts that belong in issues or source design docs.
- Mixed draft and published terminology after issues are published.
- Local slice numbers in issue titles or primary scheduler language after GitHub issue numbers exist.
- Long command blocks in the parent plan unless they are final-gate policy; examples should show shape plus one compact command when needed.
- Status-ledger history that hides the current execution source.
- Environment quirks such as one worktree's dependency setup unless the example is specifically about handoff or verification failure.

## Minimal Example Shape

For a compact teaching example, prefer this section spine:

1. Execution Mode / Execution Source.
2. Goal.
3. Architecture Boundary.
4. Source Context and Source Preservation.
5. Current Baseline.
6. Source Coverage Matrix.
7. Published Issues or Draft Issue Breakdown.
8. Dependency Graph.
9. Parallel Assignment Plan.
10. Ownership Boundaries.
11. Handoff Contracts.
12. Seams To Watch.
13. Guardrails.
14. Verification Policy.
15. Review / Publication Record.
16. Remaining Owner Decisions.
