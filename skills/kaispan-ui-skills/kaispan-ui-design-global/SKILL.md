---
name: kaispan-ui-design-global
description: KaiSpan global UI capture Skill. Use when the user asks to preserve prototype evidence, register snapshot/surface records, extract shared UI candidates, run publishability/security gates, or maintain global UI design context; outputs go to target repo docs, not the Skill directory.
---

# KaiSpan UI Design Global

Use this Skill to turn prototype input into traceable global UI evidence and shared UI candidates. It does not implement module UI and does not store real capture results in the Skill directory.

## Required Reading

- `../kaispan-ui-design/references/protocol.md`: pointer, locator, fact-source priority, and missing-locator behavior.
- `references/snapshot-capture.md`: snapshot, surface record, and shared UI candidate workflow.
- `references/publishability-security-gate.md`: source, asset, screenshot, and publication boundary.
- Templates when creating skeletons: `templates/snapshot-metadata.md` and `templates/surface-record.md`.

Completion criterion: the agent can state the target repo context, target output directory, snapshot identity, and publishability status or gap list.

## Input Checks

1. Read the target repo `.kaispan-ui-design.json`.
2. Confirm `mode` is `global`, or the user explicitly asks to initialize global context.
3. Confirm output paths are repo-relative, usually under `docs/kaispan-ui-design/`.
4. If prototype source requires local resolution, use `.kaispan-ui-design.local.json` only for lookup; do not copy local paths into submitted docs.
5. If snapshot or surface locators are missing, create a missing-data list instead of fabricating records.

Completion criterion: no output depends on an unrecorded local path or guessed locator.

## Output Locations

Global design facts belong in target repo docs, for example:

```text
docs/kaispan-ui-design/
  prototype-surfaces.md
  shared-ui-candidates.md
  decision-register.md
  module-index.md
```

The Skill directory only stores workflow and skeleton templates.

## Capture Workflow

1. Assign a stable `snapshotId` for each prototype input.
2. Record source locator, capturedAt, capture method, hash, surface list, assets policy, publishability status, and known gaps.
3. Assign stable `surfaceId` values for each surface.
4. For each surface, record visual summary, interaction inventory, business-semantic clues, adoption decision, and security/publication notes.
5. Register cross-module layout, navigation shell, card, badge, toolbar, table, state, or interaction patterns as shared UI candidates.
6. Mark any business meaning that needs module confirmation as `needs-module-readiness`.

Completion criterion: every surface has a locator, publishability state, and a clear distinction between visual evidence and unverified business meaning.

## Decision Rules

- Prototype input is UI/semantic evidence, not production truth.
- Shared UI can contain visual structure and common interaction shell only; business state, permissions, scope, mutations, and audit remain module-owned.
- Assets that fail publishability/security gate cannot be copied into production or submitted docs.
- Pilot module references can provide methodology and shared UI candidate clues; they cannot become another module's business facts.
- Legacy proof-of-concept references cannot override KaiSpan API, DB, RBAC, or contracts.

## Final Response

Report:

- Global docs created or updated.
- New or unresolved `ksui://snapshot/...`, `ksui://surface/...`, or `ksui://shared-ui/...` locators.
- Assets or screenshots that remain private.
- Business-semantic clues that require module readiness bridge validation.
