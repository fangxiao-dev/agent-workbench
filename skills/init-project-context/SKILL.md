---
name: init-project-context
description: Use when starting a new or under-documented repository that lacks a clear project definition. Use this skill when the project purpose, deliverables, boundaries, or candidate tech direction are still vague and need to be clarified before implementation planning. Default to stabilizing project context first; only draft agent instruction files later if the user explicitly wants them.
---

# Init Project Context

## Overview

Initialize project foundation before feature planning. The goal is to turn a vague repository into one with enough project definition, scope boundaries, and technical direction to support later planning.

Common path for early-stage repositories:
`stabilize project meaning -> choose technical direction -> write solution-level plan -> optionally prepare WT-PM task artifacts`

**REQUIRED SUB-SKILL:** Use `brainstorming` for the conversational discovery style.

This skill does **not** start by writing agent entry files. It first stabilizes the project itself. Agent entry files are optional follow-up outputs, not the default center of gravity.

If the user clearly intends to enter WT-PM or another task/worktree workflow next, this skill may continue past foundation docs into solution-level planning and then an execution handoff. That extension is still part of project-context initialization; it is not a replacement for `wt-plan`.

When agent entry files are needed, treat `AGENTS.md` as the single source of truth. Do not maintain parallel content in `CLAUDE.md`, `GEMINI.md`, or similar files. If a tool-specific filename is required, first try a filesystem symlink that points back to `AGENTS.md`. If symlink creation is blocked by platform permissions, fall back to a hard link. Only fall back to a copied file when linking is impossible.

## When to Use

Use this skill when:
- A repository has no usable agent entry file strategy
- Existing docs are too thin or too vague for agent-assisted development
- A user can describe the project only loosely
- You need to establish project goals, scope, constraints, and candidate tech direction before planning features
- You want foundation docs that future planning sessions can reuse

Do not use this skill for:
- Small single-task coding work in an already well-documented repository
- Updating one small section of an existing instruction file without broader ambiguity

## Core Principle

**Do not write instruction files or implementation plans from a fuzzy project description.**

First collect enough facts and boundaries to make planning reliable. By default, stabilize the project definition first and defer agent instructions until the user explicitly asks for them.

**Do not jump directly from a fuzzy project description to WT-PM task creation.** Stabilize foundation docs and solution-level intent first.

## Output Model

This skill works in three layers, plus optional agent entry docs.

### Layer 1: Foundation Docs

Create or draft these first:
- `project-context.md`
- `tech-stack-investigate.md`

Purpose: project definition. These documents explain what the project is, why it exists, what milestone matters now, and the provisional technical direction.

### Layer 2: Solution-Level Planning Docs

Create these after Layer 1 is stable when the user needs an approved implementation direction:
- `docs/plans/*`

Purpose: solution planning. These documents freeze product, design, and technical direction for a milestone or feature area. They guide execution, but they are not the same thing as tracked task plans.

### Layer 3: Execution Handoff Docs

Create these only when the user is ready to decompose work into tracked tasks:
- `plans/todo_current.md`
- `plans/workplans/*`

Purpose: execution tracking. These artifacts break approved solution intent into task-level units for WT-PM or similar workflows.

### Optional Layer 4: Agent Entry Docs

Create these only after Layer 1 is stable and only if the user explicitly wants them:
- `AGENTS.md`
- tool-specific aliases such as `CLAUDE.md` or `GEMINI.md` that resolve back to `AGENTS.md`

If the repository is still ambiguous, stop after Layer 1 and list the remaining open questions. Do not create solution plans or execution-tracking artifacts from an unresolved project definition.

## Workflow

### Phase 1: Repo Discovery

Before asking questions, inspect the repository for discoverable facts:
- top-level structure
- runtime manifests and lockfiles
- backend/frontend entrypoints
- test commands
- existing docs, plans, and architecture notes
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
- project purpose
- primary user or audience
- current milestone
- in-scope / out-of-scope
- required deliverables
- educational or business context
- candidate technical direction
- hard constraints

If the user answers vaguely, do not move on. Narrow the current question until it is actionable.

Use this pattern:
1. summarize what is already known
2. state what is still unclear
3. ask one high-value question

### Phase 3: Foundation Drafting

Once the repository is sufficiently defined, draft the foundation docs using the templates in `templates/`.

Use repository evidence plus user answers. Mark uncertain content explicitly instead of pretending certainty.

### Phase 4: Solution Planning

Once the foundation docs are stable and the user wants an implementation direction:
- create or update solution-level plans under `docs/plans/*`
- use those plans to freeze product, design, and technical direction
- treat these plans as the source of truth for what should be built at the solution level

Rules:
- use `docs/plans/*` to lock intent before task decomposition
- do not confuse a solution-level plan with WT-PM task plans
- if the design is still changing, stay here instead of preparing tracked execution artifacts

### Phase 5: Execution Handoff

Only after the solution direction is approved and the user wants tracked execution:
- create or update `plans/todo_current.md`
- create or update `plans/workplans/*`
- decompose the approved plan into task-level work with dependencies and sequencing

Rules:
- use `plans/todo_current.md` plus `plans/workplans/*` only when the user is ready to break work into tracked tasks
- if both `docs/plans/*` and WT-PM task plans exist, the task-level plans must follow the approved higher-level plan unless the user intentionally revises the design
- this phase prepares handoff into WT-PM; it does not replace `wt-plan` branch/worktree lifecycle management

#### No-git bootstrap mode

If the repository is not yet a git repo or cannot support worktrees yet:
- it is still acceptable to prepare `plans/todo_current.md` and `plans/workplans/*` as bootstrap artifacts
- explicitly mark them as pre-WT-PM bootstrap files
- do not pretend branches, trunk, or worktrees already exist
- defer formal `wt-plan` execution until git/trunk/worktree prerequisites are available

