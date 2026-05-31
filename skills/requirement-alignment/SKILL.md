---
name: requirement-alignment
description: Use whenever a new or changed requirement for prj-supplyer-webapp needs to be checked against PRD, ARD, Ubiquitous Language, or other Top Level Knowledge before Func Design or Implementation Plan work. This is the mandatory first step for feature workflow alignment, demand drift checks, scope clarification, requirement proposals, and deciding whether Top Level Knowledge should change.
---

# Requirement Alignment

Align a requirement input with this repository's stable product knowledge before any Func Design or Implementation Plan is written.

This skill adapts the intent-discovery parts of `superpowers:brainstorming`, but the project path rules here override the default superpowers document destinations. Do not write to `docs/superpowers/` for this workflow.

## Purpose

Use this skill to turn a raw requirement into an aligned requirement artifact. The output is a compact `docs/exchange/` note that a later design-planning skill can consume without reloading the full conversation.

This skill does not create Func Design documents and does not create Implementation Plans.

## Required Project Paths

Read stable knowledge from:

- `docs/top-level-knowledge/prd.md`
- Relevant PRD files under `docs/top-level-knowledge/`
- `docs/top-level-knowledge/ard.md` when architecture boundaries, role boundaries, data flow, Lark-backed contracts, order lifecycle, inventory flow, or major feature surfaces are involved
- `docs/top-level-knowledge/ubiquitous-language.md`
- `docs/hands-on-knowledge/entry-map.md` only when the requirement names a known integration or the project rules require it

Write the focused requirement artifact to:

- `docs/exchange/req-YYYYMMDD-HHMM-<topic>.md`

If Top Level Knowledge should change, update only after the user approves the proposed change. The approved long-lived edits go under `docs/top-level-knowledge/`.

## Workflow

1. Announce that you are using this skill for requirement alignment.
2. Identify the requirement input and give it a short topic slug.
3. Read the required Top Level Knowledge files before asking detailed questions.
4. Use the `superpowers:brainstorming` style of clarification: ask one focused question at a time when the requirement has unresolved product intent, scope, or success criteria.
5. Produce an alignment proposal for the user before changing long-lived docs.
6. After user approval, write the exchange artifact. If approved Top Level Knowledge changes exist, update those files in the same pass.
7. Return only a concise summary, changed paths, and any remaining owner decisions.

## Alignment Proposal

Before writing or editing long-lived knowledge, present this structure:

```markdown
## Requirement Alignment Proposal

### Focused Requirement
<1-3 paragraphs describing the requirement using canonical project terms>

### Top Level Knowledge Fit
- PRD fit:
- ARD fit:
- Ubiquitous Language fit:

### Drift Or Conflict Check
- Confirmed alignment:
- Possible drift:
- Out of scope:

### Proposed Long-Lived Knowledge Changes
- File:
- Change:
- Reason:

### Owner Decisions
- <decision question, or "None">

### Recommended Next Step
- Write exchange artifact only
- Write exchange artifact and update Top Level Knowledge
- Stop for owner decision
```

If there are no owner decisions and no Top Level Knowledge edits, the user may approve moving directly to the exchange artifact.

## Exchange Artifact Format

Use this exact structure for `docs/exchange/req-YYYYMMDD-HHMM-<topic>.md`:

```markdown
# Requirement Alignment: <topic>

## Source
- Created at: <ISO timestamp>
- Requirement input: <short quote or summary>
- Aligned by: requirement-alignment skill

## Focused Requirement
<the approved requirement description>

## Knowledge Sources Checked
- `docs/top-level-knowledge/prd.md`
- `<specific PRD or Top Level Knowledge file>`
- `docs/top-level-knowledge/ubiquitous-language.md`
- `<other file, if used>`

## Alignment Result
- PRD fit:
- ARD fit:
- Ubiquitous Language fit:
- Scope boundary:

## Top Level Knowledge Changes
- Updated: `<path>` - <summary>
- Proposed but not updated: <summary or "None">

## Owner Decisions
- Resolved:
- Still needed:

## Handoff To Feature Design Planning
- Recommended Func Design path: `docs/func-design/YYYY-MM-DD-<topic>.md`
- Recommended Implementation Plan path: `docs/impl-plans/YYYY-MM-DD-<topic>.md`
- Notes for design:
- Notes for verification:
```

Keep the exchange artifact compact. It should preserve decisions and constraints, not the full discussion transcript.

## Long-Lived Knowledge Rules

- Never silently edit `docs/top-level-knowledge/`.
- Ask the user to approve the alignment proposal first.
- Prefer small, explicit edits to the relevant PRD, ARD, or Ubiquitous Language file.
- If a term is ambiguous, propose a Ubiquitous Language update instead of inventing ad hoc wording in the exchange note.
- If the requirement conflicts with the PRD, stop and ask the user to choose whether the PRD changes or the requirement is rejected/deferred.

## User-Facing Output

During the workflow, show the user only:

- Summary bullets
- Drift or conflict bullets
- Owner decision questions
- Paths written or changed

Do not paste full intermediate drafts into the main session after the exchange artifact has been written. Reference the file path instead.
