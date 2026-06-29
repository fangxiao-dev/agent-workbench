# Do Review Output Templates

Use the smallest template that matches the run. Keep source attribution visible.

## Normal Review Report

```markdown
## Review Summary

| Field | Value |
| --- | --- |
| Target |  |
| Base / Head |  |
| Mode |  |
| Rounds |  |
| Stop reason |  |
| Verdict |  |

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

## Type Summary

| Type | Findings |
| --- | --- |
| Inventory / movement |  |
| Product/runtime/cutover |  |
| External systems |  |
| Readiness / schema |  |
| Test fidelity |  |
| Security / auth |  |

## Source Coverage

| Source | Count | Notes |
| --- | --- | --- |
| Track A (<skill>) |  |  |
| Track B (<skill>) |  |  |
| fused |  |  |
| main-session |  |  |

## Recommended Next Actions
1.
2.
3.
```

## Closure Verification Report

```markdown
## Closure Verification Summary

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
Sources: Track A (<skill>) / Track B (<skill>) / fused / main-session
Status: new / duplicate / refined / disputed / accepted / downgraded / fixed-verified
Evidence:
- `path/to/file.ts:123` - concise evidence summary.
Impact:
Recommended action:
Main-session decision:
```

## Round Ledger

```markdown
## Review Rounds

| Round | Track A (<skill>) | Track B (<skill>) | New accepted | Convergence note |
| --- | --- | --- | --- | --- |

## Known Findings Ledger

| ID | Title | Classification | Source | Status | Duplicate key |
| --- | --- | --- | --- | --- | --- |
```
