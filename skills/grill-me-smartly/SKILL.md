---
name: grill-me-smartly
description: >
  Review a plan with a Chinese Grill Ledger, a standing questioner subagent, and
  a local-fact answerer subagent. Use this when the user wants a relentless
  grill-me style review but also wants the agent to research local facts, record
  every question and answer, and summarize the choices already made on their
  behalf.
---

# Grill Me Smartly

Use this skill to stress-test a plan through a ledger-driven review loop.

The ledger is the source of truth. It records every question, every answer, all
converged decisions, unresolved user-intent questions, and the stop proof. The
top of the ledger is written in Chinese so the user can quickly see what the
agents decided, why, and what still needs their judgment.

## User Invocation

The user should only need a short request such as:

```text
用 grill-me-smartly 审 docs/plans/user-auth-migration.md。
```

Treat that as authorization to run the full workflow in this file: initialize or
load the Grill Ledger, use the Questioner and Answerer roles as needed, record
Chinese summaries, and stop only with proof. Do not require the user to restate
the internal role split, ledger mechanics, or subagent choreography.

## Review Then Apply

This skill has two separate phases:

1. **Review phase**: produce the full Chinese alignment document in the Grill
   Ledger. Do not edit the reviewed plan, spec, PRD, or source document during
   this phase.
2. **Apply phase**: update the reviewed document only after the user has read
   the alignment document and explicitly asks to apply it.

The Grill Ledger is the review deliverable. It should be complete enough for the
user to quickly understand all proposed choices, all questions asked and
answered, and all remaining user decisions before any target document changes.

## Roles

- **Main session**: scribe, judge, and user-intent gatekeeper. It is the only
  writer of the ledger and must write through `scripts/grill_ledger.py`.
- **Questioner subagent**: owns the decision tree. It only proposes the next
  highest-value question and explains why it matters now.
- **Answerer subagent**: answers only questions that can be resolved by local
  files, code, git history, docs, or available tools. It must not answer product
  intent, preference, or risk-tolerance questions.
- **Optional critic subagent**: after every five answered questions, or before
  stopping, checks whether important branches are missing or the review is
  converging too early.

Subagents do not edit the ledger directly. They return structured text to the
main session; the main session records it.

## Ledger Location

Ledgers live under the user's OS temporary directory, not the current
workspace:

```text
<os-temp>/codex-grill/grill-<slug>.md
```

The script defaults to that temp location. Do not create repo-local
`docs/exchange/grill/` ledgers and do not modify the target repository's
`.gitignore` for grill records.

Use a slug from the reviewed document basename when possible. If the review is
not anchored to a file and no obvious slug exists, ask the user for a short
slug.

`init` refuses to overwrite an existing ledger. If a ledger exists, use
`status` and continue from it.

## Ledger Commands

The commands may be run from the target repo root for convenience, but the
ledger still defaults to the OS temp directory:

```bash
python <skill>/scripts/grill_ledger.py init --topic <plan-or-topic> --slug <slug> --initiator <main-session-name>
python <skill>/scripts/grill_ledger.py status --slug <slug>
python <skill>/scripts/grill_ledger.py add-question --slug <slug> --author Questioner --branch <branch> --question <question> --why-now <reason> --recommended-default <default>
python <skill>/scripts/grill_ledger.py record-answer --slug <slug> --question Q1 --author Answerer --answer <answer> --evidence <evidence> --uncertainty <uncertainty> --needs-user true|false
python <skill>/scripts/grill_ledger.py converge --slug <slug> --question Q1 --line <decision> --rationale <why> --impact <impact>
python <skill>/scripts/grill_ledger.py need-user --slug <slug> --question Q1 --line <question-for-user>
python <skill>/scripts/grill_ledger.py end-turn --slug <slug>
python <skill>/scripts/grill_ledger.py stop --slug <slug> --proof <stop-proof>
```

Use PowerShell quoting rules when values contain spaces.

## Workflow

1. **Confirm the review target.**
   - Identify the plan, spec, PRD, or current conversation being reviewed.
   - Read the target enough to understand the design and likely decision tree.
   - Do not edit the target document while this review workflow is active.

