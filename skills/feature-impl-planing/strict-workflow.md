# Strict Feature Implementation Planning Workflow

Use this workflow when the repository follows the structured planning layout and the user wants the original strict process.

## Preconditions

The normal input is a requirement alignment artifact:

- `docs/exchange/requirement-alignment-YYYYMMDD-HHMM-<topic>.md`

Expected project paths:

- `docs/exchange/`
- `docs/func-design/`
- `docs/impl-plans/`
- `docs/top-level-knowledge/`
- `test-cases/`

If the user provides only a raw requirement in strict mode, stop and ask them to run or provide requirement alignment first. Do not recreate the full alignment workflow here.

## Read

- Requirement alignment artifact under `docs/exchange/`
- `docs/func-design/README.md`
- Existing related Func Design files under `docs/func-design/`
- `docs/impl-plans/README.md`
- Existing related Implementation Plans under `docs/impl-plans/`
- `docs/top-level-knowledge/ubiquitous-language.md`
- `docs/top-level-knowledge/ard.md` when the aligned requirement touches shared architecture, role boundaries, external contracts, lifecycle, inventory flow, or major feature surfaces
- `test-cases/entry.md` before choosing verification for behavior, contract, workflow, integration, or verification-sensitive changes

## Write

- Func Design: `docs/func-design/YYYY-MM-DD-<topic>.md`
- Implementation Plan: `docs/impl-plans/YYYY-MM-DD-<topic>.md`

Do not write to `docs/superpowers/`.

`grill-me-smartly` ledgers are temporary process records under the OS temp
directory. Do not write grill review notes into `docs/exchange/`, and do not
link temporary grill ledgers from the Func Design, Implementation Plan, README
indexes, or other formal project documents. Apply accepted review context
directly into the formal documents.

## Workflow

1. Announce strict workflow mode.
2. Read the requirement alignment artifact and relevant existing docs.
3. Create or update the Func Design.
4. If the Func Design reveals new product intent, PRD conflict, Top Level Knowledge change, or owner decision, stop and return a decision packet. Do not continue to the Implementation Plan until resolved.
5. If there are no owner decisions, create the Implementation Plan.
6. Use the `superpowers:writing-plans` quality bar: exact files, bite-sized checklist steps, verification-first steps where practical, concrete commands, and expected results.
7. Review Gate: invoke and fully follow `grill-me-smartly` on the requirement alignment artifact, Func Design, and Implementation Plan. You MUST spawn or reuse one standing answer-only subagent for the review. Do not claim a review from main-session self-review alone.
8. Apply obvious corrections and accepted review context to the Func Design and Implementation Plan until the formal documents stand alone without the grill ledger.
9. Keep the grill ledger as an OS-temp intermediate record only; do not create a repo-local review note or link it from formal docs.
10. Return a compact summary, changed paths, corrections applied, review method used, and unresolved owner decisions.

## Mandatory Review Gate Checklist

Before returning final output, verify:

- [ ] A standing answer-only subagent was spawned or reused.
- [ ] The subagent answered at least one concrete `grill-me` question, or the temp grill ledger explains why no locally answerable question existed.
- [ ] The same subagent was reused for follow-up questions when more than one question was needed.
- [ ] The OS-temp grill ledger records subagent id, questions, answers, evidence, uncertainty, and corrections.
- [ ] Obvious corrections and accepted context from the subagent were applied to the Func Design and/or Implementation Plan.
- [ ] Formal documents do not link to the temporary grill ledger or depend on it for required context.
- [ ] The subagent was closed after review.

Invalid review patterns:

- Writing a `grill-me-smartly` review note based only on main-session self-review.
- Saying "reviewed" without a subagent id and subagent answer evidence.
- Treating subagent authorization as optional in strict workflow.

## Func Design Structure

```markdown
# <Feature Name> Func Design

## Context

## Goals

## Non-Goals

## User And Domain Behavior

## Data And Contract Changes

## Module Boundaries

## Error Handling And Edge Cases

## Verification

## Open Questions
```

Rules:

- Use canonical terms from `docs/top-level-knowledge/ubiquitous-language.md`.
- Link back to the requirement alignment artifact.
- Keep implementation detail high enough to guide planning, but do not turn the Func Design into a step-by-step task list.
- Update `docs/func-design/README.md` when a new long-lived design should appear in the index.

## Implementation Plan Requirements

The Implementation Plan is temporary and executable by a coding agent with limited context.

Include:

- exact files to create or modify
- bite-sized checkbox steps
- test-first or verification-first steps where practical
- concrete commands with expected results
- no placeholders or vague "add validation" steps

Update `docs/impl-plans/README.md` only when the project convention requires it.

## Review Note Structure

Use this structure only inside the temporary grill ledger or transient review
summary. Do not save it as a repo-local formal artifact and do not link it from
formal planning documents.

```markdown
# Feature Impl Planing Review: <topic>

## Source
- Requirement alignment: `<path>`
- Func Design: `<path>`
- Implementation Plan: `<path>`
- Created at: <ISO timestamp>

## Review Summary
- Corrected:
- Confirmed:
- Risk:

## Grill Me Smartly Decisions
- Resolved locally:
- Needs owner:
- Recommended default:

## Subagent Review
- Agent id:
- Status:
- Questions asked:
- Corrections required:
- Corrections applied:
- Closed: yes/no

## Subagent Answer Summary
| ID | Question | Answer | Evidence | Uncertainty | Correction |
| --- | --- | --- | --- | --- | --- |

## Applied Changes
- `<path>` - <summary>

## Handoff
- Ready for implementation: yes/no
- Required owner decisions before implementation:
- Suggested execution mode:
```
