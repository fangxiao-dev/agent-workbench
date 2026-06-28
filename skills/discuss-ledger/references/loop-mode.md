# Loop Mode

Use this reference only for bounded multi-round discussion loops. Loop mode is a meta-workflow above ordinary orchestration: each major round may run a normal discuss-ledger orchestration, but the loop decides whether another major round is justified and carries forward a compact memory so agents do not rediscover the same points.

Loop mode is separate from `orchestrator.md`. Do not add loop control logic to the normal orchestration path.

## Trigger

Enter loop evaluation when the user explicitly asks for a loop, for example:

- `组织 3 轮 loop 审查`
- `做 X 轮循环审查`
- `multi-round loop review`
- `继续按 loop 深挖`

You may also evaluate the loop gate after an orchestration exit when the **观点评估** says more discussion may be useful. Do not enter loop mode from that soft signal alone.

## Loop Gate

Start or continue a loop only when the gate passes. A user-provided round count is a ceiling, not a command to run empty rounds.

The first major round may start when the user explicitly requested a bounded loop and there is a concrete target.

Every later major round must pass the continuation gate. The continuation gate passes only when all of these are true:

1. **Soft signal**: the exit **观点评估** says continued discussion may produce new value.
2. **Hard signal**: at least one observable rule fires:
   - the ledger exited as `僵局`;
   - a point reached two rounds with no movement;
   - high-impact new evidence appeared after the previous exit;
   - the target was revised after the previous discussion;
   - reviewers found materially different risks in separate domains.
3. **User intent**: the latest user prompt asks to continue, deepen, loop, compare, re-review, or otherwise signals that one-shot review is not enough.
4. **New input**: there is new material to inspect, such as a changed target document, code diff, user ruling, new evidence, or a narrowed question. If no new input exists, tell the user the next useful step is to revise the target or provide a new focus.

Never run an unbounded loop. If the user gives no round count, ask for a bound or choose one conservative next round only and say so. If the continuation gate fails before the round ceiling is reached, stop early and report why.

## Artifacts

Keep all loop artifacts under `docs/exchange/discuss/`.

- `discuss-<slug>-summary.md` — durable loop summary across major rounds.
- `discuss-<slug>-round-<n>.md` — temporary ledger for major round `n`.

The summary is not a normal ledger and does not use the ledger CLI. It is a plain Markdown memory document. Keep it short and rewrite it after each major round.

Suggested summary structure:

```markdown
# Loop Summary: <slug>

## Target

- <source doc/path/topic>

## Settled Conclusions

- <decision and rationale>

## Open Questions

- <question, current best answer, what evidence would close it>

## Do Not Re-Litigate

- <point already settled or proven low-value>

## Next Round Focus

- <specific questions for the next major round>

## Round History

- Round 1: <ledger path> — <one-line outcome>
```

## Major Round Procedure

For each major round:

1. Read the target, the loop summary if it exists, and any new input from the user.
2. Decide the round slug: `discuss-<slug>-round-<n>.md`.
3. Pass the loop summary into the round topic/context. The topic must tell agents:
   - what the target is;
   - what has already converged;
   - what must not be repeated;
   - what new input or focus this round should evaluate.
4. Run normal orchestration for the round, following `orchestrator.md`.
5. On exit, produce the normal user-facing report plus **观点评估**.
6. Rewrite `discuss-<slug>-summary.md` from the round result:
   - promote settled conclusions;
   - keep only live open questions;
   - add repeated or low-value points to `Do Not Re-Litigate`;
   - name the next round focus if the loop gate still passes.
7. Re-run the loop gate before starting another major round.

Completion criterion: every major round has either produced new settled conclusions, a narrowed open question, or an explicit decision to stop. If a round only restates prior points, stop the loop and report that no further discussion is useful without new input.

## Context Rules

The loop summary is mandatory context for every new temporary ledger. Without it, agents will repeat old arguments.

Keep the summary concise. It should contain decisions and live questions, not full debate transcripts. The temporary ledgers remain the evidence trail.

Do not carry every old point into the new round. Carry only:

- settled conclusions that constrain the next review;
- unresolved questions;
- explicit "do not repeat" points;
- the new evidence or changed target diff.

## Exit Reporting

When loop mode stops, tell the user:

- loop summary path;
- round ledger paths;
- final settled conclusions;
- remaining open questions or deadlocks;
- why the loop stopped;
- whether another loop would need new input, target changes, or user裁决.

Do not present "more discussion is possible" as a reason to continue. Continue only when the gate passes.
