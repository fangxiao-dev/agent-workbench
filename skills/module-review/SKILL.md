---
name: module-review
description: Review a module, PR diff, task branch, implementation package, or code change for bugs, regressions, missing tests, interface drift, and integration risks. Produces prioritized findings with file/line evidence.
---

# Module Review

Use this skill for focused module-level review. The review standard is concrete
evidence, cross-file completeness, risk ranking, and test scrutiny. It does not
assume a specific host runtime, generated skill file, telemetry layer,
AskUserQuestion flow, or GitHub workflow.

Do not edit files during this skill unless the user explicitly asks for fixes.
Default to read-only review and report findings first.

## Review Contract

**Job:** find issues that could break behavior, data, security, integration
contracts, or maintainability in the reviewed module/change.

**Inputs:** the user's target, local repo files, diff/branch state when relevant,
tests, docs, issue/PR text if available, and project instructions.

**Output:** a concise review report with verified findings ordered by severity.
Every actionable finding needs a file/line or stable source reference, impact,
and recommended action.

**Boundary:** this is not a rewrite pass, style pass, or general brainstorming
session. Mention nice-to-have cleanups only when they materially affect risk.

Completion criterion: the final report makes clear whether the change is
blocked, can proceed with follow-ups, or has no actionable findings.

## Workflow

### 1. Establish Scope

Identify what is being reviewed:

- explicit files, module, package, issue, PR, branch, or diff
- intended behavior and user-facing promise
- base branch or comparison point when a diff is involved
- project-specific instructions such as `AGENTS.md`, `CLAUDE.md`, or local review
  rules

Use the tools and commands available in the current host. Do not assume `gh`,
gstack, Claude tools, subagents, or a Unix shell. Follow repository search and
test instructions when present.

If the target is unclear, infer a narrow scope from the user's current request
and state that assumption. Ask only when a wrong scope would make the review
misleading.

Completion criterion: you can name the reviewed surface and the intended
behavior in one sentence.

### 2. Build The Change Map

Read enough surrounding code to understand the ownership boundary:

- entry points, callers, and downstream consumers
- shared types, schemas, status enums, constants, feature flags, and config
- persistence, cache, cookie, queue, background job, or external API boundaries
- UI state, optimistic updates, routing, and server/client ownership when
  frontend code is involved
- tests or docs that define the intended contract

For diffs, review both changed lines and nearby unchanged code that determines
behavior. For docs/plans, compare the proposed contract with the code it claims
to change.

Completion criterion: each modified or reviewed behavior has at least one caller
or consumer checked, or the report explicitly says that coverage was unavailable.

### 3. Critical Pass

Prioritize issues in these categories:

- **Data safety:** data loss, duplicate writes, partial updates, migration risk,
  stale snapshots, invalid persistence, and rollback gaps.
- **Authorization and trust boundaries:** missing auth, privilege drift,
  accepting client/server/LLM output as trusted without validation.
- **Concurrency and ordering:** races, idempotency gaps, retry hazards, cache
  invalidation, optimistic state reconciliation, and stale reads.
- **Contract completeness:** new enum/status/type/value not handled everywhere
  sibling values are handled; API or schema shape drift across layers.
- **External integrations:** changed assumptions for third-party APIs, webhooks,
  email, payments, warehouse/accounting systems, or rate limits.
- **Frontend behavior:** layout regressions, inaccessible controls, broken
  responsive states, hydration mismatches, loading/error states, and optimistic
  UI that cannot reconcile with server truth.
- **Testing and verification:** missing tests for changed behavior, tests that do
  not assert the real contract, or impossible-to-run verification.

Search beyond the diff when the change introduces or changes a shared value,
contract, field name, cache key, route, permission, or persistence shape.

Completion criterion: every high-risk category that applies to the reviewed
surface has been checked against code, tests, or an explicit source.

### 4. Verify Before Reporting

Before emitting a finding:

- read the exact referenced file/line or source text
- confirm the cited symbol, field, route, or behavior exists
- check whether existing code already handles the case
- distinguish confirmed issues from assumptions
- suppress speculative low-confidence concerns from the main findings

Use confidence only to control reporting, not to excuse weak evidence:

- `9-10`: verified concrete bug or contract break
- `7-8`: strong evidence from code path or missing handler/test
- `5-6`: plausible but needs confirmation; report only if impact is meaningful
- `1-4`: keep out of main findings unless it would be catastrophic

Completion criterion: every main finding has evidence strong enough that the
author can act without first redoing the whole investigation.

### 5. Test Review

Check whether verification matches the risk:

- unit tests for pure logic and edge cases
- integration tests for contracts across modules or server actions
- E2E/manual checks for user workflows, routing, layout, and optimistic UI
- migration/backfill tests or dry-runs for data shape changes
- regression tests for previously broken behavior

Do not demand broad tests for a tiny low-risk change. Do demand targeted tests
when a change crosses persistence, auth, pricing, checkout, external API, or
shared UI/component boundaries.

Completion criterion: the report says which tests were inspected or which test
gap remains.

### 6. Output Report

Lead with findings. Use this shape:

```text
Findings
- [P1 bug] file:line — title
  Impact: ...
  Evidence: ...
  Recommendation: ...

Open Questions
- ...

Coverage
- Reviewed: ...
- Not reviewed: ...

Verdict
- Blocked / Follow-up needed / No actionable findings
```

Severity:

- `P0`: immediate data loss, exploit, production outage, or irreversible action
- `P1`: likely user-visible breakage, security issue, data corruption, or broken
  core workflow
- `P2`: real defect, incomplete contract, missing meaningful test, or risky
  maintainability issue that should be fixed soon
- `P3`: minor cleanup or backlog item

If there are no findings, say that clearly and still mention residual test or
coverage limits. Keep summaries short; the findings are the review.

Completion criterion: the user can decide whether to merge, fix, or defer based
on the report alone.
