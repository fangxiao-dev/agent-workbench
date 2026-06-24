# Orchestrator Skill Decomposition Plan

**Goal:** Refactor `orchestrator` from a large all-in-one workflow into a thin coordination entrypoint plus focused composable skills. Migrate the useful WT-PM / `wt-dev` main-session recording pattern into the orchestration system without bringing back the full worktree task lifecycle.

**Working names:**

- `orchestrator`
- `orchestration-plan-rewriter`
- `orchestration-slice-designer`
- `orchestration-review-gate`
- `orchestration-ledger`

## Problem

`orchestrator` currently owns too many responsibilities:

- rewriting bulk implementation plans into orchestration parent plans
- decomposing work into issue slices
- evaluating slice size and risk
- drafting issue bodies
- running review gates
- coordinating user approval
- publishing/linking GitHub issues
- defining handoff checkpoints
- maintaining a temporary progress ledger

This makes the skill hard to evolve and hard to compose. A user may need only the parent-plan rewrite, only slice sizing, only review, or only durable session recording, but today those concerns are coupled inside one large skill.

At the same time, `wt-dev` has a useful main-session recording mechanism: the running session keeps durable records of findings, progress, blockers, and evidence so future sessions can resume without relying on chat context. That mechanism should be adapted for orchestration work, where the main session acts as scheduler / integrator / validator.

## Non-Goals

- Do not reintroduce the full WT-PM worktree lifecycle.
- Do not add `plans/todo_current.md` or `plans/workplans/<task_id>/` as Orchestrator state.
- Do not make local ledgers the durable execution source after GitHub issues are published.
- Do not duplicate `to-issues` publishing ownership.
- Do not duplicate `handoff-new-session` thread/session handoff protocol.
- Do not make `orchestrator` execute implementation issues directly.

## Target Architecture

### `orchestrator`

Thin routing and sequencing entrypoint.

Responsibilities:

- Confirm the input is an already-authored bulk implementation plan.
- Select the needed sub-skills.
- Preserve source-plan safety rules.
- Enforce the safe order: ground source -> decompose -> rewrite parent plan -> draft issue slices -> review -> user approval -> optional publish -> optional handoff.
- State which artifact is durable at each phase.

Non-responsibilities:

- Detailed rewrite rules.
- Detailed slice sizing rules.
- Reviewer prompt bodies.
- GitHub publishing mechanics beyond invoking the correct gate.
- Handoff protocol details.

### `orchestration-plan-rewriter`

Converts a bulk implementation plan into a scheduler-facing parent plan.

Owns:

- bulk-plan preservation before rewrite
- parent plan section shape
- removal of implementation-level detail
- parent-plan issue table shape before and after issue publication
- execution-mode header
- source context and guardrail sections

Does not own:

- issue decomposition
- GitHub publishing
- execution handoff

### `orchestration-slice-designer`

Designs candidate issue slices and classifies their execution risk.

Owns:

- decomposition worker prompt
- phase and dependency graph
- AFK / HITL classification
- ownership boundary
- size/risk signals
- sizing decision: keep, vertical split, tracer-bullet plus follow-ups, design gate, or escalate to user
- seam and integration-risk notes

This skill should extract the high-value slice sizing logic currently embedded inside `orchestrator`.

### `orchestration-review-gate`

Runs independent review before user approval or issue publication.

Owns:

- orchestration/spec reviewer
- issue-quality reviewer
- re-review loop after required corrections
- final approved / changes-requested result format

It should reuse the existing reviewer prompts from `skills/orchestrator/templates/decomposition-prompts.md`, but move them behind a focused skill boundary.

### `orchestration-ledger`

Defines the main-session recording contract for orchestration work.

Owns:

- ledger template
- update timing rules
- status vocabulary
- blocker vocabulary
- resume-before-decide rule
- relationship between ledger, parent plan, GitHub issues, and handoff

The ledger is orchestration state, not product documentation and not an implementation tracker.