### Phase 6: Instruction Drafting

Only after foundation docs are strong enough, and after any needed planning/handoff layers are in place:
- draft `AGENTS.md`
- identify which agent-specific filenames are actually required
- if needed, create aliases from those filenames back to `AGENTS.md`
- use this fallback order: symlink, then hard link, then copied file with a warning about duplication risk
- keep one authoritative content file instead of duplicating instructions across agents

Do not dump all details into the entry files. Keep them as navigation and operating instructions, not giant project encyclopedias.

Before creating any compatibility alias, confirm the user really uses that agent. Example: if the user confirms Claude tooling, create `CLAUDE.md` as a symlink to `AGENTS.md`, or a hard link if symlink permissions are unavailable. If there is no confirmed consumer, do not create speculative aliases.

If WT-PM or tracked execution is expected, keep the agent entry files aligned with the layered planning model:
- foundation docs define the project
- `docs/plans/*` define approved solution intent
- `plans/todo_current.md` plus `plans/workplans/*` define tracked execution

## Sufficiency Check

The project is ready for instruction drafting only if all of these are true:

- The project purpose is explicit
- The primary users or operators are explicit
- The current milestone or delivery horizon is explicit
- Required deliverables are explicit
- In-scope and out-of-scope are explicit enough for planning
- There is at least a provisional candidate tech direction or an explicit statement that tech selection is still open
- Future planning would not depend on repeated oral clarification of core context

If any of these fail, continue discovery instead of drafting instruction files.

The project is ready for WT-PM handoff only if all of these are also true:

- The current milestone is explicit enough to plan task boundaries
- The first task decomposition is explicit enough to create task rows
- Dependencies and sequencing are clear enough to assign order or parallelism
- The user actually wants tracked execution rather than direct implementation from an approved plan

If any of these fail, keep working at the foundation or solution-planning layer instead of creating execution-tracking artifacts.

## Heuristics

### Treat as Project-Specific

Usually keep in foundation docs or project entry docs:
- project background and rationale
- business domain and user scenarios
- milestone status
- required deliverables
- in-scope / out-of-scope boundaries
- technical direction that is still provisional

Usually keep in solution-level planning docs:
- approved product flow
- architecture direction for the current milestone
- implementation sequencing at the feature level
- milestone-specific acceptance criteria

Usually keep in execution-tracking docs:
- task rows and task ids
- per-task dependencies
- task-local findings and progress logs
- WT-PM execution status

### Treat as Reusable Template Material

Usually fit into instruction scaffolds:
- section structures
- lightweight reading order
- links back to shared context docs
- agent-specific link targets and compatibility notes

## Question Areas

When discovery leaves gaps, prioritize these topics in order:

1. What is the project actually for?
2. Is it a real product, an internal tool, a prototype, or a course project?
3. What is the smallest milestone that matters right now?
4. What must be delivered?
5. What is explicitly out of scope?
6. What technical direction is currently being considered?
7. Does the user want a solution-level plan after context stabilization?
8. Does the user intend to enter WT-PM or another tracked execution workflow next?
9. Which agent entry filenames are actually needed, if any?

## Drafting Rules

- Prefer concise, operational language
- Separate facts from assumptions
- Separate project definition from technical speculation
- Prefer templates with placeholders over fake certainty
- Preserve future extensibility without forcing agent scaffolding too early
- Separate project definition, solution planning, and execution tracking instead of collapsing them into one file set
- Keep `AGENTS.md` as the only maintained instruction body
- Prefer links over duplicated agent-specific instruction files
- Use symlinks first, hard links second, copies last
- Do not create agent-specific aliases until their consumers are confirmed
- Do not create WT-PM task artifacts until the approved solution direction is stable enough to decompose

## Common Mistakes

| Mistake | Better Approach |
|---|---|
| Drafting `AGENTS.md` immediately | Build foundation docs first |
| Asking broad questions in batches | Ask one high-value question at a time |
| Treating vague goals as sufficient | Narrow them to a milestone and success condition |
| Jumping straight from context discovery to WT-PM tasks | Freeze solution-level intent in `docs/plans/*` first |
| Repeating repo facts back as questions | Discover locally first |
| Making agent workflow the main story | Make the project itself the main story |
| Stuffing project meaning into agent files | Keep the core context in shared project docs |
| Pretending unknowns are known | Mark open questions explicitly |
| Maintaining separate `AGENTS.md` and `CLAUDE.md` bodies | Keep one `AGENTS.md` and use links or a last-resort copy only when required |
| Letting task plans drift from approved design docs | Treat `docs/plans/*` as the higher-level source of truth unless the design is intentionally revised |

## Files and Templates

Use the templates in this skill directory:
- `templates/project-context.md`
- `templates/tech-stack-investigate.md`
- `templates/AGENTS.draft.md`

Use the first two templates by default. Only use the `AGENTS.md` template when the user explicitly asks for agent-facing files. If a Claude-compatible filename is needed, alias `CLAUDE.md` to `AGENTS.md` using a symlink first, then a hard link if needed, instead of drafting a separate file.

If the user intends to enter WT-PM or file-based execution tracking after context stabilization, this skill may need to point to:
- `docs/plans/*` for solution-level plans
- `plans/todo_current.md`
- `plans/workplans/*`
- WT-PM / `planning-with-files` conventions

Do not duplicate the full `wt-plan` or `planning-with-files` workflow here. Point to those conventions when execution tracking is needed; keep this skill focused on preparing the repository context and handoff state.

For realistic usage patterns and conversation shape, see `usage-examples.md`.
