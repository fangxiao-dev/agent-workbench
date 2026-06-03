# Curation Principles

Use these principles when writing the approval report and maintained knowledge.

## Baseline Over Session State

Always compare session findings to the current project baseline. A session may describe an old failure, old branch, or old implementation. Durable knowledge should describe the current reusable lesson, not the historical state.

Record:

- project path.
- branch and HEAD.
- dirty worktree state.
- files that currently carry the knowledge.

## Entry Map As Reverse Index

`docs/hands-on-knowledge/entry-map.md` is a routing map, not a complete index.

After every curation round, ask:

- Can a future agent find this by symptom, error text, package, integration, or business scenario?
- Is the entry too broad, forcing the reader into a long reference for a narrow problem?
- Did we add only keywords, or did we route to the right short document?

## Minimal Supplement First

When a candidate overlaps existing knowledge:

1. Update the narrowest existing document.
2. Add cross-links only when they shorten future lookup.
3. Create a new short document only if the existing home would become a grab bag.

If a reference starts to mix several symptoms, surfaces, or external systems, split it into short patterns/runbooks and point `entry-map.md` to those shorter paths.

## Approval Report Shape

The report is for decision making. It should contain:

- current baseline coverage.
- candidate lessons worth durable curation.
- suggested destination and indexing action.
- subagent disagreement or consistency risks.

Do not include a large "not worth curation" table. Rejected one-offs can be omitted or summarized briefly if the user asked for audit traceability.

## Language

Prefer project ubiquitous language and scenario language:

- "Customer Profile Change Request needs real Customers Table pending fields"
- "Order Document links must be surface-derived"
- "Platform Account deletion must preserve External Customers"

Use code paths as evidence, not as the main name of the lesson.

Chinese explanation is preferred when the user works in Chinese. Keep canonical English project terms when the project glossary uses them.

## Curation Boundaries

Do not curate:

- raw logs.
- per-session state.
- temporary record IDs.
- secrets or env values.
- ordinary requirements that belong in `docs/func-design/`.
- implementation plans that are not proven by execution or debugging.

Do curate:

- repeated traps.
- non-obvious integration behavior.
- failed assumptions.
- recovery paths.
- verification boundaries.
- code entry paths that materially reduce future diagnosis time.
