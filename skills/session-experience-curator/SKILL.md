---
name: session-experience-curator
description: Use this when the user asks to scan sessions/threads/conversations over a time range for durable lessons, hands-on knowledge, experience curation, or "知识沉淀". This skill should run before writing knowledge docs: define the project/time/baseline, read actual session content, compare findings to the current workspace baseline, use subagents for exploration and audit, produce an approval report, and only after user approval invoke project-knowledge-manager to update durable knowledge.
---

# Session Experience Curator

Use this skill to turn a time-bounded set of project sessions into reviewed durable knowledge candidates, then curate approved items into the project knowledge base.

This is not `session-handoff`. A handoff preserves one session's state. This skill scans many sessions and decouples them from their historical state by comparing lessons against the current project baseline.

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

If the user gives a relative date, convert it to concrete dates in the current timezone before scanning.

## Output Contract

Before durable writes, produce a Markdown approval report that includes:

- scope and baseline metadata.
- how sessions were discovered and which sources were used.
- current baseline coverage.
- only actionable candidates and already-covered-but-needs-review items.
- suggested destination and indexing action for each candidate.
- subagent exploration/audit conclusions.

Do not include a long list of rejected or one-off sessions. The report is a decision aid, not an exhaustive transcript index.

## Approval Gate

Before writing maintained knowledge:

1. Show the approval report path and summary.
2. Wait for the user to approve, reject, or adjust scope.
3. After approval, use `project-knowledge-manager` to route each item to implementation, debug, top-level, or mandatory-rule homes.
4. Re-check `entry-map.md` after each curation round.

If the user has already approved in the same prompt, proceed but still keep the report updated as an audit trail.