2. **Initialize or load the ledger.**
   - If no ledger exists, run `init`.
   - If one exists, run `status` and read the Markdown file before continuing.
   - Treat the Chinese sections at the top as the current human-readable state,
     but use the script for all updates.

3. **Start or reuse the standing Questioner.**
   - Give it the plan snapshot and the current ledger summary.
   - Tell it to ask exactly one question at a time.
   - Tell it not to answer its own question.
   - Require this output:
     - branch name
     - exact question
     - why this question matters now
     - recommended default when evidence is sufficient
     - whether the question appears locally answerable

4. **Record the question.**
   - Use `add-question`.
   - Do not combine unrelated questions into one Q item.

5. **Answer locally when possible.**
   - If the question is locally answerable, send it to the Answerer.
   - The Answerer must return:
     - concise answer
     - evidence with files, commands, or inspected sources
     - uncertainty
     - whether user intent is required
   - Use `record-answer`.

6. **Converge or ask the real user.**
   - If local evidence resolves the decision, use `converge`.
   - The convergence line must be Chinese and say what choice was made.
   - Include why the choice is reasonable and what it changes.
   - If the answer depends on product intent, preference, risk tolerance, or an
     unavailable external fact, use `need-user` and ask the real user one
     concrete question.

7. **Continue the loop.**
   - Use `end-turn` after each completed question cycle.
   - If status remains `进行中`, send the updated ledger state back to the
     Questioner for the next question.
   - Do not stop after one answered question. A resolved question means the
     review advances to the next material branch.

8. **Run a critic pass when useful.**
   - After every five answered questions, before a final stop, or when the
     review feels too narrow, ask a fresh critic subagent to inspect the ledger.
   - The critic should identify missing branches, premature convergence,
     repeated questions, or places where user intent was mistaken for local
     fact.
   - Record any accepted critic point as a new question through `add-question`.

9. **Stop only with proof.**
   - A stop is valid only when the ledger shows one of:
     - all material branches are converged
     - remaining questions require the real user
     - further questions would duplicate already resolved decisions
   - Use `stop --proof` only after the Questioner or critic has provided the
     stop proof. Individual converged questions do not automatically end the
     whole review.
   - The final response must name the temp ledger path and summarize:
     - decisions already made
     - questions asked and answered
     - what still needs the user
   - Do not update the reviewed document in this response. Ask the user to
     inspect the alignment document and explicitly request application if they
     want the reviewed document changed.

10. **Apply only after user approval.**
    - When the user explicitly asks to apply the alignment, read the latest
      ledger and the target document.
    - Apply only the converged decisions and user-approved裁决.
    - Preserve unresolved items in the ledger or ask the user before changing
      the target document.

## Chinese Summary Requirements

The ledger's top sections are the user's fast-read surface:

- `已收敛决策摘要`: every choice the agents made on the user's behalf, with
  reason, impact, and evidence.
- `待用户裁决`: only decisions that require the real user's intent or risk
  tolerance.
- `问题与回答总览`: every question and answer status, so the user can audit the
  review.
- `停止证明`: why the automatic review may stop or why it must continue.

Keep these sections understandable without reading the full log.

## Question Quality Bar

Good questions:

- force one exact decision
- name the affected branch of the plan
- explain why the decision matters now
- include a recommended default when evidence supports one
- avoid facts discoverable from local files unless the Answerer is being asked
  to verify them

Bad questions:

- bundle unrelated decisions
- ask for information already recorded in the ledger
- ask the Answerer to infer user preference
- stop the review without a stop proof

## Common Mistakes

- Letting the main session own the decision tree again. The Questioner owns the
  tree; the main session records, judges, and asks the user when needed.
- Letting subagents write Markdown directly. The script owns ledger structure.
- Treating the first answer as the whole review. Continue until the stop proof
  is valid.
- Recording only the final decision. The tool must preserve all questions and
  answers for user auditability.
- Editing the reviewed document during the review phase. First produce the full
  alignment document, then wait for explicit user approval before applying it.
