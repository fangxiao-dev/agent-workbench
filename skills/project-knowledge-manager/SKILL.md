---
name: project-knowledge-manager
description: Use when preserving, curating, routing, summarizing, or maintaining durable project knowledge and documentation layers, including PRD structure, module PRDs/specs, requirement inboxes, implementation-local design/plan inputs, and hands-on knowledge with reusable pattern, trap, recovery, or reverse-lookup value.
---

# Project Knowledge Manager

Route durable project knowledge and documentation to the right maintained home. Keep product
intent, module intent, module behavior contracts, and point-in-time change design distinct.

This skill is the parent entrypoint for `docs/hands-on-knowledge/` and a router for adjacent long-lived documentation layers. It classifies incoming material, decides which maintainer skill should handle hands-on knowledge, and keeps project docs coherent without duplicating child-skill rules.

Hands-on knowledge is reverse-indexed memory for future problem solving: experience, traps, symptoms, root causes, and fast lookup paths that help during implementation, debugging, verification, migration, recovery, or codebase orientation.

## Load Extra Context

Read `references/routing-taxonomy.md` when:

- routing among top-level PRD, module PRD/spec, requirement inbox, implementation-local design/plan inputs, and hands-on knowledge is ambiguous
- the user asks for docs taxonomy, PRD cleanup, requirement lifecycle, or examples
- you need neutral examples for final reporting or user explanation

## Core Routing

Split mixed input into small candidate knowledge items before routing. One request may route to multiple destinations.

### Atomic Knowledge Item Gate

Do not route a whole incident, PR, release, or debugging session as one knowledge item just because it happened together. First split by the future lookup question a developer would ask, then route each item to the narrowest durable home.

Use these split signals:

- A different future reader would search for it from a different place, such as deploy verification, frontend implementation, backend adapter behavior, schema contract drift, or product requirement.
- The lesson has a different maintenance owner or source of truth, such as deploy script/tests, frontend tests, API models, PRD, or runbook.
- The lesson has a different action shape: diagnose/recover, implement/avoid, verify/release, decide product behavior, or record a mandatory operating rule.
- One paragraph would need both debug steps and implementation rules to stay correct.

When any split signal is present, create separate candidate items even if the user asks for "top lessons" or "summarize this incident." Cross-link related docs instead of making one catch-all doc.

Example: an outage investigation might produce one debug runbook for preview-domain/CORS verification, one implementation pattern for frontend error redaction and stale state clearing, and one deploy-script rule for split-runtime rollouts. The shared incident timeline is source material, not the documentation boundary.

Use `impl-knowledge-maintainer` for hands-on implementation knowledge:

- build, integration, migration, structure, or reuse patterns
- module boundaries, schema patterns, validation, server/client separation, wrappers, or adapters
- verified commands, test approaches, release checks, or implementation verification paths
- package behavior, implementation retrospectives, or preserved implementation references

Use `debug-knowledge-maintainer` for hands-on diagnostic knowledge:

- symptoms, diagnosis, root cause, remediation, or recovery
- known issues, recurring failure modes, platform/runtime traps, environment problems, or contract drift risks
- debug investigations, runbooks, postmortems, or preserved logs with framing
- feature-to-code entry paths that materially shorten diagnosis

Use both child skills when a session produced both implementation lessons and debug/recovery lessons. Keep the implementation-facing lesson and diagnostic/recovery lesson separate.

## Intent And Contract Routing

Route outside child skills when the item is not hands-on implementation or debug knowledge:

- journey/product-level intent -> top-level PRDs under `docs/top-level-knowledge/`
- module-level intent -> `module-prd`; update `docs/module-knowledge/<module>/prd.md` only when it already exists, otherwise register in `docs/module-knowledge/_pending.md`
- module behavior contracts -> `docs/module-knowledge/<module>/spec.md` or a module subdomain contract (`module-spec`)
- project language and canonical vocabulary -> root `CONTEXT.md` (`context-language`)
- stable architecture, milestone, or technology-stack facts -> `docs/top-level-knowledge/`
- new or changed requirements needing traceability, review, or owner decisions -> `docs/exchange/req-*.md`
- broad roadmap or milestone strategy -> `docs/epic-plans/` when the repo uses it
- point-in-time change design and temporary execution plans -> `docs/implementations/<slug>/`
- mandatory operating rules -> `AGENTS.md` or `CLAUDE.md`, following the repo's canonical agent file

