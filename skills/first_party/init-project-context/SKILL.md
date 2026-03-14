---
name: init-project-context
description: Use when starting a new or under-documented repository that lacks stable project context, goals, boundaries, rules, or agent instruction files. Use before writing AGENTS.md or CLAUDE.md, before planning real features, or when a project description is still vague and needs guided discovery, foundation docs, and draft instruction scaffolds.
---

# Init Project Context

## Overview

Initialize project foundation before feature planning. The goal is to turn a vague repository into one with enough context, rules, and explicit boundaries to support later planning and agent instructions.

**REQUIRED SUB-SKILL:** Use `brainstorming` for the conversational discovery style.

This skill does **not** start by writing `AGENTS.md` or `CLAUDE.md`. It first stabilizes the project's foundation, then drafts those files from the stabilized inputs.

## When to Use

Use this skill when:
- A repository has no `AGENTS.md` or `CLAUDE.md`
- Existing docs are too thin or too vague for agent-assisted development
- A user can describe the project only loosely
- You need to establish goals, scope, workflow, rules, and constraints before planning features
- You want foundation docs that future planning sessions can reuse

Do not use this skill for:
- Small single-task coding work in an already well-documented repository
- Updating one small section of an existing instruction file without broader ambiguity

## Core Principle

**Do not write instruction files from a fuzzy project description.**

First collect enough facts and rules to make planning reliable. Only then draft `AGENTS.md` and `CLAUDE.md`.

## Output Model

This skill works in two layers.

### Layer 1: Foundation Docs

Create or draft these first:
- `project-context.md`
- `project-goals-and-scope.md`
- `project-rules-draft.md`
- `agent-instruction-design.md`

### Layer 2: Agent Entry Docs

Draft these only after Layer 1 is stable:
- `AGENTS.md`
- `CLAUDE.md`

If the repository is still ambiguous, stop after Layer 1 and list the remaining open questions.

## Workflow

### Phase 1: Repo Discovery

Before asking questions, inspect the repository for discoverable facts:
- top-level structure
- runtime manifests and lockfiles
- backend/frontend entrypoints
- test commands
- existing docs, plans, rule folders, or skill folders
- signals of workflow conventions such as task trackers, worktrees, CI, schema directories

Record findings under these buckets:
- `confirmed facts`
- `reasonable inferences`
- `critical gaps`
- `conflicts`

Never ask the user for information that the repository already makes clear.

### Phase 2: Context Closure

Use guided discovery to close the highest-impact gaps.

Ask one question at a time. Each question must help determine at least one of:
- project goal
- primary user or audience
- current milestone
- in-scope / out-of-scope
- hard rules or constraints
- workflow expectations
- multi-agent strategy

If the user answers vaguely, do not move on. Narrow the current question until it is actionable.

Use this pattern:
1. summarize what is already known
2. state what is still unclear
3. ask one high-value question

### Phase 3: Foundation Drafting

Once the repository is sufficiently defined, draft the four foundation docs using the templates in `templates/`.

Use repository evidence plus user answers. Mark uncertain content explicitly instead of pretending certainty.

### Phase 4: Instruction Drafting

Only after foundation docs are strong enough:
- draft `AGENTS.md`
- draft `CLAUDE.md`
- identify what belongs in repo-level instruction files versus separate rule files

Do not dump all details into the entry files. Keep them as navigation and operating instructions, not giant project encyclopedias.

## Sufficiency Check

The project is ready for instruction drafting only if all of these are true:

- The project goal is explicit
- The primary users or operators are explicit
- The current milestone or delivery horizon is explicit
- In-scope and out-of-scope are explicit enough for planning
- The main technical entrypoints are known
- The architecture or directory boundaries are explicit enough to avoid obvious drift
- At least one set of hard rules is defined
- Future planning would not depend on repeated oral clarification of core context

If any of these fail, continue discovery instead of drafting instruction files.

## Heuristics

### Treat as Project-Specific

Usually keep in foundation docs or project entry docs:
- business domain and user scenarios
- milestone status
- repository paths and commands
- environment-specific workflows
- frozen contracts tied to this codebase
- task tracker locations

### Treat as Reusable Template Material

Usually fit into instruction scaffolds:
- section structures
- collaboration patterns
- review / testing / DoD structure
- worktree conventions
- agent-specific role separation
- maintenance rules for instruction files

### Treat as Rule Candidates

Usually belongs in separate rules or skills:
- stable contract policy
- planning lifecycle
- worktree lifecycle
- safety constraints
- update responsibilities

## Question Areas

When discovery leaves gaps, prioritize these topics in order:

1. What is the project trying to deliver right now?
2. Who uses or operates it?
3. What is the smallest milestone that matters?
4. What is explicitly out of scope?
5. What must never be broken?
6. How should agents collaborate in this repository?
7. Which agents need to be supported?

## Drafting Rules

- Prefer concise, operational language
- Separate facts from assumptions
- Separate stable rules from project narrative
- Prefer templates with placeholders over fake certainty
- Preserve future extensibility for multi-agent support

## Common Mistakes

| Mistake | Better Approach |
|---|---|
| Drafting `AGENTS.md` immediately | Build foundation docs first |
| Asking broad questions in batches | Ask one high-value question at a time |
| Treating vague goals as sufficient | Narrow them to a milestone and success condition |
| Repeating repo facts back as questions | Discover locally first |
| Stuffing all content into `AGENTS.md` | Split foundation docs, rules, and entry docs |
| Pretending unknowns are known | Mark open questions explicitly |

## Files and Templates

Use the templates in this skill directory:
- `templates/project-context.md`
- `templates/project-goals-and-scope.md`
- `templates/project-rules-draft.md`
- `templates/agent-instruction-design.md`
- `templates/AGENTS.draft.md`
- `templates/CLAUDE.draft.md`

Draft from those templates rather than improvising structure each time.

For realistic usage patterns and conversation shape, see `usage-examples.md`.
