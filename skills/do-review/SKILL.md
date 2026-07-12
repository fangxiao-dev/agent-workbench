---
name: do-review
description: Orchestrate dual-track code review at reviewer-skill granularity, including each assigned skill's required internal reviewers. Use for PR/code review, N-round review, loop/until-converged review, custom review-skill orchestration, or verifying whether previous review issues were actually fixed. Requires subagents by default; stop and ask if they are unavailable.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Do Review

Run a **dual-track review at reviewer-skill granularity**: assign two reviewer skills to the same target, then execute each assigned skill's own workflow completely. A track is not synonymous with one subagent. For example, the default `module-review` track has independent Standards and Spec reviewers; both are required for that track.

The main session acts as scheduler, ledger owner, deduper, verifier, and final decision maker. It does not replace an assigned skill's required internal reviewers with its own opinion.

By default, Track A uses `code-review` and Track B uses `module-review`. If the user names custom reviewer skills, assign them through this skill's orchestration instead of changing the ledger, verification, or final-decision workflow.

The main session is not a third reviewer. It verifies high-severity evidence and decides classification.

## Step 0: Subagent Gate

This skill requires subagents. Capacity must be evaluated against the full reviewer topology, not just the two outer tracks.

If subagents are unavailable, disallowed, or need authorization, stop before reviewing and ask:

```text
This do-review skill requires subagents for the two review tracks. Subagents are currently unavailable or need authorization. Do you want me to stop, or explicitly authorize a degraded single-session review?
```

Before dispatch, read every assigned reviewer skill and determine its internal reviewer requirement. Reserve enough slots to execute every required reviewer role. If the runtime cannot host all roles simultaneously but can run them safely in phases, state the phase order and execute every required role; do not silently omit a child reviewer to preserve outer-track parallelism.

Completion criterion: every required reviewer role is available, scheduled in a safe phase order, or the user explicitly authorizes a named degraded topology. If neither is true, stop.

## Step 1: Scope

Determine the review target, mode, and reviewer tracks before spawning subagents.

Scope fields:

```text
Target:
Base/head or issue set:
Mode:
Rounds/cap:
Reviewer tracks:
Known constraints:
Out of scope:
Scope source / package roots / included commits:
```

### Commit-range resolution

Review the complete requested change unit, not merely the most recent commit.

- If the user names a base, PR base, branch, tag, or issue set, use it.
- If the request refers to a **plan package**, implementation package, handoff package, or a plan directory, locate the package root and include every reachable commit from the parent of the earliest package-related commit through the chosen head. Record the resulting base/head and included commits.
- Otherwise, for a branch/PR review, use the merge base with the repository's integration branch (or the PR base) through head; do not default to `HEAD^` merely because the user asked after a commit.
- If the package root or intended integration base cannot be determined reliably, ask before dispatch. Do not infer a one-commit range as a fallback.

Ask only if the target, mode, reviewer tracks, or complete change-unit range cannot be inferred from the prompt, repo, or issue/PR metadata.

Completion criterion: the target revision/issue set and mode are explicit enough that subagents can work independently without asking follow-up questions.

## Step 2: Select Mode

Choose exactly one mode.

| Mode | Trigger | Stop rule |
| --- | --- | --- |
| N rounds | review / 审查 / code review / 重新审核 / `N轮审查` / `run N rounds` | exactly N rounds, default N=1 |
| Loop | `loop模式`, `直到收敛`, `until converged` | convergence or cap, default cap 7 |
| Closure verification | `聚焦验证模式`, `是否真的关闭`, `只验证是否修完`, `verify closure` | all named issues/findings verdicted |

In closure verification mode, do not hunt for unrelated new problems.

Completion criterion: the selected mode and stop rule are written in the main session notes or response.

## Step 3: Select Reviewer Tracks

Choose exactly two outer reviewer-skill tracks before dispatch. These are skill assignments, not a cap on the total number of reviewer agents.

Default tracks:

```text
Track A: code-review
Track B: module-review
```

Custom reviewer selection uses name-list style from the user prompt, for example:

- `review skills: architecture-review, cso`
- `用 architecture-review 和 cso 做 review`
- `用 architecture-review 审查`

Assignment rules:

- No custom reviewer skill specified: use the default tracks.
- One custom reviewer skill specified: assign the same skill to Track A and Track B, and still spawn two independent subagents.
- Two custom reviewer skills specified: assign the first to Track A and the second to Track B.
- More than two reviewer skills specified: ask the user to choose exactly two.
- If a named reviewer skill cannot be found or read, stop and ask instead of silently falling back.

Track labels remain `Track A (<skill>)` and `Track B (<skill>)` even when both tracks use the same skill. Nested reviewer results retain their axis in the source label, for example `Track B (module-review/Standards)` and `Track B (module-review/Spec)`.

