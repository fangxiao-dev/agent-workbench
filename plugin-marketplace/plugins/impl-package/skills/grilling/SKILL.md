---
name: grilling
description: >
  Grill the user relentlessly about a plan, decision, or idea. Use when the user
  wants to stress-test their thinking, uses any 'grill' trigger phrases, wants
  wave/batch decision rounds, or invokes grilling-waves / decision waves for a
  PRD, MVP, Spec, or plan.
---

Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled — the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Each question should be formatted like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Each round the user answers reshapes the tree — settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it — don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report — ask the rest of the frontier now. The _decisions_ are the user's — put each to them and wait.

After each round, state a short **reply contract** so the user can answer by number, for example:

- 「全部采纳」
- 「除 Q3 外全部采纳」
- 「Q2 选 B；Q4 按你的推荐」
- 「展开 Q1」

Do not stop per-question waiting once the round is out; wait for one batch reply.

When applying answers (especially against an upper-level product context), classify the batch:

- **Aligned** — choices fit the filter; absorb and open the next frontier.
- **Conflict** — choice fights the filter, or a real trade-off needs an explicit user pick (cost is material). Pause dependent branches; user either changes the decision or deliberately revises the filter. Do not ritualize this every round.
- **Gap** — the filter is missing a principle the answers now need. Propose a minimal filter add; user accepts or rejects before continuing.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.

## When the subject is a durable document

If the subject is a PRD, plan, Decision, Spec, MVP slice, or similar document (including former `grilling-waves` invocations):

1. **Upper-level product context first.** Before deep rounds, align a short decision filter — not a second PRD:
   - target user and product value
   - why now
   - what MVP must prove or unlock
   - what MVP should deliberately avoid
   - future compatibility worth keeping that does **not** authorize build now

   If missing, draft a short recommendation with assumptions marked, and get confirmation before opening the full tree. Keep it stable unless a later choice exposes a real conflict or gap.

2. **Use the filter while recommending.** Recommendations that expand MVP, invent speculative abstractions, or trade against the confirmed filter must name the **Conflict**. Only pause the frontier for real **Conflict** or **Gap** — not as a ritual every round.

3. **Do not edit the target document mid-grill.** Keep accepted choices, non-goals, deferrals, and open items in working memory (or a temporary notes surface the user already uses). Stable IDs (`R2-Q1`) help when the user answers by number.

4. **Write back only after confirmation.** When the frontier is empty, present a consolidated decision summary. Apply accepted decisions to authorized target docs only if the invocation already authorized post-convergence writeback, or after one explicit final confirm. Classify each displaced meaning as keep in place, migrate to a named home, replaced by an accepted decision, or user-deprecated — never silently drop a product commitment because the new text is shorter.

5. **After writeback, report briefly:**
   - which documents changed
   - which decision groups were absorbed
   - what remains unresolved or deferred
   - which stages were intentionally not run (gates, release, implementation, etc.)
