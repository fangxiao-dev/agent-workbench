---
name: discuss-ledger
description: Use this whenever multiple agents (e.g. Claude and Codex/GPT, or two review passes) debate a plan, design, spec, or PRD and their opinions should be accumulated into a single shared discussion document. Triggers on natural phrases like "审一下这个计划并记录意见", "把你的意见写进 discuss 文档", "追加到讨论文档", "他也有意见,接着往里写", "继续收敛", "把刚才这个评审过程做成讨论记录", or any time you are asked to express a review opinion that another party will later respond to. Each agent maintains a convergence section first, then appends only its disagreements, until consensus or deadlock. Use this even when the user just says "discuss" plus a target file — do not hand-roll an ad-hoc review note.
user-invocable: true
---

# Discuss Ledger

Maintain a single Markdown ledger where two or more parties (typically this agent plus another agent like Codex/GPT, or the user) debate a plan/design and converge over rounds. The ledger exists so that, across many turns and many sessions, nobody re-litigates settled points and the live disagreements stay readable.

The document has exactly two living parts:

1. **收敛区 (Convergence record)** — kept at the very top. Settled decisions only, one line each. Every agent, *before* writing its own new opinion, first promotes any newly-settled points into this section. This is the single source of truth for "what's decided."
2. **讨论记录 (Discussion log)** — round-by-round. Record **only disagreements** in full; for points you agree with, mention them in one line ("收敛入区:A、B") and move on. Signal over noise — agreements belong in 收敛区, not re-argued here.

## Core principle

Each turn is *additive and reconciling*, never destructive. You append your round; you do not rewrite the other party's words. You only edit 收敛区 (to promote settled points) and the 未决分歧 status table (to update each open point's status). The other party may have written free-form prose that ignores this template — that is expected. On your turn, normalize what you can (assign point IDs, attribute authorship) and proceed; do not demand they follow the format.

## Step 1 — Locate or initialize the ledger

Discuss ledgers are **ephemeral debate scaffolding**, not deliverables — the converged plan/spec is the deliverable. So they live in the repo's untracked scratch area, never next to the tracked source doc (where they'd look like deliverables and risk being committed by accident).

