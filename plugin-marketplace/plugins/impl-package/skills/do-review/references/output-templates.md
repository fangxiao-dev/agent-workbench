# Do Review Output Templates

Use the smallest template that matches the run. Keep source attribution and per-selected-reviewer verdicts visible; the parent report is not an owner-approval gate.

## Leaf Return Contract

The four `review-track-*` agents return a compact index. Each leaf writes full evidence, impact, recommendations, handoff, and quotations to its exclusively assigned report artifact; do not ask a leaf to repeat them in its response.

```text
verdict: PASS | FAIL | UNCERTAIN
coverage: <one compact line or report pointer>
findings:
- <slug> | <repo-relative-file>:<line> | <severity> | <one sentence>
report: <review report artifact path>
```

Use `findings: none` when no candidate exists. Each finding line must contain the slug, file and line, severity, and one sentence; leaf output is candidate evidence, not a ledger decision.

Impl-Package 的 leaf report 存在 parent 指定的 package 内独占路径，完整正文前写明以下四行，供终审核对来源：

```text
verdict: PASS | FAIL | UNCERTAIN
reviewed-head: <实际审阅 SHA>
review-run: <本次 ReviewRun ID>
review-track: <Track A/B/C/D>
```

## Terminal coverage record

terminal-final 的 canonical ledger 更新且所需结果已返回后，parent 将下列 `review.terminal_summary` fact 交给记账 subagent 用 `trail append` 落盘。它复用已有 trail，不创建第二份 ledger。artifact 和 reuseEvidence 为 package-relative 路径；report 前四行必须含上面的真实 verdict/head/run/track，各 track 使用独占 artifact。A/B/C required；Safety 适用时追加 Track D。A 在最终 HEAD 重审，B/C/Safety 可在同一 ReviewRun 内复用旧 PASS，parent 在 reuseEvidence 中记录旧/新 SHA、该轨输入的 delta 与不受影响的依据。

```json
{
  "kind": "fact",
  "subject": "attempt",
  "key": "review.terminal_summary",
  "value": {
    "reviewRunId": "<ReviewRun ID>",
    "comparisonHead": "<最终 implementation HEAD>",
    "safetyApplicable": false,
    "results": [
      {"track": "Track A", "verdict": "PASS", "reviewedHead": "<最终 HEAD>", "artifact": "execution/initial/review-a.md"},
      {"track": "Track B", "verdict": "PASS", "reviewedHead": "<旧 PASS HEAD>", "artifact": "execution/initial/review-b.md", "reused": true, "reuseEvidence": "execution/initial/review-reuse.md"},
      {"track": "Track C", "verdict": "PASS", "reviewedHead": "<最终 HEAD>", "artifact": "execution/initial/review-c.md"}
    ]
  }
}
```

新结果、comparison HEAD 或 Safety applicability 变化后记录完整新 summary；单独的 dispatch 或旧布尔 coverage 声明不证明终审结果。terminal metadata commit 后如行为与合同未变，parent 复核 metadata delta，沿用实际 implementation HEAD 的结论时仍须更新相应的完成声明依据。

## Canonical ledger and classification

The parent owns one Markdown ledger for the whole ReviewRun. Leaf results are candidates, not accepted findings. After every round, wait for every required track, then deduplicate, verify, classify, and atomically rewrite that same ledger with verdicts, evidence, lifecycle transitions, and convergence. Never create a later-round ledger; a leaf result is not authoritative before this update.

Use source labels `Track A (review-code)`, `Track B (review-code-by-standards)`, `Track C (review-code-by-spec)`, additional selected labels, `fused`, and `main-session` as applicable. Deduplicate by broken invariant or observable failure, not path or reviewer; retain every contributor for a shared issue.

Before reporting a P1, P2, or blocker, verify cited target-revision evidence against the fixed ReviewRun and record whether the failure is in the diff, triggered by changed behavior, or pre-existing/baseline. Insufficient evidence becomes disputed, downgraded, out of scope, or `UNCERTAIN`, never a verified blocker.

Default classification: blocker risks business data, money, inventory, order/customer state, security, or runtime-visible product data; follow-up is real but non-blocking; backlog is non-urgent cleanup or optional hardening; no issue is duplicate, fixed, out of scope, or unsupported. Preserve disputed and out-of-scope candidates for closure without treating them as merge gates.

The ledger context must preserve the broken invariant/failure mode, best evidence, parent decision/status, and covered/open boundary. Large detail may live in a readable artifact without changing the canonical ledger owner.

## Canonical Finding Summary

For an Impl-Package target, after atomically updating the Markdown ledger, send one complete machine-readable summary to `review_track_stats.py record`. Only accepted `blocker` and `follow-up` findings appear here; candidates, duplicates, disputed, backlog, out-of-scope, and unsupported entries remain in the human ledger and are not counted as bugs.

```json
{
  "schemaVersion": 1,
  "reviewRunId": "<stable ReviewRun id>",
  "phase": "initial | finding-closure | terminal-final",
  "resolvedHead": "<40-character commit SHA>",
  "findings": [
    {
      "findingKey": "<package-stable broken-invariant key>",
      "id": "F-001",
      "title": "Short title",
      "ticketIds": ["TKT-01"],
      "tracks": ["Track A", "Track C"],
      "classification": "blocker | follow-up",
      "lifecycle": "open | closed"
    }
  ]
}
```

Every summary is the complete latest accepted finding set for that ReviewRun, not a delta. Reuse `findingKey` when a later phase or ReviewRun rechecks the same broken invariant; the latest trail record owns lifecycle and track attribution. An empty `tracks` list is reserved for explicit legacy backfill and is rejected by normal `record`.

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
