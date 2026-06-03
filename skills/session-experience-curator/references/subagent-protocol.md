# Subagent Protocol

Use subagents to keep the main session focused and to reduce confirmation bias.

## General Rules

- Subagents are read-only until the user approves curation.
- Give each subagent the project path, time range, current baseline, report path, and assigned sessions/topics.
- Ask for concise findings with evidence paths and uncertainty.
- Tell subagents not to write maintained knowledge docs during exploration.
- Merge subagent results into the approval report before asking the user.

If subagents are unavailable, run the same lanes inline and label the report sections accordingly.

## Lanes

Use these lanes by default:

1. Session scanner
   - Reads actual session/thread content.
   - Finds candidate lessons, explicit knowledge discussions, and prior approvals.
   - Flags sessions that look skipped but lack current baseline coverage.

2. Baseline reviewer
   - Reads current code/docs/entry-map.
   - Checks whether each candidate is already covered.
   - Identifies the narrowest existing destination or recommends a short split.

3. Curation auditor
   - Reviews the consolidated report.
   - Looks for duplicate candidates, inconsistent terminology, over-broad references, stale session assumptions, and missing indexing.

## Output Contract

Ask every subagent to return:

```markdown
## Summary
<one paragraph>

## Findings
| Candidate | Keep / Covered / Drop / Needs split | Evidence | Notes |
| --- | --- | --- | --- |

## Indexing Advice
- ...

## Risks Or Disagreements
- ...
```

Keep the main report authoritative. Do not paste long subagent transcripts into it.
