---
name: discuss-ledger
description: Use this whenever multiple agents (e.g. Claude and Codex/GPT, or two review passes) debate a plan, design, spec, or PRD and their opinions should be accumulated into a single shared discussion document. Triggers on natural phrases like "审一下这个计划并记录意见", "把你的意见写进 discuss 文档", "追加到讨论文档", "他也有意见,接着往里写", "继续收敛", "把刚才这个评审过程做成讨论记录", or any time you are asked to express a review opinion that another party will later respond to. Each agent maintains a convergence section first, then appends only its disagreements, until consensus or deadlock. Use this even when the user just says "discuss" plus a target file — do not hand-roll an ad-hoc review note.
user-invocable: true
---

# Discuss Ledger

Maintain a single Markdown ledger where two or more parties (typically this agent plus another agent like Codex/GPT, or the user) debate a plan/design and converge over rounds. The ledger exists so that, across many turns and many sessions, nobody re-litigates settled points and the live disagreements stay readable.

The document has two living parts:

1. **收敛区 (Convergence record)** — at the very top. Settled decisions only, one line each. Promoted into here *before* you write new opinions, so it's always the current source of truth for "what's decided."
2. **讨论记录 (Discussion log)** — round-by-round. **Only disagreements** in full; agreements are one line ("收敛入区:…"). Signal over noise.

## The script does the bookkeeping — you do the judgment

All mechanical structure (frontmatter state machine, point IDs, section moves, round bumps, deadlock counting, gitignore) is owned by `scripts/discuss_ledger.py`. **Do not hand-edit the ledger's YAML, table, or section structure** — call the script and pass your decisions as arguments. This keeps every agent's writes consistent and removes the bookkeeping errors agents make (forgetting to bump the round, renumbering IDs, leaving the table stale).

What you decide, the script can't:

- whether a point is genuinely agreed (→ `converge`) or still contested (→ `contest`)
- the argument text and its evidence
- whether a round had real **movement** (new argument / evidence / concession) or was a restatement
- which convergence marker applies (`一致` vs `用户裁决`)
- whether to raise a new point at all

Before converging or contesting, verify factual premises that affect the conclusion. If the other party's premise is wrong, record that explicitly: either contest the point, or converge with a corrected rationale when the final action still holds. This keeps useful decisions while preventing false reasoning from becoming part of the source of truth.

Run it from the repo root (paths are resolved relative to it):

```bash
python <skill>/scripts/discuss_ledger.py <subcommand> ...
```

`--root` defaults to the current working directory, so you only need to pass `--root <repo-root>` when you are *not* already at the repo root. All subcommands except `init` take `--slug`.

Ledgers live at `docs/exchange/discuss/discuss-<slug>.md` — the repo's untracked scratch area. They are **ephemeral debate scaffolding**, not deliverables; the converged plan is the deliverable. `init` creates the dir and adds `docs/exchange/discuss/` to `.gitignore` (scoped) automatically.

## Step 1 — Locate or initialize

First decide the slug. If the discussion is anchored to a doc (a plan/spec/PRD path), the slug is that file's basename without extension (e.g. `docs/plans/2026-06-18-foo.md` → slug `2026-06-18-foo`). If there's no anchor doc, ask the user for a short slug — don't guess silently.

Before opening or answering a ledger, read the anchored doc or explicit review target enough to form your own judgment. The ledger is a debate about that source, not a substitute for reading it. When you cite facts, verify them against the source doc, repository files, or script output; line numbers and command output are better than memory.

Check whether the ledger exists (glob `docs/exchange/discuss/discuss-<slug>.md`):

- **Does not exist → you are the initiator.** Create it:
  ```bash
  python ... init --topic docs/plans/2026-06-18-foo.md --participants CC,Codex --initiator <you>
  ```
  `--topic` may be a doc path (recorded as the review target) or free text. `--initiator` is whoever speaks round 1 (usually you).
- **Exists → you are a responder.** Read ground truth with `status` before doing anything:
  ```bash
  python ... status --slug 2026-06-18-foo
  ```

## Step 2 — Take your turn

A turn is always: **read → promote settled points → respond with disagreements → end the turn.** The order matters — promoting convergence *before* arguing is the whole discipline.