Completion criterion: Track A and Track B each have a concrete reviewer skill, or the run is blocked on an unreadable/ambiguous reviewer selection.

## Step 4: Dispatch Dual Tracks

Dispatch both outer tracks in every round, then let each assigned skill run its prescribed topology. Do not flatten a multi-reviewer skill into a single generic reviewer.

Default topology:

```text
Track A: code-review → one code-reviewer
Track B: module-review → Standards reviewer + Spec reviewer
```

When capacity is insufficient for all leaves at once, phase only the constrained child reviewers. Preserve independent evidence: for `module-review`, Standards and Spec must remain separate, even if one starts after the other. Report the phased topology and reason in the review summary.

For durable prompts, read only the needed sections from `references/subagent-briefs.md`: [Common Context Block](references/subagent-briefs.md#common-context-block) and [Generic Reviewer Track Brief](references/subagent-briefs.md#generic-reviewer-track-brief). When an assigned reviewer skill is `code-review` or `module-review`, append that skill's default lens addendum regardless of whether it came from the default track selection or a user-specified reviewer list. For closure verification, use [Closure Verification Brief](references/subagent-briefs.md#closure-verification-brief). From round 2 onward, append [Round-N Anti-Duplicate Addendum](references/subagent-briefs.md#round-n-anti-duplicate-addendum).

### Track Prompt Intent

Every normal-review track prompt includes:

```text
You are Track <A/B> using reviewer skill <skill-name>.
Use the assigned reviewer skill.
Review the target in scope.

Every finding needs evidence. Prefer file:line evidence where the target is code.
Avoid duplicates from the ledger unless you add materially new evidence or impact.
Return findings in the ledger schema.
```

For N-round mode with N > 1 and for loop mode, include the current ledger in every round after round 1.

Completion criterion: each round has a completed result from every required reviewer role in Track A and Track B, or the run is explicitly blocked by subagent availability/authorization.

## Step 5: Maintain The Ledger

Use one ledger across all rounds.

```text
ID:
Title:
Severity: P0/P1/P2/P3
Classification: blocker / follow-up / backlog / no issue
Source: Track A (<skill>) / Track B (<skill>/<axis>) / fused / main-session
Status: new / duplicate / refined / disputed / accepted / downgraded / fixed-verified
Evidence:
  - file:line
Issue class:
Impact:
Recommended action:
Related issue/PR:
Main-session decision:
```

Use source labels from the actual reviewer roles, for example `Track A (code-review)`, `Track B (module-review/Standards)`, `Track B (module-review/Spec)`, `fused`, or `main-session`.

Deduplicate by broken invariant or observable failure, not by file path. If both subagents report the same issue, mark `Source: fused` and keep the contributing track names in the evidence or decision note.

Completion criterion: every accepted finding has source attribution and a main-session decision.

## Step 6: Verify High-Severity Findings

Before reporting any P1/P2/blocker:

1. Read the cited code at the target revision.
2. Confirm the line exists and supports the claim.
3. Confirm the finding is in scope.
4. Classify using the user's policy if provided.

If evidence is incomplete, mark `disputed`, `downgraded`, or `UNCERTAIN`; do not present it as a verified blocker.

Completion criterion: all P1/P2/blocker findings have main-session verification notes.

## Step 7: Classify

Default policy when the user gives no policy:

- `blocker`: can corrupt future business data, money, inventory, order/customer state, security, or runtime-visible product data.
- `follow-up`: real risk, but not blocking under stated release constraints.
- `backlog`: old data cleanup, automation convenience, optional hardening, or environment governance without immediate business risk.
- `no issue`: duplicate, fixed, out of scope, or unsupported.

Closure verification verdicts:

- `PASS`: acceptance criteria satisfied.
- `FAIL`: acceptance criteria not satisfied.
- `UNCERTAIN`: evidence insufficient; state the missing check.

Completion criterion: every ledger item has exactly one classification or closure verdict.

## Step 8: Decide Whether To Continue

For loop mode, continue until convergence or cap.

Converged means the latest round adds no distinct blocker/follow-up issue class, or only duplicates/refinements remain. The main session decides convergence and records why.

Completion criterion: the final output states the number of rounds and why the run stopped.

## Output

For report templates, read only the relevant section from `references/output-templates.md`: [Normal Review Report](references/output-templates.md#normal-review-report), [Closure Verification Report](references/output-templates.md#closure-verification-report), [Finding Record](references/output-templates.md#finding-record), or [Round Ledger](references/output-templates.md#round-ledger). Treat that reference file as the output source of truth so template drift does not create competing report shapes.

## Guardrails

- Do not mutate code, issues, or git state unless the user explicitly asks.
- Do not create new issues unless the user asked for tracking updates.
- Do not broaden closure verification into new-problem hunting.
- Do not hide subagent unavailability.
- Do not let subagents decide final classification.
