# Usage Examples

These examples show how `init-project-context` should behave in realistic repository discovery and context-closure sessions.

## Example 1: Very Vague New Project

### User Request

```text
This is an internal AI tool project. I want to set up agent workflow first.
```

### Expected Behavior

1. Inspect the repository before asking questions.
2. Summarize confirmed facts briefly.
3. Identify the highest-impact missing context.
4. Ask one narrowing question about the current milestone or smallest useful closed loop.
5. Refuse to draft `AGENTS.md` or `CLAUDE.md` until the project goal is concrete enough.

### Good Follow-Up Question

```text
I can see the repo structure, but the current delivery target is still unclear. What is the smallest end-to-end workflow this project must complete in its first milestone?
```

### What Not To Do

- Do not ask five broad questions at once.
- Do not start drafting instruction files from "AI tool project" alone.

## Example 2: Repository Has Code But Missing Rules

### User Request

```text
This repo already has frontend and backend code. Help me initialize AGENTS.md and CLAUDE.md.
```

### Expected Behavior

1. Discover the stack, entrypoints, tests, and major directories from the repo.
2. Do not ask for facts already visible in the repository.
3. Ask for the current in-scope / out-of-scope boundary and non-breakable constraints.
4. Draft foundation docs first, then prepare instruction-file scaffolds.

### Good Follow-Up Question

```text
I can already see the stack and repository layout. Before drafting instruction files, I need the boundary for this phase: which parts are in scope right now, and which parts should agents avoid changing?
```

### What Not To Do

- Do not ask "what tech stack are you using?" if manifests already answer it.
- Do not put all repo facts directly into `AGENTS.md`.

## Example 3: User Pushes For Immediate Output

### User Request

```text
Just write AGENTS.md and CLAUDE.md directly.
```

### Expected Behavior

1. Check whether the repository has enough stable context.
2. If not, explain why direct drafting would lock in bad assumptions.
3. Continue discovery until goal, scope, and rules are strong enough.
4. Stop at foundation docs if critical ambiguity remains.

### Good Response Shape

```text
The repository does not yet have enough stable project context for safe instruction drafting. I need to close the current milestone, scope boundary, and hard constraints first so the files do not encode weak assumptions.
```

### What Not To Do

- Do not comply immediately when the project description is still fuzzy.
- Do not invent rules that the repository and user have not established.

## Stop Condition

Instruction drafting is allowed only when all of these are true:

- The current project goal is explicit.
- The primary users or operators are explicit.
- The current milestone is explicit.
- In-scope / out-of-scope is explicit enough for planning.
- At least one set of hard rules is explicit.
- Future planning would not depend on repeated oral clarification of core context.
