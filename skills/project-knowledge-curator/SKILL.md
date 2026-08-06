---
name: project-knowledge-curator
description: Use this when the user asks to scan sessions/threads/conversations over a time range for durable hands-on knowledge candidates with reusable pattern, trap, recovery, or reverse-lookup value, before updating project knowledge docs.
disable-model-invocation: true
---

# Project Knowledge Curator

Use this skill to turn a time-bounded set of project sessions into reviewed durable knowledge candidates, then curate approved items into the project knowledge base.

This is not `handoff-new-session`. A handoff preserves one session's state. This skill scans many sessions and decouples them from their historical state by comparing lessons against the current project baseline.

## Durable Pattern Gate

Hands-on knowledge is for durable reverse-lookup value, not for every important implementation that happened recently.

Keep a candidate only when it would materially help a future agent who hits a confusing symptom, non-obvious integration behavior, repeated trap, failed assumption, recovery path, or narrow codebase entry problem.

Do not promote an item into `docs/hands-on-knowledge/` just because it is:

- implemented and important
- recently changed
- covered by code and tests
- worth keeping in PRD / func-design / test-case docs

If the lesson is mainly a product rule, requirement, or flow contract that is already adequately captured by requirement/design/test artifacts, do not create or update hands-on knowledge unless you can point to extra trap, recovery, or reverse-lookup value that those artifacts do not already provide.

Repetition is not required when the lesson is clearly durable on first discovery, for example a costly non-obvious integration behavior, recovery path, or debug trap that future agents are likely to hit again.

Negative example:

- `Register with an email that already belongs to one existing Customer should route to OTP login and not create/update Customer data` may be an important implemented rule, but if PRD, functional design, tests, and code already cover it, it is not automatically a hands-on pattern.

## Load References

Read only what is needed:

- `references/workflow.md` for the end-to-end process.
- `references/curation-principles.md` before writing the report or maintained knowledge.
- `references/report-template.md` when creating the approval report.
- `references/subagent-protocol.md` before dispatching subagents.

Use `project-knowledge-manager` only after the user has approved the candidate report or explicitly asks to skip the approval gate.

## Required Inputs

Resolve these before scanning:

- absolute time range, including timezone when possible.
- project path or repository name.
- current baseline: branch, HEAD, and dirty worktree state.
- target knowledge root. Default to `docs/hands-on-knowledge/`; if the project lacks it, create `docs/hands-on-knowledge/` unless the user requested another path.
- whether the project has a maintained ubiquitous-language glossary such as `docs/top-level-knowledge/ubiquitous-language.md`.

If the user gives a relative date, convert it to concrete dates in the current timezone before scanning.

## Ubiquitous Language Scan

When the project has a maintained ubiquitous-language glossary, include a lightweight glossary scan as part of the curation pass.

This scan is still report-only unless the user explicitly approves follow-up documentation work.

Look for:

- new recurring terms that appeared in sessions, code, docs, tests, or user-facing copy but are not in the glossary
- ambiguous aliases that compete with an existing canonical term
- meaning drift where a known term is being used with a different scope or boundary
- stable naming decisions that belong in the glossary rather than in hands-on knowledge

Do not force every wording change into the report. Keep only glossary candidates that are stable enough to matter across future planning, implementation, reviews, or user-facing copy.

## Output Contract

Before durable writes, produce a Markdown approval report that includes:

- scope and baseline metadata.
- how sessions were discovered and which sources were used.
- current baseline coverage.
- only actionable candidates and already-covered hands-on items that need wording/indexing review inside the hands-on layer itself.
- suggested destination and indexing action for each candidate.
- subagent exploration/audit conclusions.
- when a glossary exists, a short ubiquitous-language scan summary with candidate additions, clarifications, ambiguity fixes, or `no glossary action needed`.

The report should conclude `No new durable hands-on candidates` when the session mostly produced requirement/design/test updates rather than reusable pattern knowledge.

Do not include a long list of rejected or one-off sessions. The report is a decision aid, not an exhaustive transcript index.

## Approval Gate

Before writing maintained knowledge:

1. Show the approval report path and summary.
2. Wait for the user to approve, reject, or adjust scope.
3. After approval, use `project-knowledge-manager` to route each item to implementation, debug, top-level, or mandatory-rule homes.
4. Re-check `entry-map.md` after each curation round.

If the user has already approved in the same prompt, proceed but still keep the report updated as an audit trail.
