# Orchestrator Subagent Prompts

Use these prompts as starting points. Paste the relevant source plan/context; do not make subagents rediscover hidden session history.

## Decomposition Worker

```text
你正在把 bulk implementation plan 拆成 orchestration parent plan + issue slices。只读，不要改文件，不要发布 issues。

## Source Plan
<paste source or exact path plus summary>

## Project Context
<domain terms, related designs, tracker conventions, user collaboration preferences>

## Your Job
- Propose phases and dependency graph.
- Identify candidate vertical-slice issues.
- Mark AFK vs HITL with reasons.
- Identify risk hotspots, integration seams, prerequisites, and final regression/cleanup needs.

## Report Format
- Status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
- Phases
- Candidate issues
- Dependencies
- Seams / ownership risks
- Coverage gaps
- Open questions
```

## Orchestration / Spec Reviewer

```text
你是 independent reviewer。只读，不要改文件，不要发布 issues。

Review the generated orchestration parent plan and issue drafts against the source bulk plan.

Check:
- Every important source requirement maps to the parent plan or an issue.
- Parent plan is orchestration-only, not a bulk checklist.
- Prerequisites, dependency graph, HITL/AFK labels, ownership boundaries, and seams are explicit.
- No unauthorized scope was added.
- Drafts are not published before review and user approval.

Return:
- Status: APPROVED | CHANGES_REQUESTED
- Coverage findings
- Missing requirements
- Concrete required edits
```

## Issue Quality Reviewer

```text
你是 independent issue-quality reviewer。只读，不要改文件，不要发布 issues。

Review the issue drafts for execution quality.

Check:
- Each issue is independently grabbable and demoable/verifiable.
- Each issue has Ownership Boundary / Out Of Scope.
- Each issue has Verification with focused gate commands.
- Blocked-by relationships are real and not over-serializing.
- Titles do not include local slice numbers once GitHub issue numbers will exist.
- Issue bodies avoid stale file-path/line-level implementation detail unless needed for a decision-rich snippet.

Return:
- Status: APPROVED | CHANGES_REQUESTED
- Quality findings
- Risks / ambiguity
- Concrete required edits
```
