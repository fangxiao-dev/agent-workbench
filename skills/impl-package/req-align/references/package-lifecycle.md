# Package Lifecycle and Revision Binding

Read this reference for new-package setup, follow-up package reconciliation, D/S revision changes, sidecar registration, or closure validation.

## Package identity and files

Use the project's configured implementations root (default `docs/implementations/`). A new package ID is an immutable UTC date-prefixed slug: `YYMMDD-<topic-slug>`, with `-02`, `-03`, and so on if the exact directory exists. Retain legacy IDs for existing packages; never rename merely to add a date.

For a new package, create the directory and run `impl_package_state.py --package <path> init --package-id <id>` once before any D/S registration so both empty sidecars exist. For a follow-up, retain the owning package ID and reconcile current module knowledge/code before editing. Do not reinitialize it from templates.

This skill owns:

- `decision.md`: current Focused PRD and selected rationale; a blocked Decision must persist. A passed lightweight Decision may live only in `spec.md`'s Decision Gate Record.
- `spec.md`: current behavior, data, boundaries, recovery, constraints, and Acceptance Semantics.
- `.impl-package/revision-bindings.json`: append-only D/S binding and current selection. Its schema and commands are shared through `../../references/impl-package-state-schema.md`.

`execution-findings.md` is earned-only package-local provenance for confirmed reusable findings. Raw hypotheses, methods, failed paths, and option comparison belong only in earned `investigations/<topic>.md`; neither file is a second behavior contract or temporary todo queue. Move a package-owned pre-existing non-authoritative investigation into that location after identity is fixed; never move authoritative, shared, read-only, or externally owned documents.

## Revision rules

`decision.md` and `spec.md` each show only current content. A material user/business-result or decision-direction change increments D and reruns Decision; a behavior-contract change increments S and reruns Spec; a decision-direction change requires D then S. Pure implementation fixes that conform to current Spec reuse revisions. A `contract impact=none` editorial correction neither creates nor expands D/S.

The only D/S declarations are the machine-owned `revision-set` markers. Do not add duplicate revision headers or self hashes. When writing a new Markdown revision-history row, retain only the newest three entries. Sidecar bindings remain append-only.

After both Decision and Spec pass, compute the final D/S artifact Git blob OIDs, register both revisions, and refresh projections. On the lightweight Decision path, D and S bind separately to the same `spec.md` blob; do not create a standalone `decision.md` merely for registration. Commit the artifacts and sidecars, then run `validate --committed`. Registration must fail closed when sidecars are missing or drifted; fix capture gaps rather than hand-editing JSON or marker bodies.

## Reopened packages

Before reactivating a closed package, recalculate relevant module-knowledge commit SHAs and compare them with the prior attempt's watermark. Diff first when they differ, then classify the discrepancy as implementation drift, behavior-contract change, or decision change. Do not let a reopened package silently retain an invalid current contract.
