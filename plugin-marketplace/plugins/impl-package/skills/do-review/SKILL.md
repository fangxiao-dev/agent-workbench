---
name: do-review
description: Orchestrate independent leaf reviewer skills for PR/code review, N-round review, loop/until-converged review, custom reviewer selection, and closure verification. Uses Grok for finding closure and subagents for other phases.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Do Review

`do-review` is the sole orchestrator. It fixes one immutable ReviewRun, resolves topology and capacity, dispatches independent leaf reviewers, owns the review ledger, verifies and classifies candidates, controls convergence, and reports the result. The main session is not another reviewer.

Every dispatched reviewer is one leaf. It must not invoke `do-review`, dispatch subagents, re-evaluate topology/capacity, inspect other tracks' same-round output, classify cross-track results, or decide the overall verdict. A reviewer skill defines primary review intent, not an exclusive capability boundary; evidence-backed cross-domain candidates return to the parent for attribution and classification.

The default topology for `initial` and `terminal-final` comes only from [reviewer-registry.json](references/reviewer-registry.json): Track A `review-code`, Track B `review-code-by-standards`, and Track C `review-code-by-spec`. `safety-review` is conditional for those full reviews, not a registry default. `finding-closure` has one fresh independent `reviewer` invocation for all named findings; it does not split by registry track or launch a separate Safety leaf. The reviewer checks safety implications only when they belong to the named findings. Worker choice is independent of topology; the worker Skill owns its model and effort defaults. Other phases use the current host defaults for the caller-supplied target class, subject to explicit constraints.

## 0. Gate

This skill requires one independent worker for every selected leaf. If the required Grok process or subagent is unavailable or unauthorized, stop before ReviewRun creation and ask whether to stop or authorize an exact named degraded single-session reviewer list. Never infer degradation.

Load the registry. Do not reserve capacity until scope, phase, and topology are fixed.

## 1. Create One Immutable ReviewRun

Determine the complete change unit and reliable base/head refs. Review a supplied PR/package/branch range, including all reachable package commits when applicable, not merely `HEAD^`. Discover Spec evidence in order: tracker references from included commits; user paths; matching `docs/`, `specs/`, or `.scratch/` material; then Impl-Package Decision/Spec/Plan/DAG. Record searches and empty results. If no usable evidence exists, ask when reasonable; if continuing, record the gap and retain default Track C.

Create the ledger and fixed scope atomically, repeating `--source` for every path-based contract:

```text
python <do-review-skill-dir>/scripts/review_ledger.py create --repo-root <repo-root> --base <base-ref> --head <head-ref> [--source <contract-path>]... --slug <slug> --mode <mode> --round-cap <cap>
```

The command resolves commits, rejects an empty three-dot diff, and resolves each source as a readable UTF-8 Git blob at the resolved head before writing anything. Treat its JSON `ledger_path`, resolved SHAs, `diff_range`, and `contract_sources` (`path`, Git object ID, SHA-256) as the canonical ReviewRun. Any error stops before reviewer selection, capacity planning, or dispatch; retry with a new timestamp if the ledger name already exists.

Contract sources are immutable revision evidence. Reviewers read each only with `git show <resolved-head>:<path>`; never read it from the working tree and never perform a second hash/capture protocol. Tracker-only content stays in the discovery record rather than being invented as a repository path.

Prepare the common context defined in [subagent-briefs.md](references/subagent-briefs.md), including target, mode/round/cap, phase, resolved SHAs/range, included commits, constraints, standards, contract source records, Spec discovery/gap, Safety decision, user policy, prior canonical ledger, and assigned track/name/path. Every leaf receives the same ReviewRun. For Impl-Package targets, lifecycle and gates remain owned by `/impl-package:dev-with-track`.

## 2. Resolve Mode, Phase, Topology, And Capacity

Choose one mode: `N rounds` (default one), `Loop` (default cap ten), or `Closure verification` for named findings only. Then read [review-topology.md](references/review-topology.md): it is required for Safety admission, `initial`/`finding-closure`/`terminal-final` routing, final-HEAD rules, and Loop lifecycle.

Without explicit reviewers, use registry defaults in order and conditionally append `safety-review` for `initial` and `terminal-final`; use one `reviewer` leaf for `finding-closure`. An explicit reviewer selection for `finding-closure` must still resolve to exactly one leaf; explicit selections for other phases run exactly the stated list in order. Labels are sequential.

