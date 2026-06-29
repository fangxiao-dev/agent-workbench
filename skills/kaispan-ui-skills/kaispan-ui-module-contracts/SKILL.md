---
name: kaispan-ui-module-contracts
description: Use when KaiSpan/admin UI Phase A review feedback, screenshots, findings, or boss comments must become module contracts under docs/kaispan-ui-design/module-contracts/*.md for Phase A closure or Phase B real-route absorption. Use for drafting, revising, or checking contracts; kaispan-ui-design remains the methodology/router.
---

# KaiSpan UI Module Contracts

Create and maintain module contracts: concise decisions that convert Phase A review evidence into Phase B implementation guidance.

Use this after `kaispan-ui-design` routes the task, or directly when the user asks to “update contracts”, “沉淀 Phase A 结论”, “根据 review 写 module contract”, or “为 Phase B 准备契约”.

## Boundary

This skill writes contracts. It does not implement UI, change real routes, build screenshot harnesses, rewrite global layout grammar, or run external smoke tests.

Use nearby skills for the surrounding work:

- `kaispan-ui-design`: methodology, source routing, red lines.
- `dev-with-track`: process/findings/gate ledger updates.
- `frontend-design`: UI implementation after the contract is accepted.
- `i18n-authoring`: production copy or dictionary changes.

## Contract Source Order

Read only the files needed for the target module, in this order:

1. Target repo instructions: root `AGENTS.md`, and app-level instructions when the contract affects app code.
2. Layout grammar: `docs/top-level-knowledge/admin-layout-grammar.md` or the repo-designated UI grammar.
3. UI mechanism/evidence entry: `docs/kaispan-ui-design/README.md` and `docs/kaispan-ui-design/ui-migration-mechanism.md` if present.
4. Current roadmap and ledgers: active roadmap, `process.md`, and `findings.md`.
5. Latest module evidence README/screenshots and review feedback.
6. Existing module contract, if present.

If a source is missing, record the gap in the contract. Do not invent decisions to fill it.

## Location And Naming

Default path:

```text
docs/kaispan-ui-design/module-contracts/<module>.md
```

Use lowercase kebab-case names such as `manufacture-overview.md`, `orders-overview.md`, `order-detail-workspace.md`, `inventory-overview.md`, or `erp-order-documents.md`.

When starting a new contract, use `templates/module-contract-template.md`. The template is the section source of truth; do not duplicate its full section list in this skill.

## Contract Loop

### 1. Restore The Contract Target

Identify the module/surface, phase, target real route, review source, and evidence directory. Determine the current contract status:

- `draft`: extracted from evidence or review, not accepted.
- `needs-review`: requires human/boss confirmation before Phase B.
- `accepted-for-phase-b`: sufficient to guide real-route absorption.
- `blocked`: a named missing decision, evidence gap, or safety boundary prevents Phase B.
- `superseded`: replaced by a newer contract; link to the replacement.

Completion criterion: the contract has a named module, status, target route/surface, and evidence links.

### 2. Extract Decisions, Not Screenshots

Convert review notes and evidence into semantic decisions:

- module-home purpose;
- submodule priority;
- primary and secondary CTA;
- action carrier: inline, drawer, dialog, floating panel, list, or detail page;
- status-only sections;
- disabled or not-yet-connected capability;
- rejected/deferred ideas;
- open questions.

Do not treat screenshot pixels, temporary fixture composition, or unreviewed implementation details as accepted decisions.

Completion criterion: every statement is marked as accepted, needs-review, rejected/deferred, or open.

### 3. Write For Phase B

Write the contract so a Phase B implementer can answer:

- What should the first screen communicate?
- What is primary, secondary, status-only, or deferred?
- Where does each action open and how does the user return?
- Which real route/component family will absorb it?
- Which auth, i18n, Server Action, Route Handler, data loading, and external mutation boundaries must stay unchanged?
- What must not be built until another decision or integration is ready?

Keep docs in Chinese by default. Preserve domain/API terms such as `Production Request`, `Recipe`, `Server Action`, `Route Handler`, and `Customer` when they are project terms.

Completion criterion: the contract is specific enough to prevent Phase B from copying screenshots blindly, but not so specific that it dictates pixels.

### 4. Check The Contract

Before finishing, check for these failure modes:

- Evidence is restated instead of referenced by path.
- Review decisions are mixed with guesses.
- External mutation boundaries moved or implied.
- Disabled/not-connected capabilities look implemented.
- Open questions are vague or not answerable.
- The contract repeats global layout grammar instead of applying it to this module.

Completion criterion: all failures are either fixed or listed as explicit gaps.

### 5. Update Ledgers

If the target repo uses process/findings/gate ledgers, update them through the `dev-with-track` workflow so they point to the contract and record the review state. Do not copy the whole contract into the ledger.

Completion criterion: ledgers reference the contract path, or the final response says why they were not updated.

## Final Response

Report briefly:

- contract path created/updated;
- status set;
- accepted decisions captured;
- open questions or gaps;
- ledgers updated or intentionally skipped;
- verification performed, or “not run: docs-only contract update”.
