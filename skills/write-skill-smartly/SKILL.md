---
name: write-skill-smartly
description: Create or revise skills with a creator loop that uses writing-great-skills as the quality bar.
disable-model-invocation: true
---

# Write Skill Smartly

Use this skill when the user explicitly invokes `write-skill-smartly` to create,
fork, or improve a skill. Treat the invocation as authorization to produce the
skill artifact once intent is clear enough; do not stop at advice or a static
review unless the user asks only for review.

This is a creator skill. Its loop is:

1. understand the skill the user wants
2. inspect the local skill ecosystem
3. create or revise the skill files
4. try realistic usage prompts
5. improve the draft until it is usable

Use `writing-great-skills` as the quality bar inside that loop. Its concepts
shape what you write; they are not the deliverable.

## Source Policy

- Do not edit vendored third-party skills by default.
- If the target behavior is based on a third-party skill, create a local
  wrapper, fork, or companion skill unless the user explicitly asks to patch the
  vendored copy.
- Do not register local or self-created skills in `registry/third-party-skills.md`.
- If the new skill intentionally depends on another skill, name that dependency
  in its body and explain when to read or invoke it.

## Creator Modes

Choose exactly one mode before editing:

- **New skill**: create `skills/<name>/SKILL.md`, plus resources only when they
  remove repeated work.
- **Local revision**: edit an existing non-third-party skill in place.
- **Local fork**: copy the useful behavior of an existing skill into a new local
  skill with a new name and contract.
- **Third-party companion**: create a new local skill that wraps, narrows, or
  improves a vendored third-party skill without mutating the source copy.

Completion criterion: the target path, mode, and protected files are explicit.

## Creator Workflow

### 1. Ground The Request

Read the conversation and inspect the repository before asking questions. Find:

- whether the target skill already exists
- nearby skills with similar names, invocation patterns, or resource layout
- whether the likely source skill is local or third-party
- any examples, scripts, docs, or prior user corrections that define the desired
  behavior

Do not ask the user for facts that the repo can answer. Ask only for product
intent, risk tolerance, naming preference, or scope tradeoffs.

Completion criterion: you can state what will be created or changed, what will
be left untouched, and which remaining unknowns are true user choices.

### 2. Capture The Skill Contract

Before writing, extract or decide:

- **Job**: what the skill enables the agent to do.
- **Trigger**: user-invoked or model-invoked, and why.
- **Inputs**: prompts, files, tools, repo state, or external sources it expects.
- **Outputs**: files changed, reports produced, or final answer shape.
- **Boundaries**: what it must avoid, especially destructive or host-specific
  behavior.
- **Evidence**: how you will know the skill changes behavior.

Default local creator choices:

- use `disable-model-invocation: true` for experimental or personal skills
- keep v1 as a single `SKILL.md` unless branch-only reference or reusable
  scripts clearly earn their own files
- prefer creating a local companion over editing a vendored third-party skill

Completion criterion: a short contract exists in your working notes and no
high-impact user choice is still implicit.

### 3. Write The Artifact

Edit the skill files. For `SKILL.md`, build in this order:

1. frontmatter with stable `name`, concise `description`, and invocation mode
2. opening paragraph that says what the skill creates or changes
3. workflow steps that tell the agent what to do, not just what to check
4. completion criteria for each material step
5. resource pointers only when a branch needs more detail
6. output contract for the final user response

Use imperative instructions. Give the model reasons where they affect behavior.
Avoid copying long source-skill passages; extract the process and write the new
skill in its own voice.

Completion criterion: the requested skill exists or is revised on disk, and a
future agent can use it without inventing the main workflow.

### 4. Shape With `writing-great-skills`

If `writing-great-skills` is available and not already loaded in the current
turn, read its `SKILL.md` before this editing pass. Read its glossary only when
you need the precise meaning of a term to make a writing decision.

While drafting, apply these writing decisions:

- **Invocation**: pay context load only when the agent must discover the skill
  without the user naming it.
- **Description**: for model-invoked skills, write distinct trigger branches;
  for user-invoked skills, keep the description human-facing and compact.
- **Information hierarchy**: keep required steps in `SKILL.md`; push branch-only
  reference behind a clear pointer or omit it.
- **Completion criteria**: make each step's done state observable.
- **Single source of truth**: define each behavior once.
- **Leading words**: use compact familiar terms when they collapse repeated
  explanations.
- **Pruning**: delete sentences that do not change what the future agent does.
- **Failure modes**: revise places that invite premature completion,
  duplication, sediment, sprawl, or no-ops.

This is an editing pass on the artifact, not a separate report unless the user
asked for a critique.

Completion criterion: every retained section affects future execution, and any
remaining weakness is intentionally deferred.

### 5. Try The Skill

Do not finish a nontrivial creator run without trying the draft against realistic
use. Pick the lightest useful verification:

- **Dry run** for small or subjective skills: write 2-3 realistic prompts and
  reason through whether the new skill would drive the intended behavior.
- **Subagent trial** when the environment supports it and the prompt can be
  scoped: ask a subagent to use the new skill on one bounded task or to review
  whether it behaves like a creator rather than a checklist.
- **Formal eval loop** only when outputs are objectively gradable, two versions
  are competing, or the user asks for benchmark evidence. In that case, use the
  `skill-creator` eval/viewer flow instead of inventing a custom harness. Read
  `skill-creator` before entering that formal loop unless its instructions are
  already loaded in the current turn.

Use what the trial reveals to revise the skill before returning.

Completion criterion: at least one realistic use scenario has been checked, or
you clearly state why verification was skipped.

## Output Contract

After creating or revising the skill, return a compact summary with:

- path of each skill file created or changed
- creator mode used
- invocation mode chosen
- behavior the skill now drives
- verification performed and what it found
- any user decision still needed

The durable deliverable is the skill artifact, not a long review memo.
