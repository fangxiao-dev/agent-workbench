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
- `terminal-final`: pin the final implementation `HEAD`, resolve topology from `terminal_tracks` (not from whatever `initial` or any earlier phase in this ReviewRun selected), and run Track A unconditionally on the entire diff. For Tracks C and Safety, if an earlier `HEAD` in this ReviewRun already has a PASS for that track and the delta from that PASS `HEAD` to the final `HEAD` does not satisfy its admission condition, reuse that PASS and skip the track; otherwise apply that admission rule normally. Track C's admission range is bounded by the Ticket's section-level contract references (the contract sections and implementation surfaces). Whenever skipping, record which PASS `HEAD` is reused and the delta used for the admission decision. Admission is the only skip basis, even if intermediate finding closure was clean or a Loop track was dormant.

A finding-closure result closes only its named findings. It cannot stand in for the terminal-final review. If a closure fix changes the diff or contract facts, refresh the single closure review brief before dispatch. The terminal verdict uses the terminal-final result from the same final implementation `HEAD`.

Completion criterion: every dispatch records its phase and resolved reviewer leaf; terminal completion has one complete applicable-topology result on the final implementation `HEAD`.

## Loop track lifecycle

This section applies only to `Loop`. The parent records each selected track as `active`, `probation`, or `dormant`, with a consecutive-clean count:

- Every selected track starts `active` at zero and participates in Round 1.
- Only the parent may call a track clean, after deduplication, evidence verification, and classification. Clean means no **new, must-fix** finding from that track: both conditions must hold for a round to stay dirty.
  - **Must-fix** means an accepted blocker. An accepted follow-up is recorded in the ledger and tracked to closure, but it does not reset the count.
  - **New** means the finding does not derive from an earlier accepted finding. A candidate that continues an earlier finding, or that the fix for an earlier finding introduced, is a *derived* finding. The parent links it to that earlier finding in the ledger and closes it through `finding-closure` for that finding. It does not reset the count and does not open a new formal round for the track.
  - The parent makes the new-or-derived call and records the link. A reviewer's own framing does not decide it.
  - Duplicate, refinement, disputed, out-of-scope, and backlog-only candidates do not reset the count either.
- The first clean round moves a track to `probation`, and it must run again. The second consecutive clean round moves it to `dormant`, so later Loop rounds need not dispatch it.
- A new accepted blocker resets its source track to `active` at zero. A finding from another track reactivates a dormant track when it materially affects that track's responsibility, evidence boundary, or likely fix surface.
- Incomplete, timeout, `PARTIAL`, `UNCERTAIN`, or an evidence gap never counts as clean. Dormant means two independently clean rounds, not permanent removal or proof by itself.

Convergence requires both no new must-fix finding (as defined above) in the latest completed round and every selected track dormant. Derived findings must be closed through `finding-closure` before convergence is reported, but they never reopen a formal round on their own. A reactivated track must again complete two consecutive clean rounds. `N rounds` and `Closure verification` keep all resolved tracks active and do not use dormancy.

Completion criterion: the ledger explains every lifecycle transition and the evidence/classification that caused it.
