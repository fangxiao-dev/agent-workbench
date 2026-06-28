# Review Orchestrator Output Templates

Use these templates when the user does not request a custom format.

## Normal Review Report

```markdown
## Review Summary

| Field | Value |
| --- | --- |
| Target |  |
| Base / Head |  |
| Mode |  |
| Rounds completed |  |
| Stop reason |  |
| Main-session verdict |  |

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
| code-review |  |  |
| review |  |  |
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

## Still Open / Out Of Closure Scope

| Issue | Reason |
| --- | --- |

## Verification Commands

| Command | Result |
| --- | --- |

## Notes

- 
```

## Finding Record

Use this structure internally and in durable review docs.

```markdown
### F-XXX: Short Title

Severity: P0 / P1 / P2 / P3

Classification: blocker / follow-up / backlog / no issue

Sources: code-review / review / fused / main-session

Status: new / duplicate / refined / disputed / accepted / downgraded / fixed-verified

Evidence:

- `path/to/file.ts:123` - concise evidence summary.

Impact:

- 

Recommended action:

- 

Main-session decision:

- 
```

## Round Ledger

Use this when running fixed-round or loop mode.

```markdown
## Review Rounds

| Round | code-review result | review result | New accepted findings | Convergence note |
| --- | --- | --- | --- | --- |
| 1 |  |  |  |  |

## Known Findings Ledger

| ID | Title | Classification | Source | Status | Duplicate key |
| --- | --- | --- | --- | --- | --- |
```

