# Review Topology And Closure Routing

Read this reference after atomic ReviewRun creation. It decides the applicable reviewer topology and Loop lifecycle; it does not replace `reviewer-registry.json` as the source of canonical reviewer paths.

## Safety admission

Evaluate the complete diff and the verified contract facts semantically. Safety is applicable when either source changes or relies on any of these boundaries:

- authentication, sessions, credentials, or identity;
- authorization, permissions, roles, ownership, or tenant isolation;
- data integrity, durable writes, reconciliation, money, inventory, orders, or customer state;
- concurrency, transactions, idempotency, locking, retries, or race handling;
- schema/data migration, backfill, rollback, or compatibility during transition;
- external side effects such as payments, messages, webhooks, jobs, remote storage, or third-party mutations.

Keywords are discovery cues, not sufficient evidence by themselves. Record the matched boundary and the diff or contract fact that makes it applicable.

For `initial`, with no explicit reviewer list, start from the registry's lean `default_tracks` (Track A/C) and append `safety-review` when Safety is applicable. Standards and maintainability review belongs to Track A (`review-code`); it is not a separate track. For `terminal-final`, with no explicit reviewer list, always start from the registry's full `terminal_tracks` (Track A/C) — independent of which tracks `initial` or any earlier phase in this ReviewRun actually selected — and append `safety-review` when Safety is applicable. For `finding-closure`, select exactly one independent `reviewer` leaf for all named findings; do not split by source track or launch a separate Safety leaf. The single reviewer must include any Safety implication that is part of the named findings. An explicit reviewer selection for closure must still resolve to one leaf; explicit selections for full reviews run exactly as stated. If Safety is applicable but an explicit full-review list omits `safety-review`, record `omitted applicable Safety risk`; for closure, record Safety applicability and the single reviewer's scoped coverage instead. Do not represent the single closure reviewer as a full Safety review.

Completion criterion: the ledger states whether Safety is applicable, the evidence for that decision, and whether it is selected, scoped within closure, or explicitly omitted.

## Review phase

Record one phase separately from the review mode:

- `initial`: run the complete applicable topology selected above.
- `finding-closure`: dispatch one independent `reviewer` leaf for all named findings. Use the closure brief and verify only named findings; do not split the closure into code, spec, or Safety tracks.
- `terminal-final`: pin the final implementation `HEAD`, resolve topology from `terminal_tracks` (not from whatever `initial` or any earlier phase in this ReviewRun selected), and run Track A unconditionally on the entire diff. For Tracks C and Safety, if an earlier `HEAD` in this ReviewRun already has a PASS for that track and the delta from that PASS `HEAD` to the final `HEAD` does not satisfy its admission condition, reuse that PASS and skip the track; otherwise apply that admission rule normally. Track C's admission range is bounded by the Ticket's section-level contract references (the contract sections and implementation surfaces). Whenever skipping, record which PASS `HEAD` is reused and the delta used for the admission decision. Admission is the only skip basis, even if intermediate finding closure was clean or a review group was complete.

A finding-closure result closes only its named findings. It cannot stand in for the terminal-final review. If a closure fix changes the diff or contract facts, refresh the single closure review brief before dispatch. The terminal verdict uses the terminal-final result from the same final implementation `HEAD`.

Completion criterion: every dispatch records its phase and resolved reviewer leaf; terminal completion has one complete applicable-topology result on the final implementation `HEAD`.

## Review group continuation

Applies to every review (`initial` rounds, `finding-closure`, `terminal-final`, `N rounds` and `Loop`). A review group owns the findings it raises: it keeps reviewing until the same group has verified each fix, and a fresh group then confirms. `review_rounds.py status --group <id>` prints the group `state` and the `nextAction` derived from the tables below, so every step is a command, not a judgment from memory.

Principles (everything else is the tables):

- Only user-visible behavior and data safety block. Reviewers are strict by nature: the parent reads each finding as a principal engineer would, and for a feature that is simple from the outside it cuts coarsely near the root instead of adding fine branches, copy or acceptance.
- The same kind of finding a second time: first ask whether the requirement can be cut near its root. The script demands a `--root-cut` sentence on the second reopen of one finding; the same kind of leak across two groups needs the same judgment, which the script cannot see.
- The plan comes before code. A plan gap is never dispatched together with code fixes: revise the plan, pass a plan round, then fix code.
- When direction changes mid-flight, interrupt the running session and confirm it received the change before going on.

