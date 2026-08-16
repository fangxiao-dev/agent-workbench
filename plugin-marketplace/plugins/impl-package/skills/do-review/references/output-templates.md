# Do Review Output Templates

Use the smallest template that matches the run. Keep source attribution and per-selected-reviewer verdicts visible; the parent report is not an owner-approval gate.

## Leaf Return Contract

The four `review-track-*` agents return a compact index. Full evidence, impact, handoff, and quotations stay in the parent-supplied review report artifact; do not ask a leaf to repeat them in its response.

```text
verdict: PASS | FAIL | UNCERTAIN
coverage: <one compact line or report pointer>
findings:
- <slug> | <repo-relative-file>:<line> | <severity> | <one sentence>
report: <review report artifact path>
```

Use `findings: none` when no candidate exists. Each finding line must contain the slug, file and line, severity, and one sentence; leaf output is candidate evidence, not a ledger decision.

## Canonical ledger and classification

The parent owns one Markdown ledger for the whole ReviewRun. Leaf results are candidates, not accepted findings. After every round, wait for every required track, then deduplicate, verify, classify, and atomically rewrite that same ledger with verdicts, evidence, lifecycle transitions, and convergence. Never create a later-round ledger; a leaf result is not authoritative before this update.

Use source labels `Track A (review-code)`, `Track B (review-code-by-standards)`, `Track C (review-code-by-spec)`, additional selected labels, `fused`, and `main-session` as applicable. Deduplicate by broken invariant or observable failure, not path or reviewer; retain every contributor for a shared issue.

Before reporting a P1, P2, or blocker, verify cited target-revision evidence against the fixed ReviewRun and record whether the failure is in the diff, triggered by changed behavior, or pre-existing/baseline. Insufficient evidence becomes disputed, downgraded, out of scope, or `UNCERTAIN`, never a verified blocker.

Default classification: blocker risks business data, money, inventory, order/customer state, security, or runtime-visible product data; follow-up is real but non-blocking; backlog is non-urgent cleanup or optional hardening; no issue is duplicate, fixed, out of scope, or unsupported. Preserve disputed and out-of-scope candidates for closure without treating them as merge gates.

The ledger context must preserve the broken invariant/failure mode, best evidence, parent decision/status, and covered/open boundary. Large detail may live in a readable artifact without changing the canonical ledger owner.

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

| Classification | ID | Title | Source | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| blocker / follow-up / backlog |  |  |  |  |  |

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

For a custom full-review selection, replace the rows with exactly the selected Track label/skill pairs; retain one verdict row per selected reviewer and the same fail-closed aggregation rule. For `finding-closure`, use one `Independent closure reviewer` row covering all named findings; report any relevant Safety implication as scoped closure coverage, not as a separate track. When conditional Safety is selected for a full review, append its assigned track row. When applicable Safety is omitted from an explicit full-review list, keep the list exact and record the omitted boundary in the summary; a `terminal-final` report marks coverage `INCOMPLETE`.

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
| Review phase | finding-closure |
| Safety applicability / coverage | not applicable / selected / omitted applicable risk |

| Reviewer | Verdict | Coverage / note |
| --- | --- | --- |
| Independent closure reviewer | PASS / FAIL / UNCERTAIN |  |

| Issue | Verdict | Disposition | Reason / evidence | Suggested action |
| --- | --- | --- | --- | --- |
|  | PASS / FAIL / UNCERTAIN | reopen / stay closed / open / out of scope |  |  |
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
Design-source recheck: not applicable / current sources sufficient / req-align required / owner decision required
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
