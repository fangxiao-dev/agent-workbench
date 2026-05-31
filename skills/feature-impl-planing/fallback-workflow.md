# Fallback Feature Implementation Planning Workflow

Use this workflow when the repository does not follow the structured planning layout. This is common when all planning context lives in loose Markdown files under `docs/`.

## When To Use

Use fallback mode when any of these are true:

- `docs/func-design/` is missing
- `docs/impl-plans/` is missing
- `docs/top-level-knowledge/` is missing
- `test-cases/` is missing
- no `docs/exchange/requirement-alignment-...md` exists
- the user provides a GitHub issue, raw requirement, or discussion and asks for a plan anyway

Do not fail just because the strict folders are missing. First align the documentation gap with the user in one short note, then scan the docs that do exist.

## Read

Scan `docs/` before writing:

- `docs/PRD.md`
- `docs/architecture.md`
- `docs/project-status.md`
- `docs/team-collaboration-breakdown.md`
- `docs/README.md`
- `docs/tech-stack.md`
- `docs/design.md`
- `docs/requirements.md`
- relevant files under `docs/diagrams/`
- any other directly relevant `docs/**/*.md`

Also inspect code files needed to verify whether docs and implementation drift from each other. Keep code inspection focused on the issue.

If the repository has no useful docs, ask one concise alignment question before writing a plan.

## Write

Create `docs/exchange/` if it does not exist.

Write one combined simplified artifact:

- `docs/exchange/feature-plan-YYYYMMDD-HHMM-<topic>.md`

Review note, when `grill-me-smartly` subagent review is available:

- `docs/exchange/grill-me-smartly-YYYYMMDD-HHMM-<topic>.md`

Do not create `docs/func-design/`, `docs/impl-plans/`, `docs/top-level-knowledge/`, or `test-cases/` just to satisfy the strict workflow unless the user asks to introduce that structure.

## Simplified Artifact Structure

```markdown
# <Feature Name> Design And Implementation Plan

## Source And Alignment

## Existing Docs And Code Context

## Goals

## Non-Goals

## Design

## Module Boundaries

## Implementation Plan

## Verification

## Open Questions
```

## Workflow

1. Announce fallback workflow mode and list missing structured folders.
2. Scan existing `docs/**/*.md` to catch up PRD, tech stack, architecture, feature design, and status context.
3. Read the issue, requirement, or discussion source.
4. Add a lightweight alignment summary inside the generated artifact.
5. Write the simplified design and implementation plan under `docs/exchange/`.
6. Use the `superpowers:writing-plans` quality bar for the implementation section: exact files, bite-sized steps, concrete commands, and expected verification results.
7. Review with `grill-me-smartly` by default:
   - First check whether the `grill-me-smartly` skill can be found/read and whether subagent capability is available.
   - If available, run a review subagent against the generated artifact and relevant source files. Capture the subagent id and summarize concrete review findings in `docs/exchange/grill-me-smartly-YYYYMMDD-HHMM-<topic>.md`.
   - If `grill-me-smartly` cannot be found/read or no subagent capability is available, run the fallback review checklist inline and record the exact fallback reason in the generated artifact or final summary.
8. Apply obvious corrections from the review to the artifact.
9. Return the summary, changed path, remaining owner decisions, and the review method used (`grill-me-smartly` subagent with id, or inline fallback with reason).

## Fallback Review Checklist

Check:

- The source issue or requirement is traceable in `Source And Alignment`.
- The plan reflects existing docs instead of inventing a new architecture.
- Missing strict folders are acknowledged.
- Module boundaries are explicit.
- Verification commands are concrete.
- Open questions are separated from implementation steps.

## Notes For Loose Docs Repositories

When a repository stores all planning context directly under `docs/`, treat those files as the source of truth even if their names differ from the strict workflow. For example:

- `PRD.md` can replace structured product requirements.
- `architecture.md` can replace ARD.
- `project-status.md` can replace implementation reality notes.
- `team-collaboration-breakdown.md` can replace formal planning indexes.

Prefer adapting to the repository's current documentation culture over creating a new folder hierarchy.
