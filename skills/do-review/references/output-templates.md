# Do Review Output Templates

Use the smallest template that matches the run. Keep source attribution and per-track verdicts visible; default review output reports conclusions, findings and next actions without turning those details into an owner approval gate.

## Normal Review Report

```markdown
## Review Summary

| Field | Value |
| --- | --- |
| Target |  |
| Base / Head |  |
| Mode |  |
| Rounds |  |
| Audit record | retained internally |
| Stop reason |  |
| Overall verdict | PASS / FAIL / UNCERTAIN |

## Track Verdicts

| Track | Verdict | Coverage / note |
| --- | --- | --- |
| Track A (code-review) | PASS / FAIL / UNCERTAIN |  |
| Track B (standards-review) | PASS / FAIL / UNCERTAIN |  |
| Track C (spec-review) | PASS / FAIL / UNCERTAIN |  |

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
| Track A (code-review) |  |  |
| Track B (standards-review) |  |  |
| Track C (spec-review) |  |  |
| fused |  |  |
| main-session |  |  |

## Recommended Next Actions
1.
2.
3.
```

For a custom selection, replace the rows with exactly the selected Track label/skill pairs; retain one verdict row per selected reviewer and the same fail-closed aggregation rule.

当 `Mode` 为 `Loop` 时，在 `Track Verdicts` 后补充 track lifecycle，明确哪些 track 仍在 `active` / `probation`、哪些已因连续两轮 clean 而 `dormant`，以及是否曾因新 finding 重新激活：

```markdown
## Track Lifecycle

| Track | Final state | Consecutive clean rounds | Last review round | Reactivated because |
| --- | --- | --- | --- | --- |
```

## Closure Verification Report

```markdown
## Closure Verification Summary

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
