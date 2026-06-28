# Discuss Ledger Role-Agent Review Skill Plan

## Goal

Design a skill that turns a plan, PRD, proposal, or technical design into a structured multi-agent review using Discuss Ledger.

The key design decision is to separate:

- **Role**: the review perspective, such as CEO, Architect, or QA.
- **AgentRuntime**: the execution backend, such as Claude Code or Codex.
- **Participant**: one concrete speaker in the discussion, computed as `Role x AgentRuntime`.

This means `Claude-CEO` and `Codex-CEO` are two different participants using the same role prompt but different runtime biases.

## Non-Goals

- Do not make a general chat-room simulator.
- Do not let every participant freely debate every point by default.
- Do not make gstack commands a runtime dependency.
- Do not replace `discuss-ledger`; this skill should orchestrate or guide it.
- Do not mutate source plans unless the user explicitly asks to apply conclusions.

## Proposed Skill

Suggested directory:

```text
skills/discuss-role-review/
  SKILL.md
  references/
    roles.md
    runtime-biases.md
    orchestration.md
    output-schema.md
    eval-prompts.md
```

Suggested frontmatter:

```yaml
---
name: discuss-role-review
description: Use this when the user wants a Discuss Ledger review with explicit roles and multiple agent backends, such as Claude-CEO plus Codex-CEO, Claude-Architect plus Codex-Architect, or wants multi-agent adversarial review of a PRD, plan, spec, technical design, or proposal. This skill designs and runs role x agent-runtime discussions, separates role prompts from runtime biases, deduplicates disagreements, and records only actionable unresolved points in Discuss Ledger.
---
```

## Core Model

```yaml
roles:
  ceo:
    label: CEO / Product Strategy Reviewer
    borrowed_from: gstack /plan-ceo-review
    focus:
      - user pain and business value
      - scope expansion, hold, or reduction
      - whether the proposal solves the real problem
      - whether the plan has a narrow validation wedge

  architect:
    label: Architecture Reviewer
    borrowed_from: gstack /plan-eng-review
    focus:
      - system boundaries
      - data flow
      - failure modes
      - performance and testability
      - implementation risk

  qa:
    label: QA / Acceptance Reviewer
    borrowed_from: gstack /qa-only
    focus:
      - acceptance paths
      - empty, error, permission, and edge states
      - regression tests
      - release blockers
```

```yaml
agent_runtimes:
  claude:
    strengths:
      - long-form product and document framing
      - hidden assumption discovery
      - user and stakeholder reasoning
      - narrative consistency

  codex:
    strengths:
      - codebase and implementation constraints
      - executable verification
      - test and tool awareness
      - engineering risk grounding
```

```yaml
participants:
  - id: claude-ceo
    role: ceo
    runtime: claude

  - id: codex-ceo
    role: ceo
    runtime: codex

  - id: claude-architect
    role: architect
    runtime: claude

  - id: codex-architect
    role: architect
    runtime: codex

  - id: claude-qa
    role: qa
    runtime: claude

  - id: codex-qa
    role: qa
    runtime: codex
```

## Participant Prompt Composition

Each participant prompt should be composed from three layers:

```text
base discussion rules
+ role prompt
+ runtime bias
```

Example:

```text
Claude-CEO =
Discuss Ledger review rules
+ CEO/Product Strategy role
+ Claude runtime bias
```

```text
Codex-CEO =
Discuss Ledger review rules
+ CEO/Product Strategy role
+ Codex runtime bias
```

The role prompt defines what counts as an important issue. The runtime bias defines how this participant is likely to find evidence and challenge assumptions.

## Default Orchestration

### Phase 1: Blind Role-Runtime Review

Run all participants independently. They should not see each other's outputs yet.

Each participant returns at most 2 disagreement candidates:

```yaml
candidate:
  title: concise issue title
  role: ceo | architect | qa
  participant: claude-ceo
  risk: what goes wrong if ignored
  evidence_or_missing_info: cited source text, repo evidence, or explicit missing information
  recommendation: concrete plan change
  falsifier: what evidence would prove this concern wrong
  confidence: high | medium | low
```

Rationale: blind review prevents the first participant from anchoring the others.

### Phase 2: Same-Role Confrontation

Pair participants with the same role:

```text
Claude-CEO <-> Codex-CEO
Claude-Architect <-> Codex-Architect
Claude-QA <-> Codex-QA
```

Each pair sees only the candidates from its own role and produces a role-level merged result:

- keep strong points
- merge duplicates
- drop weak or unsupported points
- add at most 1 new point triggered by the confrontation
- mark any internal disagreement that still matters

Output:

```yaml
role_result:
  role: ceo
  final_candidates:
    - title: ...
  internal_disagreements:
    - point: ...
      claude_position: ...
      codex_position: ...
      why_user_may_need_to_decide: ...
```

### Phase 3: Cross-Role Challenge

The orchestrator shows each role result to the other role groups.

Rules:

- CEO can challenge whether architecture or QA recommendations overcomplicate the product.
- Architect can challenge whether CEO scope expansion is technically disruptive.
- QA can challenge whether CEO or Architect claims are actually testable.
- Each role may add at most 1 cross-role challenge.

The goal is to make disagreements sharper, not to increase volume.

### Phase 4: Ledger Normalization

The orchestrator converts surviving candidates into Discuss Ledger points:

```text
D1: Business scope is not tied to a narrow validation wedge
D2: Proposed data migration lacks rollback and idempotency guarantees
D3: Acceptance criteria omit permission-denied and stale-session paths
```

Only write points that would change the plan, verification, release, or user decision-making.

### Phase 5: Response and Convergence

If there is an author, maintainer, or Plan Steward, ask them to respond to each open point:

- accept
- reject with evidence
- narrow the concern
- propose a compromise
- ask for user ruling

If no Plan Steward exists, the orchestrator can synthesize a neutral response only when the answer is directly supported by the source material.

### Phase 6: Targeted Follow-Up

Do not rerun all participants by default.

For each unresolved point, wake only relevant participants:

```text
business point -> Claude-CEO + Codex-CEO
architecture point -> Claude-Architect + Codex-Architect
QA point -> Claude-QA + Codex-QA
security point -> optional Security role participants
```

Stop when:

- all points converge
- a point has repeated without movement and should be marked deadlocked
- user ruling is needed

## Optional Roles

Add optional role pairs only when the source plan requires them.

```yaml
security:
  borrowed_from: gstack /cso
  trigger:
    - authentication
    - authorization
    - secrets
    - user data
    - external integrations
    - plugin or agent permissions

design:
  borrowed_from: gstack /plan-design-review
  trigger:
    - user interface
    - user workflow
    - information architecture
    - visual or interaction design

dx:
  borrowed_from: gstack /plan-devex-review
  trigger:
    - API
    - SDK
    - CLI
    - developer platform
    - technical documentation for developers

release:
  borrowed_from: gstack /ship, /land-and-deploy, /canary
  trigger:
    - production deployment
    - data migration
    - release sequencing
    - rollback or observability requirements
```

## Skill Body Outline

`SKILL.md` should include:

1. When to use this skill.
2. How to identify the review target.
3. How to choose roles.
4. How to construct participants from `Role x AgentRuntime`.
5. How to run blind review.
6. How to run same-role confrontation.
7. How to run cross-role challenge.
8. How to normalize points into Discuss Ledger.
9. How to stop discussion and summarize conclusions.

Keep concrete role definitions in `references/roles.md`.
Keep runtime-specific differences in `references/runtime-biases.md`.
Keep the phase algorithm in `references/orchestration.md`.

## Discuss Ledger Integration

This skill should call or instruct use of `discuss-ledger` rather than rewriting ledger mechanics.

Expected integration:

1. Read the target plan/spec/PRD.
2. Initialize or locate the ledger using the target basename as slug.
3. Use role-agent participants to produce candidate disagreements.
4. Convert only surviving points into ledger `add-point` entries.
5. Use `contest` and `converge` for follow-up rounds.
6. End the turn through the ledger tool/script.

The skill should preserve the core Discuss Ledger rule:

> Agreements go into convergence. Only live disagreements belong in the discussion log.

## Output Contract

The user-facing summary should include:

```md
## Review Setup

- Target:
- Roles:
- Participants:
- Rounds run:

## Converged Decisions

- ...

## Open Disagreements

- D1:
  - owner role:
  - current positions:
  - required user ruling or missing evidence:

## Recommended Plan Changes

- ...

## Discussion Quality

- strongest contribution:
- weak coverage:
- whether another round is useful:
```

## Cost Controls

Use strict caps:

- default roles: 3
- default runtimes per role: 2
- candidates per participant in blind review: 2
- new points per role in same-role confrontation: 1
- new points per role in cross-role challenge: 1
- maximum discussion rounds after ledger normalization: 2

This makes the default maximum manageable:

```text
3 roles x 2 runtimes = 6 participants
6 blind reviews x 2 candidates = up to 12 raw candidates
same-role merge -> target 2-3 points per role
ledger normalization -> target 3-6 final D points
```

## Evaluation Plan

Create 3 test prompts:

1. **PRD review**
   - User asks to review a product requirement document.
   - Expected: CEO pair surfaces business/scope issues, Architect pair avoids over-engineering, QA pair adds acceptance gaps.

2. **Technical plan review**
   - User asks to review a backend implementation plan.
   - Expected: Architect pair leads, QA pair adds testability and regression coverage, CEO pair comments only on scope/user value when relevant.

3. **UI workflow review**
   - User asks to review a user-facing workflow proposal.
   - Expected: default roles run, Design optional role is recommended or triggered, QA covers empty/error/loading states.

Suggested assertions:

- Output explicitly lists `Role x AgentRuntime` participants.
- Output separates blind review, same-role confrontation, cross-role challenge, and ledger normalization.
- Output caps participant candidates rather than allowing open-ended debate.
- Output creates Discuss Ledger-style disagreement points instead of full reports.
- Output recommends optional roles only when triggered by the target.

## Open Design Questions

1. Should the first implementation be an orchestration-only skill, or should it also include a script that generates participant prompts?
2. Should `Plan Steward` be a role, a runtime participant, or a mode of the orchestrator?
3. Should Claude/Codex runtime biases be fixed, or configurable per repository?
4. Should same-role confrontation happen before writing to Discuss Ledger, or should raw participant points be ledger entries immediately?
5. Should this live as a new skill or become a mode inside `skills/discuss-ledger`?

## Recommended MVP

Build this as a new skill first:

```text
skills/discuss-role-review/
```

Reason:

- It keeps the existing `discuss-ledger` stable.
- It lets the role-agent model evolve independently.
- If the workflow proves useful, it can later become a first-class mode in `discuss-ledger`.

MVP behavior:

1. Require a target PRD/plan/spec.
2. Use three roles: CEO, Architect, QA.
3. Use two runtimes when available: Claude and Codex.
4. Produce six participants:
   - Claude-CEO
   - Codex-CEO
   - Claude-Architect
   - Codex-Architect
   - Claude-QA
   - Codex-QA
5. Run blind review.
6. Run same-role confrontation.
7. Normalize into Discuss Ledger points.
8. Skip cross-role challenge in v1 unless the user asks for a deeper review.