### `to-issues`

Remains owner of:

- user quiz / approval loop
- approved breakdown publication
- issue body baseline
- dependency-order publication

The Orchestrator system may pass reviewed issue drafts into `to-issues`, plus orchestration-specific fields such as ownership boundary and verification.

### `handoff-new-session`

Remains owner of:

- durable rolling handoff
- continuation prompt
- Codex thread creation / fork behavior
- fresh workspace facts

The Orchestrator ledger can feed handoff facts, but does not replace handoff.

## Ledger Contract

Create or replace the current `progress-ledger.md` template with a more explicit `orchestration-ledger.md`.

Suggested path:

```text
skills/orchestrator/templates/orchestration-ledger.md
```

Suggested shape:

```markdown
# <Feature> Orchestration Ledger

This ledger is temporary orchestration state. It is not product documentation and is not the durable execution source.

## Status

| Field | Value |
| --- | --- |
| phase | grounded / decomposed / reviewed / approved / published / handoff-ready / blocked |
| source_plan | <path or URL> |
| parent_plan | <path or chat-only> |
| durable_execution_source | GitHub issues / drafts / none |
| updated_at | <timestamp> |

## Decisions

| Time | Decision | Reason | Source |
| --- | --- | --- | --- |

## Findings

| Time | Finding | Impact | Follow-up |
| --- | --- | --- | --- |

## Slices

| Slice | Status | Size/Risk | Blocked By | Durable ID | Notes |
| --- | --- | --- | --- | --- | --- |

## Review Results

| Time | Reviewer | Artifact | Result | Required Changes |
| --- | --- | --- | --- | --- |

## Gate Results

| Time | Gate | Result | Evidence | Follow-up |
| --- | --- | --- | --- | --- |

## Blockers

| Time | Status | Blocker | Needed From | Resolution |
| --- | --- | --- | --- | --- |

## Handoff

Workspace, branch, HEAD, dirty state, issue order, verified gates, unresolved risks, and next action.
```

Ledger rules:

- Write after each irreversible orchestration step:
  - source grounded
  - decomposition drafted
  - review completed
  - user approval received
  - issue publish/link completed
  - handoff prepared
- Record blockers before stopping.
- On resume, read the ledger before making new orchestration decisions.
- After GitHub issues are published, issue numbers become canonical IDs. Local slice IDs are secondary.
- If the user requests read-only work, keep the ledger in chat only and do not write files.

## Implementation Plan

### Task 1: Add The Ledger Contract

**Files:**

- Add: `skills/orchestrator/templates/orchestration-ledger.md`
- Modify: `skills/orchestrator/SKILL.md`

**Steps:**

1. Add the new ledger template.
2. Update `orchestrator` to reference `orchestration-ledger.md` instead of `progress-ledger.md`.
3. State that ledger is orchestration state, while parent plan and GitHub issues remain the durable execution source.
4. Add resume-before-decide behavior for cross-session orchestration.

**Acceptance criteria:**

- The ledger records status, decisions, findings, slices, review results, gate results, blockers, and handoff facts.
- `orchestrator` no longer treats the ledger as a handoff protocol replacement.

### Task 2: Extract `orchestration-slice-designer`

**Files:**

- Add: `skills/orchestration-slice-designer/SKILL.md`
- Add or move: `skills/orchestration-slice-designer/templates/decomposition-worker.md`
- Modify: `skills/orchestrator/SKILL.md`

**Steps:**

1. Move decomposition worker responsibilities out of `orchestrator`.
2. Preserve size/risk signals:
   - call-sites / modules touched
   - cross-cutting concern
   - design uncertainty
   - seam coupling
   - independent verifiability
3. Preserve sizing decisions:
   - keep
   - vertical split
   - tracer-bullet plus follow-ups
   - design / interface gate
   - escalate to user
4. Update `orchestrator` to invoke this skill for decomposition.

**Acceptance criteria:**

