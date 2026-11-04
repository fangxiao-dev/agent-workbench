# Loop Mode

Use this only when the user explicitly asks for a bounded multi-round loop (`组织 3 轮 loop 审查`, `继续按 loop 深挖`). A loop is a series of normal orchestrations (see [orchestrator.md](orchestrator.md)); this file only says how to decide whether another round is worth running and what to carry between rounds. Do not add loop control to the normal orchestration path.

## Judging Another Round

A user-provided round count is a ceiling, not an order to run empty rounds. Start another round when there is something new to look at and the user's intent still points that way:

- the previous ledger ended in `僵局`, or participants report a material conflict that evidence has not settled;
- the target was revised, new evidence or a user ruling arrived, or the question was narrowed;
- the **观点评估** says continued discussion may add value.

Stop and say so when a round would only restate earlier points, or no new input exists. Then the useful next step is to revise the target or give a new focus. With no user-given bound, run one conservative round and say so. Never loop unbounded.

## Carrying Memory

Write a short `docs/exchange/discuss/discuss-<slug>-summary.md` (plain Markdown, no ledger CLI) after each round and pass it into the next round's topic. Keep only what constrains the next round:

- the target and settled conclusions with their rationale;
- open questions, the current best answer, and what evidence would close each;
- points not to re-litigate;
- the focus of the next round and a one-line outcome per finished round.

Each round uses its own ledger, `discuss-<slug>-round-<n>.md`, which remains the evidence trail. Without the summary, agents repeat old arguments.

## On Stopping

Report the summary path, the round ledger paths, settled conclusions, remaining open questions, why the loop stopped, and whether more discussion needs new input or a user ruling.
