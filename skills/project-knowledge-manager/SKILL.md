---
name: project-knowledge-manager
description: Use when preserving, curating, routing, summarizing, or maintaining durable project knowledge and documentation layers, including PRD structure, module PRDs, requirement inboxes, functional designs, implementation plans, and hands-on knowledge with reusable pattern, trap, recovery, or reverse-lookup value.
---

# Project Knowledge Manager

Route durable project knowledge and documentation to the right maintained home.

This skill is the parent entrypoint for `docs/hands-on-knowledge/` and a router for adjacent long-lived documentation layers. It classifies incoming material, decides which maintainer skill should handle hands-on knowledge, and keeps project docs coherent without duplicating child-skill rules.

Hands-on knowledge is reverse-indexed memory for future problem solving: experience, traps, symptoms, root causes, and fast lookup paths that help during implementation, debugging, verification, migration, recovery, or codebase orientation.

## Load Extra Context

Read `references/routing-taxonomy.md` when:

- routing among PRD, module PRD, requirement inbox, func-design, impl-plan, and hands-on knowledge is ambiguous
- the user asks for docs taxonomy, PRD cleanup, requirement lifecycle, or examples
- you need neutral examples for final reporting or user explanation

## Core Routing

Split mixed input into small candidate knowledge items before routing. One request may route to multiple destinations.

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

## Requirement Routing

Route outside child skills when the item is not hands-on implementation or debug knowledge:

- stable product, architecture, domain, milestone, or technology-stack facts -> `docs/top-level-knowledge/`
- product-level PRD content -> `docs/top-level-knowledge/prd.md`
- module or domain PRD content -> `docs/top-level-knowledge/prd-*.md`
- new or changed requirements needing traceability, review, or owner decisions -> `docs/exchange/req-*.md`
- broad roadmap or milestone strategy -> `docs/epic-plans/` when the repo uses it
- feature or module design decisions -> `docs/func-design/`
- temporary coding plans -> `docs/impl-plans/`
- mandatory operating rules -> `AGENTS.md` or `CLAUDE.md`, following the repo's canonical agent file

New/changed requirements generally flow: `req` inbox -> product/module PRD after acceptance -> func-design when design details are needed -> impl-plan for execution -> hands-on only for reusable implementation/debug lessons.

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
- product or flow rules already covered by PRD, func-design, or executable tests
- recent feature work whose only argument is "we changed this"
- requirement refreshes with no new trap, symptom, recovery path, or reverse-lookup shortcut

## Workflow

1. Infer source material from the prompt, conversation, files, changed paths, plans, handoffs, logs, or notes.
2. Confirm completion only when it is unclear whether the task, milestone, implementation, or investigation is done enough to preserve.
3. Split mixed material into candidate knowledge items.
4. Apply the durability gate to each candidate.
5. Classify each item as implementation, debug, both, PRD, requirement inbox, design, planning, top-level, mandatory rule, one-off, stale candidate, or unclear.
6. Load `impl-knowledge-maintainer` or `debug-knowledge-maintainer` only for hands-on items.
7. Before changing maintained docs, search existing relevant knowledge and prefer updating existing documents over creating new ones.
8. If material changes under `docs/hands-on-knowledge/`, evaluate whether `docs/hands-on-knowledge/entry-map.md` needs a routing update.

The child skills own detailed metadata, curation rules, destination decisions, and final document shape for implementation/debug knowledge.

## Final Report

Report:

- implementation/debug/both-routed items and the docs updated or created
- PRD, requirement inbox, design, planning, top-level, or mandatory-rule items routed outside hands-on knowledge
- ignored one-offs or unfinished items
- whether `docs/hands-on-knowledge/entry-map.md` changed, and why

If no maintained docs changed, say whether the material was one-off, already covered, unfinished, or better handled by another documentation layer.