Use two questions for durable deltas:

1. If the implementation were completely replaced but the user value stayed the same, must the statement still hold? If yes, it is intent.
2. Can tests, interfaces, state queries, or failure drills directly verify it? If yes, it is a behavior contract.

Split statements that contain both why and how; do not duplicate the same statement in PRD and spec.
New/changed requirements generally flow: `req` inbox -> top-level or module PRD after acceptance ->
implementation-local design when a change needs design -> module spec after verified behavior becomes
current contract -> hands-on only for reusable implementation/debug lessons.

Module PRDs are lazy. Ordinary gates and project-knowledge maintenance must register a
`module-prd` delta in `docs/module-knowledge/_pending.md` whenever the module `prd.md` does not
exist; only an owner-reviewed backfill apply may create the first file. Normal maintenance may
update an existing `prd.md`. Evidence for first creation must come from a top-level PRD, approved
design, owner decision, or confirmed gate, never code alone, and the content must establish
Purpose, users or journeys, Outcomes, Scope/Non-goals, and links to its top-level PRD and module
spec. Until the top-level PRD journey restructure is complete, persist each new `top-level-prd`
delta in the project's `docs/module-knowledge/_pending.md` with destination=`top-level-prd`,
source, statement, and authority instead of expanding the existing large PRDs.

## Durability Gate

Do not put an item in `docs/hands-on-knowledge/` just because it is important or implemented.

Preserve hands-on knowledge only when it is likely to help a future agent after they hit a confusing symptom, failed verification, wrong assumption, environment mismatch, or non-obvious implementation trap in a way that PRD/requirement/design/test docs would not already cover.

Preserve:

- repeated implementation or debug patterns
- non-obvious runtime, platform, integration, or package behavior
- migration, refactor, verification, or recovery lessons
- known failure modes or root causes likely to recur
- codebase entry paths that materially shorten implementation or diagnosis

Route elsewhere or ignore:

- ordinary requirements, PRD content, design decisions, and execution plans
- one-off logs, status updates, or per-session notes that do not change future behavior
- product intent already covered by PRD, or behavior contracts already covered by module spec or executable tests
- recent feature work whose only argument is "we changed this"
- requirement refreshes with no new trap, symptom, recovery path, or reverse-lookup shortcut

## Workflow

1. Infer source material from the prompt, conversation, files, changed paths, plans, handoffs, logs, or notes.
2. Confirm completion only when it is unclear whether the task, milestone, implementation, or investigation is done enough to preserve.
3. Split mixed material into atomic candidate knowledge items using the future lookup question, maintenance owner, source of truth, and action shape. Do not preserve an incident narrative as one doc when it contains multiple reusable lessons.
4. Apply the durability gate to each candidate.
5. Classify each item as implementation, debug, both, module-spec, module-prd, top-level-prd, context-language, requirement inbox, change design, planning, mandatory rule, one-off, stale candidate, or unclear.
6. Load `impl-knowledge-maintainer` or `debug-knowledge-maintainer` only for hands-on items.
7. Before changing maintained docs, search existing relevant knowledge and prefer updating existing documents over creating new ones.
8. If material changes under `docs/hands-on-knowledge/`, evaluate whether `docs/hands-on-knowledge/entry-map.md` needs a routing update.

The child skills own detailed metadata, curation rules, destination decisions, and final document shape for implementation/debug knowledge.

## Final Report

Report:

- implementation/debug/both-routed items and the docs updated or created
- module-spec, module-prd, top-level-prd, context-language, requirement inbox, change-design, planning, or mandatory-rule items routed outside hands-on knowledge
- ignored one-offs or unfinished items
- whether `docs/hands-on-knowledge/entry-map.md` changed, and why

If no maintained docs changed, say whether the material was one-off, already covered, unfinished, or better handled by another documentation layer.
