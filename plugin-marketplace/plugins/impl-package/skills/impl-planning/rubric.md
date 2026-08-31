# Impl Planning Rubric

## Confirmed preferences

- Choose the smallest earned Composition; small linear work may use no Tickets and no DAG.
- D/S/P are optional readable aliases only; Git commit is the cross-session comparison point.
- One complete bundle receives one review and one owner approval.
- Plan holds only global scheduling — Composition, Ticket order/dependency, shared-resource serialization, integration/rollout boundary, and Final Gate criteria — while per-constraint coverage and verification live in each Ticket's Contract references and AC; current execution state stays in `state.json` and is exposed through `progress.md`.
- Only affected records require revalidation after a plan change.
- Plan only maps an already-frozen Spec contract ensemble to implementation and verification. If observable behavior, data identity, permission, concurrency, recovery, or public shape remains undecided, return to req-align without creating Plan/state or inventing a second DTO/schema contract.