- Candidate slices always include dependency, ownership, AFK/HITL, size/risk, and sizing decision.
- Cross-cutting slices are not silently shipped as normal AFK issues.

### Task 3: Extract `orchestration-plan-rewriter`

**Files:**

- Add: `skills/orchestration-plan-rewriter/SKILL.md`
- Modify: `skills/orchestrator/SKILL.md`

**Steps:**

1. Move parent-plan rewrite rules out of `orchestrator`.
2. Keep source-plan preservation rules.
3. Keep parent-plan section rules.
4. Keep rules for removing implementation-level detail.
5. Keep published issue mapping rules.

**Acceptance criteria:**

- The new skill can rewrite a bulk plan without drafting or publishing issues.
- `orchestrator` becomes responsible only for calling the rewriter at the correct point.

### Task 4: Extract `orchestration-review-gate`

**Files:**

- Add: `skills/orchestration-review-gate/SKILL.md`
- Add or move reviewer templates from `skills/orchestrator/templates/decomposition-prompts.md`
- Modify: `skills/orchestrator/SKILL.md`

**Steps:**

1. Move orchestration/spec reviewer prompt into the review-gate skill.
2. Move issue-quality reviewer prompt into the review-gate skill.
3. Define review result shape: `APPROVED` or `CHANGES_REQUESTED`.
4. Define correction and re-review loop.

**Acceptance criteria:**

- User approval and GitHub publication remain blocked until review gate passes.
- Required corrections cannot be dismissed by the main session without re-review.

### Task 5: Re-Scope `orchestrator`

**Files:**

- Modify: `skills/orchestrator/SKILL.md`

**Steps:**

1. Reduce `orchestrator` to a high-level entrypoint.
2. Keep routing rules:
   - raw requirement -> `feature-impl-planing`
   - only issues -> `to-issues`
   - execute approved issues -> execution skill / project convention
3. Keep external side-effect guardrails.
4. Reference the new sub-skills in execution order.
5. Remove duplicated prompt bodies and detailed local rules now owned by sub-skills.

**Acceptance criteria:**

- `orchestrator/SKILL.md` is shorter and mostly describes orchestration sequencing.
- Detailed decomposition, rewrite, review, and ledger rules live in focused skills.

### Task 6: Update Documentation

**Files:**

- Modify: `README.md`
- Modify: relevant files under `docs/workbench-design/`

**Steps:**

1. Document Orchestrator as a composable planning system.
2. Document when to use each new skill.
3. Document that `orchestration-ledger` is a main-session state record, not a replacement for GitHub issues or handoff.

**Acceptance criteria:**

- User-facing docs no longer describe `orchestrator` as the owner of every step.
- Skill boundaries are understandable from docs without reading every skill file.

### Task 7: Validation

**Files:**

- Verify skills and docs only.

**Steps:**

1. Search for stale references to `progress-ledger.md`.
2. Search for old statements that say `orchestrator` directly owns reviewer prompts or issue publication details.
3. Check that every new skill has valid YAML frontmatter with `name` and trigger-focused `description`.
4. Run installer tests if installer-visible skill layout changes need validation:

```powershell
powershell -ExecutionPolicy Bypass -File tests/install.ps1
```

**Acceptance criteria:**

- No stale ledger references remain unless intentionally kept as aliases.
- New skills conform to `docs/workbench-design/02-skills-spec.md`.
- Installer tests pass if run.

## Open Questions

- Should `progress-ledger.md` remain as a backward-compatible alias or be deleted after migration?
- Should `orchestration-ledger` be its own user-invocable skill or only a required sub-skill of `orchestrator`?
- Should issue publication remain entirely inside `to-issues`, or should there be a thin `orchestration-publication-gate` wrapper for parent-plan link-back and checkpoint commit?
- Should the new skills live as siblings under `skills/`, or should they be references/templates under `skills/orchestrator/` until the boundaries stabilize?
