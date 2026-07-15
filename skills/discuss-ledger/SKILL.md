---
name: discuss-ledger
description: Use this when two or more parties need to accumulate and resolve live disagreements across review rounds for a plan, design, spec, PRD, or skill. Triggers on explicit requests such as "组织审核 ...", "用 discuss orchestrator 审 ...", "自动讨论 ...", "组织 3 轮 loop 审查 ...", "多轮 loop review ...", "把你的意见写进 discuss 文档", "追加到讨论文档", "他也有意见,接着往里写", "继续收敛", or "discuss <target>". Do not use for an ordinary single-pass review, a one-way subagent findings handoff, or a review without a live responding party; return the review directly instead. Each participant maintains a convergence section first, then appends only disagreements until consensus or deadlock.
user-invocable: true
---

# Discuss Ledger

Maintain a single Markdown ledger where two or more parties (typically this agent plus another agent like Codex/GPT, or the user) debate a plan/design and converge over rounds. The ledger exists so that, across many turns and many sessions, nobody re-litigates settled points and the live disagreements stay readable.

## Trigger boundary

Before creating or reading a ledger, confirm that the work needs an accumulating, multi-party discussion: an explicit `discuss`/orchestrated/multi-round request, an existing ledger continuation, or a known second party who will respond to unresolved points. An ordinary one-pass review, review report, or one-way subagent handoff is not a discussion: return findings through that workflow and do not create a ledger. Do not turn an otherwise single review into a ledger merely because another person might read the result later.

The document has two living parts:

1. **收敛区 (Convergence record)** — at the very top. Settled decisions only, one line each. Promoted into here *before* you write new opinions, so it's always the current source of truth for "what's decided."
2. **讨论记录 (Discussion log)** — round-by-round. **Only disagreements** in full; agreements are one line ("收敛入区:..."). Signal over noise.

## References

Read only the reference needed for the current path:

- Before invoking `scripts/discuss_orchestrator.py`, read `references/orchestrator.md`.
- If the user asks for a bounded multi-round loop review (for example "组织 3 轮 loop 审查") or the exit evaluation suggests continued discussion may be useful and the gate may pass, read `references/loop-mode.md`.
- If Claude Code / `claude -p` reports auth/login, hangs, or looks unavailable during orchestration while the user says they are already logged in, read `references/claude-code-noninteractive.md`.
- When you need exact `discuss_ledger.py` command syntax, read `references/ledger-cli.md`.

## Language

Prefer Chinese for discussion entries, point summaries, convergence lines, and user-facing summaries. Use another language only when the user explicitly asks for it, the target document requires it, or preserving a technical term / quoted text avoids ambiguity.

## The script does the bookkeeping — you do the judgment

All mechanical structure (frontmatter state machine, point IDs, section moves, round bumps, deadlock counting, gitignore) is owned by `scripts/discuss_ledger.py`. **Do not hand-edit the ledger's YAML, table, or section structure** — call the script and pass your decisions as arguments. This keeps every agent's writes consistent and removes the bookkeeping errors agents make.

What you decide, the script can't:

- whether a point is genuinely agreed (→ `converge`) or still contested (→ `contest`)
- the argument text and its evidence
- whether a round had real **movement** (new argument / evidence / concession) or was a restatement
- which convergence marker applies (`一致` vs `用户裁决`)
- whether to raise a new point at all

Before converging or contesting, verify factual premises that affect the conclusion. If the other party's premise is wrong, record that explicitly: either contest the point, or converge with a corrected rationale when the final action still holds. This keeps useful decisions while preventing false reasoning from becoming part of the source of truth.

Run the ledger CLI from the repo root (paths are resolved relative to it). `--root` defaults to the current working directory, so pass `--root <repo-root>` only when you are not already at the repo root. See `references/ledger-cli.md` for exact commands.

Ledgers live at `docs/exchange/discuss/discuss-<slug>.md` — the repo's untracked scratch area. They are **ephemeral debate scaffolding**, not deliverables; the converged plan is the deliverable. `init` creates the dir and adds `docs/exchange/discuss/` to `.gitignore` (scoped) automatically.

## Orchestrated auto-discussion

