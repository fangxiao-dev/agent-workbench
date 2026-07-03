---
name: feature-impl-planing
description: >
  Create or update a feature design and implementation plan from an aligned
  requirement, issue, or discussion. Use this when the user asks for an
  implementation plan, feature plan, Func Design, or issue implementation plan.
  Route into one of two modes: strict workflow when the repository has the
  expected docs/exchange, docs/func-design, docs/impl-plans, top-level
  knowledge, and test-case folders; fallback workflow when those folders are
  missing and the repository keeps planning context in loose docs/*.md files.
---

# Feature Impl Planing

Create a feature design and implementation plan using the repository's documentation shape.

This skill has two entry options:

1. **Strict workflow**: use the user's structured workflow exactly when the repository has the expected planning folders and a requirement-alignment artifact.
2. **Fallback workflow**: use the adaptive workflow when the repository lacks those folders, especially when PRD, tech stack, architecture, feature design, and status context live as loose Markdown files under `docs/`.

## Route Selection

First inspect the repository docs shape:

- `docs/exchange/`
- `docs/func-design/`
- `docs/impl-plans/`
- `docs/top-level-knowledge/`
- `test-cases/`
- directly relevant `docs/**/*.md` files

Choose **strict workflow** when the expected folders and requirement alignment artifact are present, or when the user explicitly asks to follow the strict structured workflow.

Choose **fallback workflow** when one or more required folders are missing and the repository still has useful `docs/*.md` context. Briefly tell the user which structured folders are missing, then proceed with fallback if the user's request is already clear.

If the repository has no usable docs and no aligned requirement, ask one concise alignment question before writing the plan.

## Workflow Details

- Strict workflow details: [strict-workflow.md](./strict-workflow.md)
- Fallback workflow details: [fallback-workflow.md](./fallback-workflow.md)

Read only the detail document for the selected route.

## Mandatory Review Subagent

Invoking this skill authorizes only the review subagent described by the selected route. The authorization is limited to local factual/codebase research about the requirement, generated design, generated plan, and related project files.

In strict workflow, the review subagent is mandatory. This is not optional permission; it is the required review mechanism. Do not write or claim a `grill-me-smartly` review note from main-session self-review alone.

In fallback workflow, default to the `grill-me-smartly` review subagent as well. Use inline self-review only when the `grill-me-smartly` skill cannot be found/read or when no subagent capability is available in the current environment. When falling back to inline review, state the exact reason in the returned summary.

Do not use subagents for implementation or unrelated exploration unless the user separately asks for that.

`grill-me-smartly` output is an intermediate process record only. Keep grill
ledgers in the OS temp location defined by that skill, not in the repository.
Do not link grill ledgers or grill review notes from Func Design,
Implementation Plan, simplified plan artifacts, README indexes, or other formal
project documents. Apply all accepted grill context, corrections, and owner
decisions directly into the formal documents so they stand alone without the
temporary grill record.

Invalid review patterns:

- Writing a `grill-me-smartly` review note based only on main-session self-review.
- Saying "reviewed" without a subagent id and subagent answer evidence.
- Treating this subagent authorization as optional in strict workflow.
- Using inline review in fallback workflow without first checking whether `grill-me-smartly` and subagent review are available.
- Linking a formal document to a temporary grill ledger instead of applying the
  review context into the document.

## Output Contract

Return a compact summary with:

- selected route: strict or fallback
- files created or changed
- main design and implementation summary
- corrections applied by review
- review method used (`grill-me-smartly` subagent, or inline fallback with reason)
- remaining owner decisions
- whether the plan is ready for implementation

Keep proposal drafts in the repository's selected exchange path when the route
calls for drafts. Keep grill review details in the OS temp grill ledger only,
and make the formal planning documents complete without links to that ledger.