1. **`status`** — read current round, who's next, and every open point with its 已历轮次. Don't trust your own parse of the file; ask the script.

   If `status` is already `已达成一致` or `僵局`, do not append another round. Report the converged outcomes or the deadlocked points to the user. Only continue if the user gives genuinely new evidence or explicitly asks to start a new discussion.

   After `status`, read the ledger file itself before judging. `status` is the state summary; the full discussion log contains evidence, corrected premises, and nuances that must inform converge/contest decisions.

2. **Promote what's now settled (`converge`).** For each point you now genuinely agree on (or the user ruled), promote it *before* writing new opinions:
   ```bash
   python ... converge --slug S --point D1 --marker "一致" --line "保留兼容入口,重指新 dashboard"
   ```
   Marker is `一致` (both agree) or `用户裁决` (user ruled; write `用户裁决·覆盖CC` if it overrides a party). Convergence ≠ agreement — a user ruling settles a point even if you still disagree; record it and stop arguing it.

   When a point's original premise is wrong but its practical conclusion is still right, converge the corrected conclusion rather than preserving the bad premise. Write the correction in the convergence line so later agents do not inherit false reasoning.

   A convergence line should include the final decision, corrected rationale if any, and the concrete change requested. Keep it one line, but make it actionable enough that the user can apply it to the target plan/spec.

3. **Normalize the other party's free-form contribution.** The other agent may have edited the file directly without the script, so its new points aren't in the table. Register each as a tracked point so it can be followed:
   ```bash
   python ... add-point --slug S --author <them> --summary "..." --body "their argument"
   ```

   First map free-form notes to existing points. Use `contest` for a response to an existing point, `converge` for a settled point, and `add-point` only for a materially new disagreement.

4. **Respond to live disputes (`contest`)** — counter an existing point in the current round:
   ```bash
   python ... contest --slug S --point D2 --author <you> --body - --movement true   # body via stdin
   ```
   Set `--movement false` when you're restating with no new ground. The script increments 已历轮次 and, at ≥2 rounds with no movement, **auto-marks the point 僵局** — so be honest about movement; that flag is what lets a dead debate actually die instead of looping.

   Set `--movement true` only for new evidence, corrected facts, a narrowed scope, an explicit concession, or a concrete compromise. Rephrasing the same preference is `--movement false`.

5. **Coverage pass + new disagreements (`add-point`).** Before ending your turn, scan the target plan/spec once for important risks not represented by existing open/converged points. Add a new point only when it is materially distinct and would change implementation, verification, or user decision-making.

   `add-point` auto-allocates the next `Dn`, adds a table row, and writes the argument under the current round. Always include reasoning and evidence (file paths, line numbers, verified facts), not bare positions — that's what lets the next party engage.

6. **`end-turn`** — closes your turn. It recomputes overall status and either bumps the round / sets who's next, or declares the exit:
   ```bash
   python ... end-turn --slug S --next Codex      # while debate is open
   python ... end-turn --slug S                   # when you think it may be resolved
   ```

   Do not run `end-turn` until every existing point has one of: converged, contested with evidence, marked no-movement, or intentionally left open for the next party. Also account for any high-impact issue you found during the coverage pass.

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

When the script prints an `EXIT:` line, **stop appending rounds and tell the user**: summarize what converged, and list any deadlocked points needing their ruling. If they rule, that becomes a `converge --marker "用户裁决…"` entry that can break the deadlock.

## Anti-patterns

- **Hand-editing structure.** Don't touch the YAML/table/section layout directly — use the script, or its invariants drift. Free-form *prose* by the other party is fine and preserved; your job is to register their points via the script on your turn.
- **Re-opening 收敛区 items.** Settled stays settled unless genuinely new evidence appears (then say so explicitly).
- **Performative agreement.** Don't concede just to end the debate. If a counter is wrong or unverified, contest it with reasoning — this skill surfaces real disagreement, it doesn't manufacture consensus. (See `superpowers:receiving-code-review` for the spirit.)
- **Restating without movement.** If you have nothing new, set `--movement false` and let the point deadlock rather than looping.
- **Dumping agreements into the log.** Agreements are a one-line `converge`; their substance lives in 收敛区, not re-argued in the discussion log.

## Safety

- Only create/modify the single `discuss-<slug>.md` ledger (and read the source doc). Do not touch the plan/spec itself unless the user explicitly asks to "落计划".
- The ledger is a notes artifact, written directly (no dry-run gate required) — but never write outside `docs/exchange/discuss/`.

`templates/discuss-template.md` is a human-readable illustration of the produced structure; the script is the authoritative writer.