If the user asks for `组织审核`, `discuss orchestrator`, `自动讨论`, "Codex 作为 orchestrator", or asks to "用 discuss 审" a target, do not perform a normal single-agent review. Read `references/orchestrator.md`, then run the local orchestrator unless the user explicitly asks for manual ledger editing.

The orchestrator timeout rule is a hard preflight requirement: before invoking `scripts/discuss_orchestrator.py`, set the outer tool/wrapper timeout high enough for the whole run, not just one agent call. Use the formula and defaults in `references/orchestrator.md`.

## Step 1 — Locate or initialize

First decide the slug. If the discussion is anchored to a doc (a plan/spec/PRD path), the slug is that file's basename without extension (e.g. `docs/plans/2026-06-18-foo.md` → slug `2026-06-18-foo`). If there's no anchor doc, ask the user for a short slug — don't guess silently.

Before opening or answering a ledger, read the anchored doc or explicit review target enough to form your own judgment. The ledger is a debate about that source, not a substitute for reading it. When you cite facts, verify them against the source doc, repository files, or script output; line numbers and command output are better than memory.

Check whether the ledger exists (glob `docs/exchange/discuss/discuss-<slug>.md`):

- **Does not exist → you are the initiator.** Create it with `init`.
- **Exists → you are a responder.** Read ground truth with `status` before doing anything.

Use `references/ledger-cli.md` for exact command syntax.

## Step 2 — Take your turn

A turn is always: **read → promote settled points → respond with disagreements → end the turn.** The order matters — promoting convergence *before* arguing is the whole discipline.

1. **`status`** — read current round, who's next, and every open point with its 已历轮次. Don't trust your own parse of the file; ask the script.

   If `status` is already `已达成一致` or `僵局`, treat that as "no open disputes at the last exit," not as a permanent freeze. Do not append routine restatements or reopen points just because you want another pass. However, if the user brings new evidence, a later review finds a materially new risk, implementation reveals a contradiction, or the user explicitly asks to continue, reopen the ledger deliberately:
   - for a new issue, add a new tracked point with `add-point`;
   - for new evidence that undermines an existing convergence line, add a new point that references the prior `Dn` and explains what changed;
   - preserve the old convergence record instead of hand-editing it away.
   Reopening is encouraged when it prevents a stale consensus from becoming the plan of record.

   After `status`, read the ledger file itself before judging. `status` is the state summary; the full discussion log contains evidence, corrected premises, and nuances that must inform converge/contest decisions.

2. **Promote what's now settled (`converge`).** For each point you now genuinely agree on (or the user ruled), promote it *before* writing new opinions. Marker is `一致` (both agree) or `用户裁决` (user ruled; write `用户裁决·覆盖CC` if it overrides a party).

   Convergence ≠ agreement — a user ruling settles a point even if you still disagree; record it and stop arguing it.

   When a point's original premise is wrong but its practical conclusion is still right, converge the corrected conclusion rather than preserving the bad premise. Write the correction in the convergence line so later agents do not inherit false reasoning.

   A convergence line should include the final decision, corrected rationale if any, and the concrete change requested. Keep it one line, but make it actionable enough that the user can apply it to the target plan/spec.

3. **Normalize the other party's free-form contribution.** The other agent may have edited the file directly without the script, so its new points aren't in the table. Register each materially new disagreement as a tracked point.

   First map free-form notes to existing points. Use `contest` for a response to an existing point, `converge` for a settled point, and `add-point` only for a materially new disagreement.

4. **Respond to live disputes (`contest`).** Counter an existing point in the current round. Set `--movement false` when you're restating with no new ground. The script increments 已历轮次 and, at ≥2 rounds with no movement, auto-marks the point 僵局.

   Set `--movement true` only for new evidence, corrected facts, a narrowed scope, an explicit concession, or a concrete compromise. Rephrasing the same preference is `--movement false`.

5. **Coverage pass + new disagreements (`add-point`).** Before ending your turn, scan the target plan/spec once for important risks not represented by existing open/converged points. Add a new point only when it is materially distinct and would change implementation, verification, or user decision-making.

   `add-point` auto-allocates the next `Dn`, adds a table row, and writes the argument under the current round. Always include reasoning and evidence (file paths, line numbers, verified facts), not bare positions — that's what lets the next party engage.