### Group states

| State | Holds when | Event → action / command |
| --- | --- | --- |
| `plan-open` | a plan round is open, or no plan round has passed yet, or a plan-gap is not yet verified | `open --phase plan --track …`, `record` each track, `close`. PASS → `plan-pass`, and the close verifies every `fixed` plan-gap recorded before that round opened. Not PASS → `triage add`, revise the plan, `triage fixed --commit <plan commit>` before the next plan round opens. Each `open` from the third plan round since the last PASS warns (no block): check for local detail and for a root cut |
| `plan-pass` | a plan round passed, no code round yet, no open plan-gap | `open --phase initial …` → `code-open`. A group without a plan starts here |
| `code-open` | a code round is open | `record` each track, `close` → `code-closed` |
| `code-closed` | the latest round is closed; the group is not complete, converged or capped | `triage add` each accepted finding (`--source plan-gap` → `plan-open`; `impl-drift` → the implementer fixes, `triage fixed --commit`). Next round `只核实关闭`: `triage verify` or `triage reopen`. **Group complete** = every finding verified or downgraded and the latest round raised no new design-type finding → `open --group <new> --succeeds <this>` for a fresh group |
| `converged` | the group is complete, follows a complete group, and raised no design-type finding itself | stop |
| `cap-reached` | at most 5 code rounds per group and the group is still incomplete | `open` refuses; `open --group <new> --succeeds <this>` moves the unresolved findings to the new group |

A complete group is not proof. The fresh group (new leaves, no prior sessions, full scope) either raises nothing important and converges, or raises design-type findings, owns them, completes, and is followed by another fresh group. There is no total round cap across groups; three fresh groups in a row without convergence make `open` warn: cut the requirement near its root, or ask the Owner.

### Finding states

| State | Set by | Next |
| --- | --- | --- |
| `open` | `triage add --source plan-gap\|impl-drift --class design\|control --severity P0\|P1\|P2 --summary …` (`--round` defaults to the group's latest closed round) | the original implementer fixes, resumed: `triage fixed --commit`. The parent fixes control-type findings itself with `--self-verified` (→ `verified`) |
| `fixed` | `triage fixed` | the same group's next round: `triage verify` (round defaults to the group's latest closed round) or `triage reopen` |
| `verified` | `triage verify`, `--self-verified`, or a passing plan round for a plan-gap | closed |
| `reopened` | `triage reopen`; the second reopen of one finding needs `--root-cut "<one sentence>"` | fix again: `triage fixed` |
| `downgraded` | `triage downgrade --reason "<why>"`, parent only | backlog; no longer blocks. P2 is not downgraded by default: fix it in passing when it costs almost nothing, downgrade only the P2 that cannot be fixed in passing |

### Dispatch rules

- **Plan round**: only the relevant tracks. A rule-wording plan goes to Track C alone; add Safety when it touches permissions, concurrency or data ownership.
- **Verification round**: tracks follow the fix scope. A narrow fix opens only the track that raised the finding; the other tracks keep their previous PASS (note it in the ledger).
- **Round brief**: the first line says `重新分析` (review the fixed input again) or `只核实关闭` (only check that the findings marked `fixed` are closed), and lists fixed items and registered backlog so they are not reported again. A `只核实关闭` PASS is not convergence.
- **Fix**: the original implementer fixes, resumed. The brief names the rule behavior as the basis; test names carry the rule-case ID; the receipt ends with a rule → test table. Design-type fixes change the plan document first.
- **Class**: design-type (behavior, data, permissions, pay calculation, contract) or control-type (commands, gate order, evidence registration, wording); the parent judges severity and class and does not copy the reviewer's rating.
- **Fresh group on a large diff**: reports P0/P1 and the P2 that cost almost nothing to fix; the remaining P2 go to the backlog and the journey walkthrough covers them.

Completion criterion: the ledger explains every group completion, fresh-group handover and downgrade, and the evidence/classification that caused it. Incomplete, timeout, `PARTIAL`, `UNCERTAIN`, or an evidence gap never counts toward completion. `N rounds` and `Closure verification` run their fixed rounds and do not track convergence.