Resolve names through the registry or active catalog and verify canonical paths before dispatch:

```text
python <do-review-skill-dir>/scripts/verify-reviewer-skills.py --plugin-root <impl-package-plugin-root> --skills <registry-skills...>
python <do-review-skill-dir>/scripts/verify-reviewer-skills.py --plugin-root <impl-package-plugin-root> --skill-path <custom-name>=<absolute-skill-path>
```

Reject ambiguous, unreadable, escaping, or frontmatter-mismatched paths. Reserve one slot per selected leaf; prefer concurrency, or use safe phases with unchanged context. Capacity never removes a reviewer.

## 3. Dispatch Independent Rounds

Read [subagent-briefs.md](references/subagent-briefs.md) before composing prompts. Use its common block and generic leaf brief, plus its closure brief only for Closure verification and its anti-duplicate addendum only after round 1. Closure uses that brief once for the single independent reviewer; it does not compose one brief per review track. Include the verified absolute reviewer `SKILL.md` path and canonical ledger path.

Round 1 has no prior findings; later rounds receive only the parent-verified prior round's canonical context, never raw reviewer output. Start every round with fresh leaf workers; resume only an interrupted leaf from that same round. For `finding-closure`, run exactly one fresh reviewer leaf through `$grok-worker --no-subagents` in the background with the assigned reviewer skill and complete closure brief; the leaf returns PASS, FAIL, or UNCERTAIN for each named issue. After an incomplete Grok executor result, confirm process cleanup before one fresh fallback to the applicable current default reviewer. Timeout, cancellation, `PARTIAL`, or missing evidence is incomplete, not PASS.

Wait for all required active tracks. A recorded dormant Loop track is not missing; any other incomplete leaf blocks the round unless the user authorized that exact degraded topology.

## 4. Canonicalize The Round

After all leaves return, read [output-templates.md](references/output-templates.md) for the required ledger fields, evidence verification, deduplication key, finding classification, convergence, and atomic update rules. Leaf output is candidate evidence until the parent records its decision in the one canonical temp ledger; do not create per-round ledgers.

When the parent accepts and classifies a finding as Track C / Spec fidelity, regardless of which leaf first surfaced it, run the one-shot source recheck from [subagent-briefs.md](references/subagent-briefs.md) before handing the finding to implementation. Use one fresh independent `reviewer` leaf and limit it to the accepted finding plus the immutable Decision, Spec, subordinate `contract-design.md` when present at the fixed head, and directly referenced Ticket or cross-module authority. Record its result once on the accepted finding; downstream skills consume that record and do not dispatch a second recheck. A missing `contract-design.md` in an untouched legacy package is not by itself a contract gap. Record whether the current sources uniquely decide the behavior, require a contract revision, or leave an owner decision. An unavailable or incomplete reviewer blocks the implementation handoff instead of silently skipping the check. This is a post-classification check inside the current ReviewRun, not a new review phase or lifecycle state. Other accepted findings and unaccepted candidates do not trigger it.

For Loop, apply [review-topology.md](references/review-topology.md) after classification. Convergence requires no new accepted blocker/follow-up in the latest round and every selected track dormant. For `finding-closure`, the single reviewer verifies only named findings; it cannot stand in for `terminal-final`. A terminal result requires `terminal-final` on the final implementation `HEAD` with the complete applicable topology.

## 5. Report

Read [output-templates.md](references/output-templates.md) and use the smallest matching report. Show review phase, Safety applicability/coverage, every selected track verdict, material findings, stop reason, and next action. Ledger paths remain internal unless requested.

Aggregate fail-closed: any required `FAIL` makes Overall `FAIL`; otherwise any required `UNCERTAIN` makes Overall `UNCERTAIN`; PASS requires every required track. Applicable Safety omitted from an explicit `terminal-final` list makes coverage `INCOMPLETE` and cannot support Impl-Package terminal PASS.

## Guardrails

- Do not mutate code, issues, Git state, data, or external systems unless explicitly asked; do not create tracking issues by default.
- Do not broaden Closure verification into unrelated problem hunting or hide unavailable/incomplete topology.
- Do not create, request, or infer owner approval. A GO attempt returns findings to `/impl-package:dev-with-track`; direct invocation stops at the review checkpoint.
- Only revise reviewer responsibility or topology when that reviewer skill definition changes.
