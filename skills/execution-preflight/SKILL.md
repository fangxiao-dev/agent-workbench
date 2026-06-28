---
name: execution-preflight
description: Use before starting a substantial task, including any prompt that attaches or references a design doc, review doc, execution plan, implementation plan, audit material, or handoff; also use before implementation, verification runs, or external-environment workflows to surface owner authorizations and HITL decisions that could block autonomous execution, including subagents, staging/Lark smoke, external mutations, open decisions, and verification scope.
---

# Execution Preflight

Use this skill before beginning a non-trivial task when missing owner authorization or human decisions could interrupt execution later. The goal is to collect the minimum useful permissions and decisions up front, then proceed without avoidable mid-task stalls.

Do not use it for tiny read-only answers, simple local commands, or edits that clearly need no external access, delegation, or owner choice.

## Workflow

### 1. Decide If Preflight Is Needed

Run preflight when the task is about to start and any of these are plausible:

- The user's prompt attaches, links, or points to a document, plan, design, review, audit, handoff, or execution artifact. Treat this as non-small by default, even if the visible request is short.
- Subagents could materially improve research, review, implementation, or verification.
- The task may need staging, Lark smoke, real database reads/writes, browser smoke, Lexware, email, production-like checks, or other external systems.
- The task has open product, UX, schema, data cleanup, migration, or acceptance decisions.
- The user wants autonomous end-to-end execution and missing authorization could block it later.

Skip preflight when the task is a small explanation, local-only inspection, or a clearly bounded edit with no external or HITL dependency. If skipped, continue normally.

Completion criterion: either preflight is skipped with an obvious reason, or the needed authorization categories are identified before execution begins.

### 2. Build The Authorization Map

Inspect the user request and immediate context just enough to identify likely blockers. Do not start implementation while building this map.

Check these categories:

- **Delegation:** whether subagents may be used, and for what roles: research, review, implementation, verification.
- **External environments:** whether staging, Lark smoke, real database access, browser smoke, Lexware, email, or production-like checks are allowed; distinguish read-only from mutation.
- **Data risk:** whether migrations, cleanup, test-order deletion, or destructive staging actions need explicit permission.
- **Open decisions:** business, UX, schema, naming, lifecycle, or acceptance questions that would change the work.
- **Verification:** expected test/build/smoke scope and whether failures should block completion.
- **Git flow:** whether commits, branches, staging, pushes, or PRs are in scope.

Respect current host and conversation restrictions. If subagents, external tools, or mutations are unavailable or explicitly forbidden, mark that category as blocked/unavailable instead of asking the owner to authorize it.

Completion criterion: every category that could block this task is either marked "not needed", "safe default", or "needs owner answer".

### 3. Ask A Compact Preflight

Ask before execution, not halfway through. Keep the ask task-specific and short.

Prefer this shape:

```markdown
Preflight before I start:
- Subagents: <needed/not needed; proposed scope>
- External checks: <local only/staging/Lark smoke/Lexware/etc.; read-only or mutating>
- HITL decisions: <specific open questions, or none>

Please confirm <the narrow decision(s)>.
```

If a structured user-input tool is available, use it for one to three short questions. Otherwise ask in plain text. Do not ask for blanket permission to do everything; request only what this task is likely to need.

If the user already granted a category in the current active task, do not ask again. Restate it in the authorization record and only ask for missing or ambiguous categories.

Completion criterion: the user can answer with a concise yes/no or scoped permission, and no important category is hidden behind vague wording.

### 4. Record The Execution Authorization

After the user answers, restate the usable scope before continuing:

```markdown
Execution authorization for this task:
- Subagents: <allowed/blocked/scope>
- External checks: <allowed/blocked/scope>
- Mutations/data cleanup: <allowed/blocked/scope>
- Open decisions: <resolved/pending>
```

Treat authorization as task-scoped unless the user explicitly grants a standing rule. Do not silently reuse permission from an unrelated prior task.

Completion criterion: the active task has a clear permission boundary that later agents or resumptions can follow.

### 5. During Execution

If a new blocker appears outside the recorded scope, stop and ask before crossing it. If the blocker is inside the recorded scope, proceed without re-asking.

In the final response, mention only authorization gaps that affected completion. Do not list every preflight decision unless it matters to the outcome.

Completion criterion: execution either completes within the recorded scope, or any unresolved HITL blocker is surfaced promptly with the exact missing decision.

## Failure Modes

- Asking too late, after implementation has already run into a missing authorization.
- Asking too broadly, causing the owner to grant vague permission that is unsafe or hard to apply.
- Asking about subagents when the current environment or conversation explicitly forbids them.
- Treating staging or Lark smoke read access as permission for mutations.
- Treating a previous task's permission as reusable for the current task without an explicit standing rule.
