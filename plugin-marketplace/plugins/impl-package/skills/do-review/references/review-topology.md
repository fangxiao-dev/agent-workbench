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

For `initial` and `terminal-final`, with no explicit reviewer list, start from the registry's three default tracks and append `safety-review` as the next track when Safety is applicable. For `finding-closure`, select exactly one fresh independent `reviewer` leaf for all named findings; do not split by source track or launch a separate Safety leaf. The single reviewer must include any Safety implication that is part of the named findings. An explicit reviewer selection for closure must still resolve to one leaf; explicit selections for full reviews run exactly as stated. If Safety is applicable but an explicit full-review list omits `safety-review`, record `omitted applicable Safety risk`; for closure, record Safety applicability and the single reviewer's scoped coverage instead. Do not represent the single closure reviewer as a full Safety review.

Completion criterion: the ledger states whether Safety is applicable, the evidence for that decision, and whether it is selected, scoped within closure, or explicitly omitted.

## Review phase

Record one phase separately from the review mode:

- `initial`: run the complete applicable topology selected above.
- `finding-closure`: dispatch one fresh independent `reviewer` leaf for all named findings. Use the closure brief and verify only named findings; do not split the closure into source, standards, spec, or Safety tracks.
- `terminal-final`: pin the final implementation `HEAD`, reactivate every applicable selected track, and run the complete applicable topology again, even if intermediate finding closure was clean or a Loop track was dormant.

A finding-closure result closes only its named findings. It cannot stand in for the terminal-final review. If a closure fix changes the diff or contract facts, refresh the single closure review brief before dispatch. The terminal verdict uses the terminal-final result from the same final implementation `HEAD`.

Completion criterion: every dispatch records its phase and resolved reviewer leaf; terminal completion has one complete applicable-topology result on the final implementation `HEAD`.

## Loop track lifecycle

This section applies only to `Loop`. The parent records each selected track as `active`, `probation`, or `dormant`, with a consecutive-clean count:

- Every selected track starts `active` at zero and participates in Round 1.
- Only the parent may call a track clean, after deduplication, evidence verification, and classification. Clean means no distinct new accepted blocker or follow-up from that track; duplicate, refinement, disputed, out-of-scope, and backlog-only candidates do not reset the count.
- The first clean round moves a track to `probation`, and it must run again. The second consecutive clean round moves it to `dormant`, so later Loop rounds need not dispatch it.
- A new accepted blocker/follow-up resets its source track to `active` at zero. A finding from another track reactivates a dormant track when it materially affects that track's responsibility, evidence boundary, or likely fix surface.
- Incomplete, timeout, `PARTIAL`, `UNCERTAIN`, or an evidence gap never counts as clean. Dormant means two independently clean rounds, not permanent removal or proof by itself.

Convergence requires both no distinct new accepted blocker/follow-up in the latest completed round and every selected track dormant. A reactivated track must again complete two consecutive clean rounds. `N rounds` and `Closure verification` keep all resolved tracks active and do not use dormancy.

Completion criterion: the ledger explains every lifecycle transition and the evidence/classification that caused it.
