# Impl Planning Rubric

## Confirmed preferences

- Choose the smallest earned Composition; small linear work may use no Tickets and no DAG.
- D/S/P are readable aliases only; Git commit is the cross-session comparison point.
- One complete bundle receives one review and one owner approval.
- Plan holds Coverage、strategy、verification and integration authorization, while current execution state stays in `state.json` and is exposed through `progress.md`.
- Only affected records require revalidation after a plan change.
- Plan only maps an already-frozen Spec contract ensemble to implementation and verification. If observable behavior, data identity, permission, concurrency, recovery, or public shape remains undecided, return to a Spec revision without creating Plan/state or inventing a second DTO/schema contract.
