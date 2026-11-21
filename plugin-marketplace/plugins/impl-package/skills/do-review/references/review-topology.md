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
- `terminal-final`: pin the final implementation `HEAD`, resolve topology from `terminal_tracks` (not from whatever `initial` or any earlier phase in this ReviewRun selected), and run Track A unconditionally on the entire diff. For Tracks C and Safety, if an earlier `HEAD` in this ReviewRun already has a PASS for that track and the delta from that PASS `HEAD` to the final `HEAD` does not satisfy its admission condition, reuse that PASS and skip the track; otherwise apply that admission rule normally. Track C's admission range is bounded by the Ticket's section-level contract references (the contract sections and implementation surfaces). Whenever skipping, record which PASS `HEAD` is reused and the delta used for the admission decision. Admission is the only skip basis, even if intermediate finding closure was clean or a Loop track was converged.

A finding-closure result closes only its named findings. It cannot stand in for the terminal-final review. If a closure fix changes the diff or contract facts, refresh the single closure review brief before dispatch. The terminal verdict uses the terminal-final result from the same final implementation `HEAD`.

Completion criterion: every dispatch records its phase and resolved reviewer leaf; terminal completion has one complete applicable-topology result on the final implementation `HEAD`.

## Review group continuation

Applies to every review (`initial` rounds, `finding-closure`, `terminal-final`, `N rounds` and `Loop`); normal reviews and final reviews use the same rules.

- **Review group**: the leaves selected for one review. Keep each leaf's session for the group's whole lifecycle; from round 2 send incremental instructions instead of starting new leaves.
- **Round mode**: the first line of every round brief says `重新分析` (default: review the fixed input again) or `只核实关闭` (only check that the previous round's fixed findings are closed). The brief also lists fixed items and registered backlog so they are not reported again. A `只核实关闭` PASS is not convergence.
- **Fresh group**: one group runs at most 3 rounds. After 3 rounds, or as soon as only control-type findings are left, dispatch one fresh group (new leaves, no prior sessions) for one full-scope round. The new group's count restarts at 1; the Loop round cap counts rounds across all groups. The review is converged only when the fresh group also leaves only control-type findings.
- **Severity and class**: the parent judges severity and does not copy the reviewer's rating. Findings are design-type (behavior, data, permissions, pay calculation, contract) or control-type (commands, gate order, evidence registration, wording). Only control-type findings left, with no design-type finding, is what triggers the fresh group above.
- **Fix**: the original implementer fixes, resumed. Design-type fixes change the plan document first, which goes into the next review round; code follows after it passes, then stable docs. The parent fixes control-type findings directly and records them in the ledger without another round.
- The ledger records, per group, the group id, member leaves and rounds used. For an Impl-Package target, put the group id in the canonical summary as `reviewGroup`; `review_track_stats.py record` counts the group's rounds and warns when it reaches 3.

## Loop track lifecycle

This section applies only to `Loop`. The parent records each selected track as `active` or `converged`:

- Every selected track starts `active` and participates in Round 1. Rounds follow Review group continuation.
- A track becomes `converged` only through a fresh group: the track's current group reaches 3 rounds or has only control-type findings left, a fresh group reviews the whole scope for one round, and that round also leaves only control-type findings (no design-type accepted blocker/follow-up). The parent decides after deduplication, evidence verification, and classification. A clean round inside the same group never converges a track.
- If the fresh group's round finds a design-type finding, the track stays `active`: fix it, and the fresh group continues as the track's group with its count at 1.
- Control-type findings are fixed directly and recorded; they neither block convergence nor reactivate a track. Duplicate, refinement, disputed, out-of-scope, and backlog-only candidates are not findings for this purpose.
- A converged track is not dispatched again. A new design-type accepted finding from another track reactivates it when that finding materially affects the converged track's responsibility, evidence boundary, or likely fix surface; it then needs a fresh-group round again.
- Incomplete, timeout, `PARTIAL`, `UNCERTAIN`, or an evidence gap never counts toward convergence.

Convergence requires every selected track `converged`. `N rounds` and `Closure verification` keep all resolved tracks active and do not track convergence.

Completion criterion: the ledger explains every lifecycle transition and the evidence/classification that caused it.
