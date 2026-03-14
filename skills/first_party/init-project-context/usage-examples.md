# Usage Examples

These examples show how `init-project-context` should behave in realistic repository discovery and context-closure sessions.

## Example 1: Very Vague New Project

### User Request

```text
This is an internal AI tool project. I need help figuring out what this repo is actually for before we build anything.
```

### Expected Behavior

1. Inspect the repository before asking questions.
2. Summarize confirmed facts briefly.
3. Identify the highest-impact missing context.
4. Ask one narrowing question about the current milestone or smallest useful closed loop.
5. Refuse to draft `AGENTS.md` or `CLAUDE.md` until the project purpose and scope are concrete enough.

### Good Follow-Up Question

```text
I can see the repo structure, but the project itself is still loosely defined. What is the smallest meaningful thing this repository is supposed to deliver first?
```

### What Not To Do

- Do not ask five broad questions at once.
- Do not start drafting instruction files from "AI tool project" alone.

## Example 2: Course Project With Unclear Scope

### User Request

```text
This is a course project for a cloud-based web app. Help me initialize the project context.
```

### Expected Behavior

1. Discover the current repository state and any existing concept docs.
2. Do not ask for technical facts already visible in the repository.
3. Ask what the project is for, how it will be evaluated, and what must be delivered.
4. Draft `project-context.md` and `tech-stack-investigate.md`.
5. Treat agent instruction files as optional follow-up output.

### Good Follow-Up Question

```text
I can already see that this is a cloud web app repo, but I still need the real boundary for the assignment. What are the required features, and what is intentionally out of scope for the course project?
```

### What Not To Do

- Do not jump straight into agent rules if the project itself is still fuzzy.
- Do not mistake candidate stack notes for finalized implementation truth.

## Example 3: User Pushes For Immediate Output

### User Request

```text
Just write AGENTS.md and CLAUDE.md directly.
```

### Expected Behavior

1. Check whether the repository has enough stable context.
2. If not, explain why direct drafting would lock in bad assumptions about the project.
3. Continue discovery until project purpose, scope, and candidate technical direction are strong enough.
4. Stop at foundation docs if critical ambiguity remains.

### Good Response Shape

```text
The repository does not yet have enough stable project context for safe instruction drafting. I need to close the project purpose, required scope, and candidate technical direction first so the files do not encode weak assumptions.
```

### What Not To Do

- Do not comply immediately when the project description is still fuzzy.
- Do not invent rules that the repository and user have not established.

## Example 4: Project Context Is Primary, Agent Files Are Secondary

### User Request

```text
I need the context docs to explain the project itself. Agent rules are not the main point.
```

### Expected Behavior

1. Re-center the process around project definition, deliverables, and boundaries.
2. Draft the context files first.
3. Keep any later `AGENTS.md` or `CLAUDE.md` content thin and dependent on the shared context docs.

### Good Response Shape

```text
The first step is to make the project itself explicit: what it is for, what must be delivered, and what is out of scope. I will treat agent entry files as optional follow-up outputs instead of the main deliverable.
```

## Stop Condition

Instruction drafting is allowed only when all of these are true:

- The current project purpose is explicit.
- The primary users or operators are explicit.
- The current milestone is explicit.
- The required deliverables are explicit.
- In-scope / out-of-scope is explicit enough for planning.
- There is at least a provisional candidate technical direction, or an explicit statement that it is still open.
- Future planning would not depend on repeated oral clarification of core context.
