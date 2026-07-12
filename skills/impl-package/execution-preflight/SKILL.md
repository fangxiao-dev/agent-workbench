---
name: execution-preflight
description: Use before starting a task from a handoff, plan, review, audit, or execution artifact to extract only permissions, owner authorizations, HITL decisions, and subagent mode before work begins.
---

# Execution Preflight

Use this skill before beginning work from a handoff, plan, review, audit, issue list, or execution artifact. The job is narrow: review any current-session authorization, read the referenced authorization sources, extract permissions and human-in-the-loop decisions, and ask the owner for missing authorization before execution begins.

Preflight is not readiness analysis. Do not recommend implementation order, inspect code for solution shape, create worktrees, run tests, start subagents, or make edits while this skill is running.

## Workflow

### 1. Decide If Preflight Is Needed

Run preflight when the active request asks you to begin or prepare work from any of these sources:

- handoff, execution plan, implementation plan, audit, review document, or issue tracker;
- instructions that mention subagents, external environments, staging, production, real integrations, migrations, cleanup, git publishing, or owner decisions;
- a task where the user explicitly asks for "preflight", "readiness permissions", or "authorization".

Skip preflight for small read-only answers, simple local commands, or clearly bounded edits that do not cite an execution artifact and do not need external access, delegation, git publishing, data mutation, or owner choice.

Completion criterion: either preflight is skipped for an explicit reason, or the authorization sources to read are identified before any execution action begins.

### 2. Read Only Authorization Sources

If this is not a new session, first review the active conversation for task-scoped permissions already granted or denied. Capture only current-session authorization facts, not stale permissions from unrelated tasks. This gives the owner a concise inheritance summary for handoff.

Then read the user-referenced handoff, plan, issue, review, or audit material only far enough to extract authorization and HITL facts. If a plan points to another source as required source of truth for permissions or scope, read that source too.

Do not infer extra external systems from general codebase knowledge. If a plan does not mention Azure, Lark, staging, production, browser smoke, database access, email, git publishing, or another external system, omit that system from the preflight output. If the plan mentions a system only to forbid it or require separate approval, report that exactly as a plan-stated boundary.

Extract only these categories when they appear in the sources:

- **Subagents:** whether the plan allows, forbids, or leaves ambiguous any delegation.
- **External systems:** read-only checks, smoke checks, staging, production, real integrations, email, databases, Azure, Lark, or similar systems.
- **Mutations and data risk:** migrations, cleanup, destructive actions, test-order deletion, external writes, or production-like changes.
- **Verification:** local tests, builds, dry-runs, browser smoke, external smoke, and whether failures block completion.
- **Git flow:** worktree/branch creation, staging, commits, pushes, PRs, issue updates, or thread handoff.
- **HITL decisions:** explicit owner decisions, open product/schema/UX choices, or acceptance exceptions.

Completion criterion: every current-session and source-stated authorization/HITL statement is captured once, and no unmentioned system or implementation recommendation has been added.

### 3. Ask Only For Missing Authorization

Ask before execution, not halfway through. Keep the ask limited to permission gaps discovered from the sources.

Always include the subagent mode when subagents are not explicitly forbidden by the active conversation or host:

- **普通使用:** the main session may use subagents for bounded support tasks, while the main session owns implementation and integration.
- **主session负责调度、记录、决策、seaming，派发 subagent 做执行:** the main session owns coordination, authorization records, decisions, integration seams, and final accountability while subagents execute assigned slices.
- **不允许:** no subagents.

Prefer this shape:

```markdown
Preflight permissions from the referenced plan:
- Current-session authorization: <already granted or denied in this session, or "none found/new session">
- Already allowed by plan: <only plan-stated permissions>
- Plan-stated boundaries: <forbidden or separately-authorized actions>
- HITL / owner decisions: <open decisions, or none found>
- Verification / git scope: <only plan-stated local tests, dry-runs, worktree, commits, pushes, etc.>

Please confirm:
- Subagents: 普通使用 / 主session负责调度、记录、决策、seaming，派发 subagent 做执行 / 不允许
- Missing authorization: <specific yes/no items, or "none">
```

Do not ask the owner to re-confirm boundaries that the plan already forbids unless the current active request explicitly asks to cross that boundary. Do not ask broad "can I do everything" questions.

If the user already granted a category in the current active task, restate it and ask only for still-missing authorization.

Completion criterion: the user can answer with a subagent mode plus concise yes/no permission decisions, and no implementation advice is mixed into the ask.

### 4. Record The Execution Authorization

After the user answers, restate the usable scope before continuing:

```markdown
Execution authorization for this task:
- Subagents: <普通使用 / 主session负责调度、记录、决策、seaming，派发 subagent 做执行 / 不允许>
- Allowed by plan/user: <scoped permissions>
- Blocked unless separately authorized: <plan-stated or user-stated boundaries>
- HITL decisions: <resolved/pending>
```

Treat authorization as task-scoped unless the user explicitly grants a standing rule. Do not silently reuse permission from an unrelated prior task.

Completion criterion: the active task has a clear permission boundary that later agents or resumptions can follow.

### 5. During Execution

If a new permission blocker appears outside the recorded scope, stop and ask before crossing it. If the blocker is inside the recorded scope, proceed without re-asking.

In the final response, mention only authorization gaps that affected completion. Do not list every preflight decision unless it matters to the outcome.

If reporting readiness or status to an owner, follow the root [Owner-Facing Reporting Contract](../references/owner-facing-reporting.md); keep preflight fields as evidence rather than the opening summary.

Completion criterion: execution either completes within the recorded scope, or any unresolved HITL blocker is surfaced promptly with the exact missing decision.

## Failure Modes

- Doing readiness analysis, implementation planning, issue ordering, or code reconnaissance during preflight.
- Mentioning external systems or risks that are not in the referenced sources.
- Asking the owner to re-confirm a plan-stated prohibition instead of recording it as blocked.
- Starting subagents before the owner chooses a subagent mode.
- Treating read-only access to staging or another project-specific external system as permission for mutations.
- Treating a previous task's permission as reusable for the current task without an explicit standing rule.
