# Approval Report Template

Use this structure for the temporary report. Trim sections that do not apply.

```markdown
---
status: draft
doc_type: session-experience-curation-report
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
baseline_branch: <branch>
baseline_head: <short-sha title>
baseline_workspace: <clean/dirty summary>
scope: <time range + project path>
---

# <Project> Session Experience Curation Candidates

## Scope And Baseline

- Project: `<absolute path>`
- Time range: `<absolute range and timezone>`
- Branch: `<branch>`
- HEAD: `<sha title>`
- Worktree: `<status summary>`
- Knowledge root: `<path>`
- Session sources: `<thread tools / local JSONL / other>`

## Curation Principles For This Pass

- Current baseline overrides historical session state.
- `entry-map.md` is the reverse index; durable writes must keep it effective.
- Prefer minimal supplements; split short documents only when references become too broad.
- Report only actionable candidates and already-covered hands-on items that need wording/indexing review inside the hands-on layer.
- Keep only items with durable pattern, trap, recovery, or reverse-lookup value; do not keep implemented requirement rules already covered in PRD / func-design / tests unless you can state the extra trap, recovery, or reverse-lookup value that those artifacts do not already provide.

## Current Baseline Coverage To Review

| ID | Covered lesson | Current home | Review needed |
| --- | --- | --- | --- |
| W-01 | ... | `docs/hands-on-knowledge/...` | wording / indexing / split boundary |

## Candidate Lessons

If there are no qualifying durable candidates, say so explicitly:

`No new durable hands-on candidates recommended in this pass.`

### C-01 <Scenario Name>

Priority: high / medium / low.

Scenario:
<business-facing scenario language>

Candidate knowledge:

- ...
- ...

Recommended route:

- Existing document to update, or new short doc if needed.
- `entry-map.md` route/search terms to add or verify.

Evidence:

- `path/to/doc-or-code`
- `thread-id` as evidence pointer only

Decision needed:

- ...

Why this is hands-on knowledge instead of requirement/design/test coverage:

- ...

## Ubiquitous Language Scan

Use this section only when the project has a maintained glossary such as `docs/top-level-knowledge/ubiquitous-language.md`.

- Candidate term additions:
- Candidate clarifications or ambiguity fixes:
- No glossary action needed: yes/no, why

## Subagent Review Summary

| Agent lane | Conclusion | Changes made to report |
| --- | --- | --- |
| Session scanner | ... | ... |
| Baseline reviewer | ... | ... |
| Curation auditor | ... | ... |

## Approved Curation Execution

Fill this only after the user approves and curation is performed.

- C-01 -> updated/created `...`
- C-02 -> updated/created `...`
- `entry-map.md` changed: yes/no, why

## Verification

- `git diff --check`: pass/fail
- Runtime tests: not run / commands
- Residual risks:
```
