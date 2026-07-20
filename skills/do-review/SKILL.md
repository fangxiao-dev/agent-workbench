---
name: do-review
description: Orchestrate independent leaf reviewer skills for PR/code review, N-round review, loop/until-converged review, custom reviewer selection, and closure verification. Requires subagents by default; stop and ask if they are unavailable.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Do Review

`do-review` is the sole review orchestrator. It fixes the complete review scope and comparison point, prepares shared context, plans capacity, dispatches leaf reviewers, owns the cross-track ledger, verifies P1/P2 evidence, classifies findings, controls loop convergence, and writes the final report. The main session is not another reviewer.

Every dispatched reviewer is a leaf reviewer. A leaf reviewer performs only its assigned skill's review role: it must not invoke `$do-review`, run its subagent gate, dispatch subagents, re-resolve reviewer topology, re-plan capacity, read another track's same-round findings, classify cross-track results, or decide the overall verdict.

The default topology comes only from [reviewer-registry.json](references/reviewer-registry.json): Track A `code-review`, Track B `standards-review`, and Track C `spec-review`. `safety-review` remains an opt-in reviewer, not a default track. Do not infer internal reviewer topology from a reviewer skill; every resolved reviewer is already one leaf.

## Step 0: Subagent Gate, Preflight, And Capacity

This skill requires subagents. If they are unavailable, disallowed, or need authorization, stop before reviewing and ask:

```text
This do-review skill requires subagents for every selected leaf reviewer. Subagents are currently unavailable or need authorization. Do you want me to stop, or explicitly authorize a named degraded single-session review?
```

Resolve the selected reviewer names through [reviewer-registry.json](references/reviewer-registry.json), then preflight every canonical path before reserving capacity or dispatching. The registry is the single source for the default topology and canonical paths.

```text
python <do-review-skill-dir>/scripts/verify-reviewer-skills.py --workbench-root <agent-workbench-root>
python <do-review-skill-dir>/scripts/verify-reviewer-skills.py --workbench-root <agent-workbench-root> --skills <selected-skill-1> <selected-skill-2> <selected-skill-3>
python <do-review-skill-dir>/scripts/verify-reviewer-skills.py --workbench-root <agent-workbench-root> --skill-path <custom-skill>=<absolute-skill-path>
```

For an explicit reviewer selection, resolve each name once through the registry or active skill catalog, pass every resolved registry name with `--skills`, and pass every catalog-resolved custom name/path with `--skill-path`. A path must exist, be readable, remain inside the workbench root, and have frontmatter whose `name` exactly matches the requested name. Fail before dispatch if any selection is ambiguous or invalid; never substitute a similarly named or removed skill.

Reserve one subagent slot for every selected leaf reviewer. Prefer concurrent dispatch. If capacity requires phases, schedule every selected reviewer with the same already-fixed context; phases change only start time. Do not omit a reviewer merely to preserve parallelism. A named degraded topology is valid only when the user explicitly authorizes its exact reviewer list.

Completion criterion: every selected reviewer has a verified canonical path and a capacity slot or safe phase; otherwise the run stops.

## Step 1: Fix Scope And Shared Context

Determine the target, mode, reviewer selection, complete change unit, immutable base SHA, immutable head SHA, diff range, and included commits once before dispatch. Review the complete requested change unit, not merely `HEAD^`: use a user-supplied base/PR base/branch/tag/issue set; for a plan or implementation package include the package's reachable commits; otherwise use the integration or PR merge base through head. Ask before dispatch if this cannot be determined reliably.

Prepare one immutable shared context for every selected reviewer:

```text
Review target:
Repo/worktree:
Mode and round/cap:
Comparison point input:
Resolved base SHA:
Resolved head SHA:
Diff command/range:
Included commits:
Scope source/package roots:
Known constraints and out of scope:
Repository standards sources:
Issue/Decision/Spec/Plan/DAG sources:
User classification policy:
Prior-round canonical ledger:
Assigned track label:
Assigned reviewer skill:
Assigned canonical SKILL.md path:
```

When the target is an Impl-Package, include its package root and relevant Decision, Spec, Plan, and DAG material as evidence only. `impl-package/dev-with-track` remains the lifecycle owner for applying findings and package gates.

Completion criterion: every selected reviewer receives the same complete diff, base SHA, head SHA, commit list, and comparison point.

## Step 2: Select Mode And Reviewers

Choose exactly one mode:

| Mode | Trigger | Stop rule |
| --- | --- | --- |
| N rounds | review / 审查 / code review / 重新审核 / `N轮审查` / `run N rounds` | exactly N rounds, default 1 |
| Loop | `loop模式`, `直到收敛`, `until converged` | convergence or cap, default 10 |
| Closure verification | `聚焦验证模式`, `是否真的关闭`, `只验证是否修完`, `verify closure` | all named findings verdicted |

