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

Run it with the repo root so paths resolve:

```bash
python <skill>/scripts/discuss_ledger.py --root <repo-root> <subcommand> ...
```

Ledgers live at `docs/exchange/discuss/discuss-<slug>.md` — the repo's untracked scratch area. They are **ephemeral debate scaffolding**, not deliverables; the converged plan is the deliverable. `init` creates the dir and adds `docs/exchange/discuss/` to `.gitignore` (scoped) automatically.

## Step 1 — Locate or initialize

First decide the slug. If the discussion is anchored to a doc (a plan/spec/PRD path), the slug is that file's basename without extension (e.g. `docs/plans/2026-06-18-foo.md` → slug `2026-06-18-foo`). If there's no anchor doc, ask the user for a short slug — don't guess silently.

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

2. **Promote what's now settled (`converge`).** For each point you now genuinely agree on (or the user ruled), promote it *before* writing new opinions:
   ```bash
   python ... converge --slug S --point D1 --marker "一致" --line "保留兼容入口,重指新 dashboard"
   ```
   Marker is `一致` (both agree) or `用户裁决` (user ruled; write `用户裁决·覆盖CC` if it overrides a party). Convergence ≠ agreement — a user ruling settles a point even if you still disagree; record it and stop arguing it.

3. **Normalize the other party's free-form contribution.** The other agent may have edited the file directly without the script, so its new points aren't in the table. Register each as a tracked point so it can be followed:
   ```bash
   python ... add-point --slug S --author <them> --summary "..." --body "their argument"
   ```

4. **Respond to live disputes (`contest`)** — counter an existing point in the current round:
   ```bash
   python ... contest --slug S --point D2 --author <you> --body - --movement true   # body via stdin
   ```
   Set `--movement false` when you're restating with no new ground. The script increments 已历轮次 and, at ≥2 rounds with no movement, **auto-marks the point 僵局** — so be honest about movement; that flag is what lets a dead debate actually die instead of looping.

5. **Raise new disagreements (`add-point`)** — auto-allocates the next `Dn`, adds a table row, and writes the argument under the current round. Always include reasoning and evidence (file paths, line numbers, verified facts), not bare positions — that's what lets the next party engage.

6. **`end-turn`** — closes your turn. It recomputes overall status and either bumps the round / sets who's next, or declares the exit:
   ```bash
   python ... end-turn --slug S --next Codex      # while debate is open
   python ... end-turn --slug S                   # when you think it may be resolved
   ```

Use `--dry-run` on any mutating command to preview the resulting file without writing.

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
