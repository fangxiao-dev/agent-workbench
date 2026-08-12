# Do Review Output Templates

Use the smallest template that matches the run. Keep source attribution and per-track verdicts visible; default review output reports conclusions, findings and next actions without turning those details into an owner approval gate.

## Canonical ledger and classification

The parent owns one Markdown ledger for the whole ReviewRun. Leaf results are candidates, not accepted findings. After every round, wait for every required track, then deduplicate, verify, classify, and atomically rewrite that same temp ledger with track verdicts, finding status, evidence, lifecycle transitions, and the convergence decision. Never create a later-round ledger. A leaf result is not authoritative before this update.

Use the default source labels `Track A (review-code)`, `Track B (review-code-by-standards)`, and `Track C (review-code-by-spec)`. Additional selected reviewers use their assigned sequential labels. `main-session` is a decision source, never another reviewer. Deduplicate by broken invariant or observable failure, not by path or reviewer; for a shared issue use `fused` and retain every contributor.

Before reporting a P1, P2, or blocker, read its cited target-revision evidence, confirm the citation supports the claim and belongs to the fixed ReviewRun, and record the verification. Decide whether the diff directly contains the failure, changed behavior triggers it, or it is pre-existing/baseline. Insufficient evidence becomes disputed, downgraded, out of scope, or `UNCERTAIN`, never a verified blocker.

Default classification: blocker risks business data, money, inventory, order/customer state, security, or runtime-visible product data; follow-up is real but non-blocking under stated release constraints; backlog is non-urgent cleanup or optional hardening; no issue is duplicate, fixed, out of scope, or unsupported. Preserve disputed and out-of-scope candidates separately so closure work can revisit them without treating them as merge gates.

The ledger's canonical context may be concise free-form Markdown, but it must preserve the broken invariant/failure mode, best evidence, parent decision/status, and covered/open boundary. Topic labels alone are insufficient. Large context may live in a readable artifact without changing the canonical ledger owner.

## Normal Review Report

```markdown
## Review Summary

| Field | Value |
| --- | --- |
| Target |  |
| Base / Head |  |
| Mode |  |
| Review phase | initial / finding-closure / terminal-final |
| Safety applicability / coverage | not applicable / selected / omitted applicable risk |
| Rounds |  |
| Audit record | retained internally |
| Stop reason |  |
| Overall verdict | PASS / FAIL / UNCERTAIN |

## Track Verdicts

| Track | Verdict | Coverage / note |
| --- | --- | --- |
| Track A (review-code) | PASS / FAIL / UNCERTAIN |  |
| Track B (review-code-by-standards) | PASS / FAIL / UNCERTAIN |  |
| Track C (review-code-by-spec) | PASS / FAIL / UNCERTAIN |  |

## Findings

### Blockers

| ID | Title | Source | Evidence | Decision |
| --- | --- | --- | --- | --- |

### Follow-ups

| ID | Title | Source | Evidence | Decision |
| --- | --- | --- | --- | --- |

### Backlog / Not Blocking

| ID | Title | Source | Evidence | Decision |
| --- | --- | --- | --- | --- |

## Source Coverage

| Source | Count | Notes |
| --- | --- | --- |
| Track A (review-code) |  |  |
| Track B (review-code-by-standards) |  |  |
| Track C (review-code-by-spec) |  |  |
| fused |  |  |
| main-session |  |  |

## Recommended Next Actions
1.
2.
3.
```

For a custom selection, replace the rows with exactly the selected Track label/skill pairs; retain one verdict row per selected reviewer and the same fail-closed aggregation rule. When conditional Safety is selected, append its assigned track row. When applicable Safety is omitted by an explicit list, keep the list exact and record the omitted boundary in the summary; a `terminal-final` report marks coverage `INCOMPLETE`.

当 `Mode` 为 `Loop` 时，在 `Track Verdicts` 后补充 track lifecycle，明确哪些 track 仍在 `active` / `probation`、哪些已因连续两轮 clean 而 `dormant`，以及是否曾因新 finding 重新激活：

```markdown
## Track Lifecycle

| Track | Final state | Consecutive clean rounds | Last review round | Reactivated because |
| --- | --- | --- | --- | --- |
```

## Closure Verification Report

```markdown
## Closure Verification Summary

| Field | Value |
| --- | --- |
| Review phase | finding-closure / terminal-final |
| Safety applicability / coverage | not applicable / selected / omitted applicable risk |

| Track | Verdict | Coverage / note |
| --- | --- | --- |
| Track A (<skill>) | PASS / FAIL / UNCERTAIN |  |
| Track B (<skill>) | PASS / FAIL / UNCERTAIN |  |
| Track C (<skill>) | PASS / FAIL / UNCERTAIN |  |

| Issue | Verdict | Reason | Evidence |
| --- | --- | --- | --- |

## Should Reopen / Retrack

| Issue | Failed acceptance | Evidence | Suggested action |
| --- | --- | --- | --- |

## Safe To Stay Closed

| Issue | Why it passes | Evidence |
| --- | --- | --- |

## Still Open / Out Of Scope

| Issue | Reason |
| --- | --- |
```

## Finding Record

```markdown
### F-XXX: Short Title

Severity: P0 / P1 / P2 / P3
Classification: blocker / follow-up / backlog / no issue
Source: Track <label> (<skill>) / fused / main-session
Contributing sources:
Status: candidate / new / duplicate / refined / disputed / accepted / downgraded / out of scope / fixed-verified
Evidence:
- `path/to/file.ts:123` - concise evidence summary.
Impact:
Suggested handoff:
Recommended action:
Main-session decision:
```

## Round Ledger

```markdown
## Review Rounds

| Round | Track A (<skill>) | Track B (<skill>) | Track C (<skill>) | New accepted | Convergence note |
| --- | --- | --- | --- | --- | --- |

## Track Lifecycle

| Track | State | Consecutive clean rounds | Last completed round | Reactivation reason |
| --- | --- | --- | --- | --- |

## Known Findings Ledger

| ID | Title | Classification | Source | Status | Duplicate key |
| --- | --- | --- | --- | --- | --- |
```
