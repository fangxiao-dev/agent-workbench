---
name: grilling
description: >
  Grill the user relentlessly about a plan, decision, or idea. Use when the user
  wants to stress-test, deepen, or challenge their thinking, or uses any 'grill'
  trigger phrases.
---

Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Let focus follow the maturity of the material. With only an idea or a thin draft, explore broadly: surface alternative directions, hidden assumptions, concrete examples, and downstream consequences. As the proposal becomes more developed, concentrate increasingly on its chosen direction, internal consistency, unresolved decisions, and material risks. Reopen the option space when evidence exposes a genuine gap or the user asks to explore more widely.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled — the questions you can ask _now_ without guessing at answers you haven't heard yet. Begin each round by identifying the complete frontier. Present it in one batch when it remains readable; otherwise use consecutive batches under the completeness rule below. Number each question, give your recommended answer, and wait for the user's batch reply before continuing.

The frontier is a completeness boundary, not a question quota. It has no hard or default size. If a complete frontier would be too large for one readable response, divide it into consecutive batches: state what the known frontier contains, identify what this batch covers, and carry every remaining item forward with stable IDs. After each batch reply, revalidate the remaining items against the new answers, preserving every item that is still material. Do not omit, collapse, shorten, or silently defer a material decision merely to control response length. New branches discovered from an answer belong to a later round and should be identified as newly unblocked.

Each question should be formatted like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Give the user enough substance to decide without another round of basic clarification. As useful for the decision, include why it matters now; a concrete scenario, boundary, or failure example; genuinely different options; the recommended choice and its basis; and material effects on cost, risk, recovery, downstream behavior, or future compatibility. These are content requirements, not a fixed template. Do not manufacture options without a real difference, and do not reduce questions to one-line choices because a batch is large.

Each round the user answers reshapes the tree — settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it — don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report — ask the rest of the frontier now. The _decisions_ are the user's — put each to them and wait.

After each round, state a short **reply contract** so the user can answer by number, for example:

- 「全部采纳」
- 「除 Q3 外全部采纳」
- 「Q2 选 B；Q4 按你的推荐」
- 「展开 Q1」

Do not stop per-question waiting once the round is out; wait for one batch reply.

Treat existing choices with increasing weight as the material matures, without turning them into a cage. When a new answer conflicts with a confirmed direction or exposes a missing principle, explain the concrete trade-off and let the user decide whether to change the detailed choice or reopen the broader direction. Do not perform this check as a ritual when no material conflict exists.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.

## When the subject is a durable document

If the subject is a PRD, plan, Decision, Spec, MVP slice, or similar document:

1. **Use the document's maturity as guidance.** For a thin document, help develop the option space and make assumptions visible. For a mature document, use its established purpose, scope, non-goals, and accepted decisions as the center of gravity. If missing product context blocks a useful recommendation, draft the smallest necessary context from available evidence, mark assumptions, and ask the user to correct it rather than making them start from a blank page or creating a second PRD.

2. **Do not edit the target document mid-grill.** Keep accepted choices, non-goals, deferrals, and open items in working memory (or a temporary notes surface the user already uses). Stable IDs (`R2-Q1`) help when the user answers by number.

3. **Write back only after confirmation.** When the frontier is empty, present a consolidated decision summary. Apply accepted decisions to authorized target docs only if the invocation already authorized post-convergence writeback, or after one explicit final confirm. Classify each displaced meaning as keep in place, migrate to a named home, replaced by an accepted decision, or user-deprecated — never silently drop a product commitment because the new text is shorter.

4. **After writeback, report briefly:**
   - which documents changed
   - which decision groups were absorbed
   - what remains unresolved or deferred
   - which stages were intentionally not run (gates, release, implementation, etc.)
