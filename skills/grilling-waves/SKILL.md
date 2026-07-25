---
name: grilling-waves
description: Orchestrate the existing grilling skill as recommendation-led decision waves, anchored by an explicit upper-level product intent and followed by one consolidated writeback. Use whenever the user wants to grill, align, or refine a PRD, MVP, product decision, or spec in batches/waves instead of answering one question at a time, especially when avoiding overdesign matters.
---

# Grilling Waves

Use this skill as a thin orchestration layer over `grilling`. Do not restate or independently implement the interrogation method.

## Dependency

At the start, read and use [`../grilling/SKILL.md`](../grilling/SKILL.md). It remains the source of truth for question quality, recommendations, dependency traversal, and local-fact research.

This skill changes only the interaction unit and lifecycle:

- organize related grilling decisions into waves instead of presenting one question at a time;
- anchor every decision to an upper-level product context;
- recheck user changes against that context;
- defer target-document edits until the grilling is complete, then write back once.

If this file conflicts with `grilling` only about asking one question at a time, this skill's wave batching takes precedence. All other `grilling` rules remain in force.

## 1. Establish the upper-level context

Before starting waves, require both:

1. a basic PRD, plan, decision draft, or equivalent problem statement;
2. an upper-level product context explaining the enduring intent used to judge detailed choices.

The upper-level context is not a second PRD. Capture only the decision filter:

- target user and product value;
- why this work exists now;
- what the MVP must prove or unlock;
- what the MVP should deliberately avoid;
- which future compatibility matters without authorizing present-day implementation.

If the user did not provide this context, stop before grilling. Infer a short recommended draft from available evidence, label assumptions, and ask the user to confirm or edit it. Do not make the user author it from a blank page.

Once aligned, keep it compact and stable. Do not repeatedly reopen it unless a later choice exposes a real conflict or missing principle.

## 2. Plan and run waves

Ask `grilling` to explore the decision tree, but group tightly related decisions into a wave. Each wave should be small enough to review as one unit and should include recommended answers.

Choose wave themes dynamically. The following is an optional menu, not a required sequence or completeness checklist:

- user, value, scope, and non-goals;
- business facts and field authority;
- workflow, checkpoints, and state;
- rules, recommendations, and manual overrides;
- failures, blockers, and recovery boundaries;
- permissions, audit, and external responsibility;
- acceptance evidence and future extensions.

Skip irrelevant themes, combine small ones, split dense ones, and reorder them according to decision dependencies. Do not manufacture questions merely to fill the menu.

For each wave, present:

1. the wave topic and why it matters now;
2. a numbered set of related decisions;
3. the recommended choice for each decision and its concise rationale;
4. material MVP cost or future-compatibility implications;
5. an easy response contract, such as accepting the whole wave or changing selected item numbers.

Prefer a wave of roughly 3–7 decisions. Use fewer when the decisions are consequential or weakly coupled. Never hide a high-uncertainty choice inside a large batch.

## 3. Recheck modifications against context

After every user response, update the working decision ledger and compare changed choices with the upper-level context and prior accepted decisions.

Classify the result internally:

- **Aligned:** absorb it and continue.
- **Trade-off:** state the concrete cost briefly; continue if the user's choice is clear.
- **Context conflict:** stop and ask whether to revise the detailed choice or intentionally amend the upper-level context.
- **Context gap:** recommend a minimal addition to the upper-level context and ask whether to adopt it.

Only interrupt for a genuine conflict or gap. Do not turn the context check into repetitive ceremony. In particular, do not treat future compatibility as permission to build speculative abstractions or broaden the MVP.

When a question can be answered from code, documents, or other available evidence, follow `grilling` and research it instead of asking the user.

## 4. Converge before writing

During grilling, do not edit the target PRD, Decision, Spec, plan, or implementation documents. Maintain a working ledger containing:

- aligned upper-level context;
- accepted decisions and later amendments;
- explicit non-goals and deferrals;
- unresolved decisions;
- superseded meanings and their intended disposition.

Finish the waves when all material branches are resolved, intentionally deferred, or explicitly left open. Then present one compact consolidated ledger for confirmation.

If the original invocation already explicitly authorized writeback after convergence, proceed after showing the ledger. Otherwise request one final confirmation before mutating target documents.

## 5. Perform one consolidated writeback

Apply the accepted decisions to all authorized target documents together. Preserve the distinction between product intent, requirements, contracts, and implementation details.

Before deleting or weakening existing text, account for every affected meaning as one of:

- preserved in place;
- migrated to a named destination;
- superseded by an accepted decision;
- explicitly deprecated by the user.

Do not silently remove an older product promise merely because the new structure is shorter. Do not run approval gates, publish, bind revisions, implement code, or expand the mutation scope unless the user separately authorized those actions.

After writeback, report:

- which documents changed;
- which decision groups were absorbed;
- unresolved or deferred items;
- any stage that remains intentionally undone.

## Interaction principles

- Recommend confidently where evidence supports a default; make it easy to accept a whole wave.
- Keep MVP proportionality visible without repeatedly lecturing the user about it.
- Separate durable product context from changeable PRD detail.
- Use waves to reduce interaction overhead, not to reduce decision clarity.
- Preserve user amendments as authoritative unless they conflict with a higher-level constraint that the user has not chosen to change.