In closure verification, do not hunt unrelated problems.

With no explicit reviewer names, read `default_tracks` from the registry in its configured order. Its current entries are Track A (`code-review`), Track B (`standards-review`), and Track C (`spec-review`). With explicit reviewer names, run exactly those names once in the user's stated order: do not duplicate one selection, auto-fill omitted defaults, or infer missing reviewers. Assign labels sequentially (`Track A`, `Track B`, `Track C`, then later letters only if the user explicitly provides more reviewers).

Completion criterion: the mode and every selected track label/name/path are fixed before dispatch.

## Step 3: Dispatch Independent Leaf Tracks

For each round, dispatch every selected reviewer as an independent leaf. Use [subagent-briefs.md](references/subagent-briefs.md) for the common context and one generic leaf brief, plus the closure brief when applicable. Include the exact preflight-verified absolute `SKILL.md` path.

Every normal-review prompt must include this contract:

```text
You are <Track label> using reviewer skill <skill-name>.
Read and use exactly this canonical reviewer skill: <absolute SKILL.md path>.
You are a leaf reviewer in a topology already resolved by the parent do-review run.
Do not invoke do-review. Do not dispatch subagents. Do not re-evaluate reviewer topology or capacity.
Perform only the review role defined by the assigned reviewer skill.
Review exactly the supplied complete diff and fixed comparison point.
Do not inspect, request, or use findings produced by other tracks in the current round.
If this round is executed in phases, treat other same-round track results as unavailable.
Return findings in the supplied ledger schema. Do not make the final cross-track classification or overall verdict.
```

All same-round tracks are isolated, including phased tracks. Do not deduplicate, classify, summarize, or inject one track's output into another track until every selected reviewer has finished the round. In round 1 provide no ledger. From round 2 onward provide only the prior round's canonical ledger, after main-session deduplication and required evidence verification; never provide raw reviewer output.

Completion criterion: every selected track has completed independently for the round, or the run is explicitly blocked.

## Step 4: Ledger, Verification, Classification, And Loop

Maintain one canonical ledger across all rounds:

```text
ID:
Title:
Severity: P0/P1/P2/P3
Classification: blocker / follow-up / backlog / no issue
Source: Track <label> (<skill>) / fused / main-session
Contributing sources:
Status: new / duplicate / refined / disputed / accepted / downgraded / fixed-verified
Evidence:
Issue class:
Impact:
Recommended action:
Related issue/PR:
Main-session decision:
```

Use these default source labels exactly: `Track A (code-review)`, `Track B (standards-review)`, and `Track C (spec-review)`. Deduplicate by the broken invariant or observable failure, not by path or reviewer. For one shared issue use `Source: fused` and retain every contributor in `Contributing sources`. `main-session` is a decision source, never a fourth reviewer.

Before reporting a P1, P2, or blocker, read its cited target-revision evidence, confirm the citation supports the claim and is in fixed scope, then apply the user's policy or the default classification. Mark insufficient evidence as `disputed`, `downgraded`, or `UNCERTAIN`; do not present it as a verified blocker.

Default classification: blocker risks business data, money, inventory, order/customer state, security, or runtime-visible product data; follow-up is real but non-blocking under stated release constraints; backlog is non-urgent cleanup or optional hardening; no issue is duplicate, fixed, out of scope, or unsupported.

For loop mode, converge only after the latest completed round adds no distinct blocker/follow-up issue class, or only duplicates/refinements remain. A PASS/no-finding result from one track never skips another selected track or proves overall convergence. A round is incomplete if any selected reviewer is missing, unless the user explicitly authorized that named degraded topology.

Completion criterion: every accepted finding has source attribution and main-session decision; every P1/P2/blocker has an evidence verification note; the stop reason is recorded.

## Step 5: Report

Read [output-templates.md](references/output-templates.md) and use the smallest matching template. Show every selected track's verdict separately. For the default topology, show:

```text
Track A (code-review): PASS / FAIL / UNCERTAIN
Track B (standards-review): PASS / FAIL / UNCERTAIN
Track C (spec-review): PASS / FAIL / UNCERTAIN
Overall: PASS / FAIL / UNCERTAIN
```

Aggregate fail-closed: any required `FAIL` makes Overall `FAIL`; otherwise any required `UNCERTAIN` makes Overall `UNCERTAIN`; Overall is `PASS` only when every required track passes. A passing track never offsets another track's failure, and finding count is not a vote.

## Guardrails

- Do not mutate code, issues, or git state unless the user explicitly asks.
- Do not create tracking issues unless the user asks.
- Do not broaden closure verification into new-problem hunting.
- Do not hide subagent unavailability or an incomplete/degraded topology.
- Only revise a reviewer's responsibility or topology when that reviewer's own skill definition changes.
