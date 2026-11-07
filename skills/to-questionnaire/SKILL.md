---
name: to-questionnaire
description: Turn what you can't settle alone into a questionnaire — discovery (ask for facts) or decision (confirm recommended defaults), as Markdown or interactive HTML.
disable-model-invocation: true
---

Turn something the user can't answer alone into a **questionnaire** for one person to fill in async, or fill out together over a meeting.

**Grill the send, not the subject.** Interview the user only about the _send_, which they can always answer: who it goes to, and what they need back. The questions in the document then target the **gap** between what the recipient knows and what the user needs.

1. **Who is it going to?** Ask, in one exchange, the recipient's role, expertise, and relationship to the user. This fixes the questionnaire's tone and how much context it must carry. Done when you know who the recipient is and what they know that the user doesn't.

2. **What must you be able to decide or know once the answers are back?** Ask, in one exchange, for the concrete decisions and facts — e.g. "how work is split between store managers and the owner", "how rehires are handled", "how many days before expiry a document reminder goes out" — not whether a reply is wanted. The list has two uses: it limits the questionnaire to the questions it needs, and after writing you check that every item on it is covered by a question. Done when you have that list.

3. **Pick the mode and the format.** Decide from steps 1–2, and say which you chose:
   - **Discovery** — the recipient holds facts the user lacks; questions are open. Always Markdown, using the template below.
   - **Decision** — the user can already propose a default and needs the recipient to confirm or correct it. Read [`references/decision-mode.md`](references/decision-mode.md): every question carries a stable ID mapped to its source item, the current situation, a recommendation, and the fixed choices; prune, order and close the loop as it says. Format: Markdown for a meeting or a short list; interactive HTML for a recipient filling in alone or a long list — read [`references/html-output.md`](references/html-output.md).
   - **Revising** an existing questionnaire on the same topic: read the "改版" section of `references/decision-mode.md` first; keep the original question IDs and, for HTML, the original `storeKey`.
   Done when mode and format are fixed and, for decision mode, every item from step 2 has a recommendation you would act on.

4. **Write the questionnaire.** Draft questions aimed at the gap. Markdown goes to `to-questionnaire-<slug>.md` in the current directory unless the project has a research folder for it; HTML follows `references/html-output.md`. Report the path. Done when the file exists and every item from step 2 is covered by a question or, in decision mode, recorded as a decided conclusion after pruning.

5. **Review from the recipient's seat.** Dispatch a fresh subagent with only the questionnaire and the recipient description from step 1; ask whether each question is understandable without outside context, compact, and something this recipient should be asked. Apply the findings and rerun the coverage check from step 4; if the fixes changed questions substantively, dispatch another fresh subagent for one more pass. Done when no finding is left unaddressed.

6. **Close the loop (decision mode).** When answers come back, use the question-ID ↔ source mapping produced before sending to write each answer back to its source item, as `references/decision-mode.md` describes. Done when every answered ID is reflected in the source documents.

## Document structure (Markdown)

Order questions most-important-first, since async means you may only get one pass, and group them under `##` headings by theme once there are more than a handful. In decision mode, use the per-question layout in `references/decision-mode.md` (ID in the heading, why, recommendation, four choices).

<questionnaire-template>

# <Questionnaire title>

**Purpose:** why this questionnaire exists and the decision riding on it.

**From:** <the user>, **To:** <the recipient>, **How your answers will be used:** <where they go>

## Context

One paragraph orienting a recipient who wasn't in the user's head. Enough to answer well, not a page.

## How to answer

Deadline and rough effort. Partial answers and "I don't know" are useful: flag anything you're unsure of rather than skipping it.

## <Theme heading>

One `##` section per theme. Under each, its questions, most-important-first. Every question is one idea, never compound, with an answer stub directly beneath, and a one-line _why this matters_ only where the question could be misread or invite a throwaway answer.

<question-example>
### What load is the system expected to handle at launch?

_Why this matters: it decides whether we provision for burst traffic now or defer it._

>
</question-example>

## Anything else?

A closing catch-all: anything we didn't ask that we should know?

</questionnaire-template>
