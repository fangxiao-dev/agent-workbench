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

Applies to every review (`initial` rounds, `finding-closure`, `terminal-final`, `N rounds` and `Loop`); normal reviews and final reviews use the same rules.

A review group owns the findings it raises: it keeps reviewing until each one is fixed and verified by the same group. Round counts are only a backstop against endless loops.

- **Review group**: the leaves selected for one review. Keep each leaf's session for the group's whole lifecycle; from round 2 send incremental instructions instead of starting new leaves.
- **Plan first**: when the work has a plan, the group reviews the plan (`--phase plan`) until a plan round closes with PASS, and only then reviews code. A group that never opened a plan round is not gated. Plan rounds are counted apart from code rounds: from the third plan round each `open` warns, without blocking, so the parent checks whether the review is stuck in local detail and whether the requirement can be narrowed at its root.
- **Round mode**: the first line of every round brief says `重新分析` (default: review the fixed input again) or `只核实关闭` (only check that the findings marked fixed are closed). The brief also lists fixed items and registered backlog so they are not reported again. A `只核实关闭` PASS is not convergence.
- **Triage**: after `close`, the parent records each accepted finding with `review_rounds.py triage add` as `plan-gap` (the plan did not design it) or `impl-drift` (the code did not follow the plan), and as design-type or control-type. A `plan-gap` sends the group back to plan rounds before more code is reviewed; an `impl-drift` is fixed in code directly.
- **Severity and class**: the parent judges severity and does not copy the reviewer's rating. Findings are design-type (behavior, data, permissions, pay calculation, contract) or control-type (commands, gate order, evidence registration, wording). The reviewers are strict by nature: before a finding is accepted the parent reads it as a principal engineer would. Only user-visible behavior and data safety block; for a feature that is simple from the outside, cut coarsely near the root instead of adding fine branches, copy or acceptance; everything else is a non-blocking backlog item.
- **Fix**: the original implementer fixes, resumed, and records it with `triage fixed --commit`. Design-type fixes change the plan document first, which goes into the next review round; code follows after it passes, then stable docs. The parent fixes control-type findings directly (`--self-verified`) without another round.
- **Verify**: the same group's next round checks every `fixed` finding and records `triage verify` (closed) or `triage reopen` (back to open). The second reopen of one finding needs a `--root-cut` sentence first: say whether the requirement can be cut near its root instead of patching again. The same kind of leak showing up a second time downstream (not visible to the script) calls for the same judgment.
- **Downgrade**: only the parent downgrades a finding to non-blocking, with a written reason (`triage downgrade --reason`); it goes to the backlog and no longer blocks the group.
- **Group complete**: every finding of the group is `verified` or downgraded, and the group's latest closed round raised no new design-type finding (`review_rounds.py status --group`).
- **Fresh group**: a complete group's work is not proof. Dispatch one fresh group (new leaves, no prior sessions, `open --succeeds <group>`) for one full-scope round to check whether anything important remains. If it raises design-type findings, it becomes the group that owns them and is judged by the same completion rule, but it has not confirmed anything: once it is complete, another fresh group follows. The review is converged only when a fresh group is complete and raised no design-type finding itself (`status` reports `converged`). Review keeps going until then.
- **Backstop**: one group runs at most 5 code rounds; `open` then refuses and a fresh group takes over the unresolved findings. There is no total round cap across groups, because that would cut review off before a fresh group can confirm. Instead, when three fresh groups in a row have not converged, `open` warns: stop and decide whether the requirement can be cut near its root, or ask the Owner.
- `review_rounds.py` keeps the per-group state beside the ledger (rounds, findings): `open` registers every track of the round and enforces the plan gate and the code-round cap, `close` refuses while a registered track has not returned, `triage` and `status` track ownership, `export` works only on a closed round.

Completion criterion: the ledger explains every group completion, fresh-group handover and downgrade, and the evidence/classification that caused it. Incomplete, timeout, `PARTIAL`, `UNCERTAIN`, or an evidence gap never counts toward completion. `N rounds` and `Closure verification` run their fixed rounds and do not track convergence.