6. **`end-turn`** — closes your turn. It recomputes overall status and either bumps the round / waits for the next speaker to be assigned, or declares the exit.

   Do not run `end-turn` until every existing point has one of: converged, contested with evidence, marked no-movement, or intentionally left open for the next party. Also account for any high-impact issue you found during the coverage pass.

   If the debate remains open, `end-turn` sets `next: 待指定`. The previous speaker must not choose the next speaker. The actual caller, user, or orchestrator assigns the next turn explicitly with `set-next`.

Use `--dry-run` on any mutating command to preview the resulting file without writing.

## Review discipline

The ledger is useful only when each party contributes new judgment instead of duplicating a normal review.

- **Separate fact checks from opinions.** A strong turn can challenge wrong evidence while still keeping a usable conclusion. If the recommendation is right for a different reason, say that and converge the corrected rationale instead of mechanically agreeing or mechanically rejecting.
- **Record only live disagreement in the log.** If you agree with a point, use `converge`; do not add another paragraph saying the same thing. If you partly agree, converge the agreed slice and contest only the remaining live issue.
- **Prefer narrow, actionable summaries.** A point summary should name the defect ("final integration gate has no executable hook"), not the remedy alone. The body can carry evidence and proposed fixes.
- **Do not overfit to one partner.** Participant names may be `CC`, `Codex`, `Claude`, `GPT`, or a human reviewer. Use the names in the existing ledger; when initializing, choose the names the user used.
- **Treat the converged plan as the deliverable.** The discuss file is scratch debate scaffolding. When all points converge, summarize what the target plan should change; do not edit the plan unless the user asks to apply the conclusions.

## Step 3 — Exit

`end-turn` sets `status` automatically once **every point is either 收敛 or 僵局**:

- all converged → `已达成一致`
- any deadlocked → `僵局` (and `next: 用户`)

When the script prints an `EXIT:` line, stop the current debate turn and tell the user: summarize what converged, and list any deadlocked points needing their ruling. If they rule, that becomes a `converge --marker "用户裁决..."` entry that can break the deadlock.

After an orchestrated discussion exits, add a short **观点评估** section to the user-facing summary. This is not a new ledger point and does not reopen the debate. Judge the discussion itself:

- **质量判断**: whether the debate produced implementation-grade conclusions, only surface-level restatements, or mixed value.
- **有效贡献**: which findings changed the plan/spec/review outcome, especially evidence-backed risks that were not obvious from the target alone.
- **薄弱处**: where coverage was narrow, evidence was weaker, points overlapped, or the orchestrator target omitted relevant docs/code.
- **是否继续讨论**: say whether more discussion is useful. Prefer "revise the target, then run a focused follow-up review" over continuing abstract debate when all live points already converged.

`EXIT` closes the current state; it does not prohibit future reopening when genuinely new evidence, newly discovered risk, implementation feedback, or an explicit user request appears. A later turn may reopen by adding a new point as described in Step 2.

## Anti-patterns

- **Hand-editing structure.** Don't touch the YAML/table/section layout directly — use the script, or its invariants drift. Free-form *prose* by the other party is fine and preserved; your job is to register their points via the script on your turn.
- **Unjustified re-opening.** Reopen when there is genuinely new evidence, a newly discovered risk, implementation feedback, or an explicit user request. Preserve prior convergence lines and add a new tracked point explaining what changed; do not erase or quietly rewrite settled history.
- **Performative agreement.** Don't concede just to end the debate. If a counter is wrong or unverified, contest it with reasoning — this skill surfaces real disagreement, it doesn't manufacture consensus.
- **Restating without movement.** If you have nothing new, set `--movement false` and let the point deadlock rather than looping.
- **Dumping agreements into the log.** Agreements are a one-line `converge`; their substance lives in 收敛区, not re-argued in the discussion log.

## Safety

- Only create/modify the single `discuss-<slug>.md` ledger (and read the source doc). Do not touch the plan/spec itself unless the user explicitly asks to "落计划".
- In loop mode only, also create/modify the loop summary and per-round temporary ledgers described in `references/loop-mode.md`; keep them under `docs/exchange/discuss/`.
- The ledger is a notes artifact, written directly (no dry-run gate required) — but never write outside `docs/exchange/discuss/`.

`templates/discuss-template.md` is a human-readable illustration of the produced structure; the script is the authoritative writer.
