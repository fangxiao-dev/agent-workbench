---
name: do-review
description: Orchestrate dual-track code review with code-review and review subagents. Use for PR/code review, N-round review, loop/until-converged review, or verifying whether previous review issues were actually fixed. Requires subagents by default; stop and ask if they are unavailable.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Do Review

Run a **dual-track review**: one subagent uses `code-review`, one subagent uses `review`, and the main session acts as scheduler, ledger owner, deduper, verifier, and final decision maker.

The main session is not a third reviewer. It verifies high-severity evidence and decides classification.

## Step 0: Subagent Gate

This skill requires subagents.

If subagents are unavailable, disallowed, or need authorization, stop before reviewing and ask:

```text
This do-review skill requires subagents for the code-review and review tracks. Subagents are currently unavailable or need authorization. Do you want me to stop, or explicitly authorize a degraded single-session review?
```

Completion criterion: either subagents are available, or the user explicitly authorizes degraded mode. If neither is true, stop.

## Step 1: Scope

Determine the review target and mode before spawning subagents.

Scope fields:

```text
Target:
Base/head or issue set:
Mode:
Rounds/cap:
Known constraints:
Out of scope:
```

Ask only if the target or mode cannot be inferred from the prompt, repo, or issue/PR metadata.

Completion criterion: the target revision/issue set and mode are explicit enough that subagents can work independently without asking follow-up questions.

## Step 2: Select Mode

Choose exactly one mode.

| Mode | Trigger | Stop rule |
| --- | --- | --- |
| Default | review / 审查 / code review / 重新审核 | 1 round |
| Fixed rounds | `N轮审查`, `run N rounds` | exactly N rounds |
| Loop | `loop模式`, `直到收敛`, `until converged` | convergence or cap, default cap 5 |
| Closure verification | `聚焦验证模式`, `是否真的关闭`, `只验证是否修完`, `verify closure` | all named issues/findings verdicted |

In closure verification mode, do not hunt for unrelated new problems.

Completion criterion: the selected mode and stop rule are written in the main session notes or response.

## Step 3: Dispatch Dual Tracks

Spawn two subagents in every round.

For durable prompts, read only the needed sections from `references/subagent-briefs.md`: [Common Context Block](references/subagent-briefs.md#common-context-block), [code-review Track Brief](references/subagent-briefs.md#code-review-track-brief), and [review Track Brief](references/subagent-briefs.md#review-track-brief). For closure verification, use [Closure Verification Brief](references/subagent-briefs.md#closure-verification-brief). From round 2 onward, append [Round-N Anti-Duplicate Addendum](references/subagent-briefs.md#round-n-anti-duplicate-addendum).

### Track A: `code-review`

Prompt intent:

```text
Use the code-review skill. Review the target from the concrete implementation lens:
- reachable code-path bugs;
- local business invariants;
- error handling and partial failures;
- tests and missing regressions;
- local/mock behavior that can hide real bugs.

Every finding needs file:line evidence. Avoid duplicates from the ledger unless you add materially new evidence.
Return findings in the ledger schema.
```

### Track B: `review`

Prompt intent:

```text
Use the review skill. Review the target from the PR/system lens:
- cross-module seams;
- transaction semantics and crash points;
- replay, idempotency, and concurrency;
- runtime modes and environment matrix;
- external systems and release risk.

Prefer distinct issue classes with observable failure modes. Avoid duplicates from the ledger unless you add materially new impact.
Return findings in the ledger schema.
```

For fixed-round and loop modes, include the current ledger in every round after round 1.

Completion criterion: each round has one `code-review` result and one `review` result, or the run is explicitly blocked by subagent availability/authorization.

## Step 4: Maintain The Ledger

Use one ledger across all rounds.

```text
ID:
Title:
Severity: P0/P1/P2/P3
Classification: blocker / follow-up / backlog / no issue
Source: code-review / review / fused / main-session
Status: new / duplicate / refined / disputed / accepted / downgraded / fixed-verified
Evidence:
  - file:line
Issue class:
Impact:
Recommended action:
Related issue/PR:
Main-session decision:
```

Deduplicate by broken invariant or observable failure, not by file path. If both subagents report the same issue, mark `Source: fused`.

Completion criterion: every accepted finding has source attribution and a main-session decision.

## Step 5: Verify High-Severity Findings

Before reporting any P1/P2/blocker:

1. Read the cited code at the target revision.
2. Confirm the line exists and supports the claim.
3. Confirm the finding is in scope.
4. Classify using the user's policy if provided.

If evidence is incomplete, mark `disputed`, `downgraded`, or `UNCERTAIN`; do not present it as a verified blocker.

Completion criterion: all P1/P2/blocker findings have main-session verification notes.

## Step 6: Classify

Default policy when the user gives no policy:

- `blocker`: can corrupt future business data, money, inventory, order/customer state, security, or runtime-visible product data.
- `follow-up`: real risk, but not blocking under stated release constraints.
- `backlog`: old data cleanup, automation convenience, optional hardening, or environment governance without immediate business risk.
- `no issue`: duplicate, fixed, out of scope, or unsupported.

Closure verification verdicts:

- `PASS`: acceptance criteria satisfied.
- `FAIL`: acceptance criteria not satisfied.
- `UNCERTAIN`: evidence insufficient; state the missing check.

Completion criterion: every ledger item has exactly one classification or closure verdict.

## Step 7: Decide Whether To Continue

For loop mode, continue until convergence or cap.

Converged means the latest round adds no distinct blocker/follow-up issue class, or only duplicates/refinements remain. The main session decides convergence and records why.

Completion criterion: the final output states the number of rounds and why the run stopped.

## Output

For report templates, read only the relevant section from `references/output-templates.md`: [Normal Review Report](references/output-templates.md#normal-review-report), [Closure Verification Report](references/output-templates.md#closure-verification-report), [Finding Record](references/output-templates.md#finding-record), or [Round Ledger](references/output-templates.md#round-ledger).

Normal review:

```markdown
## Summary
- Target:
- Mode:
- Rounds:
- Stop reason:

## Findings
### Blockers
### Follow-ups
### Backlog / Not blocking

## Type Summary
- Inventory / movement:
- Runtime / cutover:
- External systems:
- Readiness / schema:
- Test fidelity:

## Source Coverage
- code-review:
- review:
- fused:

## Recommended Next Actions
```

Closure verification:

```markdown
## Closure Verification Summary

| Issue | Verdict | Reason |
| --- | --- | --- |

## Should Reopen / Retrack

## Safe To Stay Closed

## Still Open / Out Of Closure Scope

## Evidence Notes
```

## Guardrails

- Do not mutate code, issues, or git state unless the user explicitly asks.
- Do not create new issues unless the user asked for tracking updates.
- Do not broaden closure verification into new-problem hunting.
- Do not hide subagent unavailability.
- Do not let subagents decide final classification.