Determine the target file before doing anything else. The ledger always lives under `docs/exchange/discuss/` (the repo's established scratch/exchange convention — create the folder if missing):

- **Anchored to a doc** (a plan/spec/PRD path is in play): use `docs/exchange/discuss/discuss-<basename>.md`, where `<basename>` is the source filename without extension. Example: reviewing `docs/plans/2026-06-18-foo.md` → `docs/exchange/discuss/discuss-2026-06-18-foo.md`. Record the source path in the `topic:` frontmatter so the link back is preserved.
- **No anchor doc**: ask the user for a short slug, then use `docs/exchange/discuss/discuss-<slug>.md`. Do not guess a slug silently.

If `docs/exchange/discuss/` is not yet git-ignored, the initiator adds `docs/exchange/discuss/` to `.gitignore` (scoped — do not ignore all of `docs/exchange/`, other skills keep notes there that may be committed).

Then glob for the target path:

- **Does not exist** → you are the initiator. Copy `templates/discuss-template.md`, fill the frontmatter, and write Round 1 (Step 3, initiator path).
- **Exists** → you are a responder. Read it fully and follow Step 3, responder path.

## Step 2 — Understand the document shape

Use `templates/discuss-template.md` as the canonical structure. Frontmatter carries the live state machine:

- `status`: `进行中` | `已达成一致` | `僵局`
- `round`: current round number (integer)
- `next`: who should speak next (a participant name, or `用户` when waiting on a ruling)
- `participants`: list of party names

Body sections, in order: `## 收敛区(已定论,勿重开)`, `## 未决分歧`(a status table), `## 讨论记录`(rounds).

## Step 3 — Take your turn

### Initiator (file did not exist)

1. Write frontmatter: `status: 进行中`, `round: 1`, `participants`, `next: <the other party>`.
2. Leave 收敛区 empty (nothing settled yet) or seed it only with points that are genuinely not in dispute.
3. In 未决分歧, list each point you are raising with a stable point ID (`D1`, `D2`, …), a one-line summary, status `分歧`, and `已历轮次: 1`.
4. In 讨论记录, add `### 轮次 1 · <你的名字>` and write each point's full argument **with its reasoning** — not just the position. Reasoning is what lets the next party actually engage instead of restating.

### Responder (file existed)

Do these in order — the order is the whole point of the skill:

1. **Promote settled points first.** Re-read the last round. For every point where you now genuinely agree (or the user has ruled), move it into 收敛区 as a one-liner with a **source marker** (see below) and drop it from / mark it resolved in the 未决分歧 table. Do this *before* writing your own new opinions, so the convergence record is always current when you start arguing.
2. **Normalize the opponent's contribution** if it was free-form: assign point IDs to any new disagreements they raised, so they can be tracked.
3. **Bump `round`** and set `### 轮次 N · <你的名字>`.
4. **Record only disagreements in full.** For points you accept, write one line ("收敛入区:A、B、E — 同意,不展开"). For points you contest, write your counter-argument *with reasoning and evidence* (file paths, line numbers, verified facts — ground it, don't assert).
5. **Update the 未决分歧 table**: for each still-open point, set status and increment `已历轮次` if it was contested again this round.
6. **Update `next`** to the other party (or `用户` if a point now needs a ruling).

## Convergence source markers

A point is "converged" when it leaves the debate — but *how* it left matters, so mark the source:

- `[一致]` — both parties agree. One proposed, the other accepted without counter.
- `[用户裁决]` — the user made a final ruling. If it overrides a party, say so: `[用户裁决·覆盖CC]`.

Convergence ≠ agreement. A point the user rules on is settled even if an agent still disagrees — record it in 收敛区 with the override marker, and stop arguing it. The dissent is preserved in the discussion log; it just no longer blocks.

## Deadlock detection (per-point, not whole-document)

Track deadlock **per point**, not for the document as a whole — one stuck point should not keep the ledger open forever while others resolve.

A point is in **僵局 (deadlock)** when it has been contested across **≥2 full rounds by both parties with no movement**. "Movement" means a genuinely new argument, new evidence, a concession, or a narrowing of scope. A mere restatement of the same position is *not* movement.

When you detect a deadlocked point:

- Mark its status `僵局` in the 未决分歧 table.
- Stop arguing it. Do not open round 3 on the same ground — that wastes turns and the user's attention.

## Step 4 — Exit conditions

The ledger is done when **every open point is either in 收敛区 or marked 僵局**. At that point:

- All points converged → set `status: 已达成一致`.
- Some points deadlocked → set `status: 僵局`.

Then **stop updating and tell the user**: summarize what converged and, if any, list the deadlocked points needing their ruling. Do not keep appending rounds after exit — if the user wants to break a deadlock, they rule, and that ruling becomes a `[用户裁决]` convergence entry.

## Anti-patterns

- **Re-opening 收敛区 items.** Once settled, a point stays settled unless genuinely new evidence appears (then re-open explicitly with a note, don't silently relitigate).
- **Performative agreement.** Do not concede just to end the debate. If a counter-argument is technically wrong or unverified, say so with reasoning — this skill exists to surface real disagreement, not to manufacture consensus. (See `superpowers:receiving-code-review` for the spirit.)
- **Restating without movement.** If you have nothing new on a point, don't re-argue it — let it deadlock.
- **Rewriting the other party's text.** Append your round; never edit their words. Only 收敛区 and the status table are shared mutable surfaces.
- **Dumping agreements into the discussion log.** Agreements are one line ("收敛入区:…"); their substance lives in 收敛区. The log is for live disputes only.

## Safety

- Only create/modify the single `discuss-<slug>.md` ledger and, if anchored, read the source doc. Do not touch the plan/spec itself unless the user explicitly asks to "落计划".
- Default to writing the ledger directly (this is a notes artifact, not source code). There is no dry-run gate here — but never edit files outside the ledger and its directory.
