# Handoff Template

Use this exact section structure in the handoff markdown:

```md
# Session Handoff

## Current Goal
- State the current objective clearly.
- State why this work is being done now.

## Completion Status
- Separate what is completed, partially completed, and not completed.
- Include what has been verified and what has not been verified.
- If verification is blocked, state the blocker plainly.

## Repo / Git State
- Branch name, and whether the work is committed or only in the working tree.
- Current HEAD and any divergence from the trunk (ahead/behind, merge-base).
- Workspace/worktree roles: where implementation should continue, whether this is a dedicated feature worktree, and whether the main workspace should remain untouched.
- Capture this from actual `git` output, not from memory.

## What Changed
- Summarize the meaningful code, logic, UI, workflow, or documentation changes from this session.
- Prefer behavior-level changes over raw edit inventories.

## Pitfalls And Resolutions
- For each important issue, include:
  - what went wrong
  - root cause
  - how it was resolved
  - whether the fix is final or only a mitigation

## Open Issues
- List remaining bugs, validation gaps, manual checks, or decisions still pending.
- Include anything the next session must confirm before changing code.

## Next Recommended Actions
- State the first action the next session should take.
- List the most relevant files to read first.
- List the most relevant verification command or manual check to run next.

## Useful References
- Include only high-signal file paths, docs, commands, or artifacts.
- Prefer a short list over a long dump.
```

## Writing Guidance

- Write for a new session that does not know the conversation history.
- Use concrete file paths when they help the next session move quickly.
- Distinguish facts from assumptions.
- Keep it high-signal: prefer behavior-level summaries over raw edit inventories; keep each list short.
- Do not paste secrets, tokens, env values, or full logs into the handoff.
- Do not include any section about skill extraction, manual alignment, or continuous learning review.
