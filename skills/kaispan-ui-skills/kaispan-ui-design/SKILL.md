---
name: kaispan-ui-design
description: KaiSpan UI design router. Use when the user asks for prototype/global capture, shared UI governance, module UI migration, readiness bridge, slice plan, closure note, Skill/toolbox review, or capture/tooling automation; first choose global, module, review, or v0 tooling-protocol mode and then load the matching child Skill.
---

# KaiSpan UI Design Router

This Skill is the suite entry point. It chooses the mode, loads the correct child Skill, and keeps the protocol and safety boundaries visible. Do not store prototype surface inventory, module business mappings, closure notes, screenshots, production facts, or local paths in the Skill suite.

## Mode Decision

Choose one mode before taking task actions.

| Mode | Trigger | Next step |
| --- | --- | --- |
| Global | Preserve prototype evidence, register snapshot/surface records, extract shared UI candidates, or maintain global UI design context | Read `../kaispan-ui-design-global/SKILL.md` |
| Module | Map global UI evidence into a module, create readiness bridge/slice plan/closure note, or implement module UI | Read `../kaispan-ui-design-module/SKILL.md` |
| Review | Review Skill suite, global capture, module readiness, migration plan, fact-source conflict, or publishability/security risk | Read `../kaispan-ui-design-review/SKILL.md` |
| Tooling protocol | User asks for capture/extract/hash/screenshot scripts or automation | v0 has protocol and templates only; explain that scripts and `kaispan-ui-design-tooling` belong to a later version |

If one request spans modes, process dependencies in order: global evidence, then module readiness, then review. Do not skip missing locators or fact sources.

## Child Skill Index

- `kaispan-ui-design-global`: prototype/global capture method, snapshot/surface skeletons, shared UI candidates, and publishability/security gate.
- `kaispan-ui-design-module`: pointer discovery, readiness bridge, source priority, missing-locator blocked behavior, and module verification gates.
- `kaispan-ui-design-review`: boundary review, fact-source conflict review, publishability/security review, and whether `discuss-ledger` is needed.

## Required Protocol

Before entering a child flow, read `references/protocol.md`. Read `references/routing.md` for detailed routing and fallback. Read `references/safety-boundaries.md` when the task touches assets, source-of-truth conflicts, or write boundaries.

Protocol minimum:

- Committed pointer: `.kaispan-ui-design.json`, containing only logical locators, repo-relative paths, and public aliases.
- Local override: `.kaispan-ui-design.local.json`, gitignored and used only for local prototype/source/cache resolution.
- Canonical locators:
  - `ksui://snapshot/<snapshotId>`
  - `ksui://surface/<snapshotId>/<surfaceId>`
  - `ksui://shared-ui/<componentOrPatternId>`
  - `ksui://module/<moduleKey>/<surfaceId>`
- Module mode must stop with `blocked-by-skill-missing-locator` when `globalContextPath`, `activeSnapshotId`, target `surfaceIds`, or required `ksui://...` locators cannot be resolved.

## Fallback Order

Use fallback only after reading the relevant child Skill and protocol.

1. Child Skill references and templates.
2. Target repo `.kaispan-ui-design.json` and repo-relative design context.
3. Target repo official docs, API/contracts, DB/RBAC/file/audit/Action Center facts.
4. Lower-priority UI evidence only for visual intent, naming clues, or methodology.
5. Missing locator: stop and report `blocked-by-skill-missing-locator`; do not guess.

## Safety Boundaries

- The Skill suite may contain only instructions, references, gates, checklists, and empty skeleton templates.
- Real snapshot metadata, surface records, shared UI decisions, readiness bridges, slice plans, and closure notes belong in target repo docs.
- Formal Skill files, templates, and committed pointers must not contain local absolute paths. Use `<agent-workbench>`, repo-relative paths, or `ksui://...`.
- Do not modify production code, contracts, migrations, or business docs unless the user explicitly asks for implementation work in the target repo.
