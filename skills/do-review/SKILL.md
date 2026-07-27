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

The canonical ledger is a Markdown artifact owned and updated by the main session. Create it in the user temp directory as `%TEMP%\\do-review\\<YYMMDDHHMM>-<slug>-<shortsha>.md` (the helper is `scripts/review_ledger.py`). Keep the same absolute path for every round and let leaf reviewers read it only. The ledger is an internal audit artifact, not repository/Git state or a default owner-facing deliverable.

Every dispatched reviewer is a leaf reviewer. A leaf reviewer performs its assigned skill's review role: it must not invoke `$do-review`, run its subagent gate, dispatch subagents, re-resolve reviewer topology, re-plan capacity, read another track's same-round findings, classify cross-track results, or decide the overall verdict. Reviewer roles state primary review intent and handoff direction, not exclusive capability boundaries; a leaf may surface an evidence-backed cross-domain candidate for the parent to attribute, deduplicate, and classify.

The default topology comes only from [reviewer-registry.json](references/reviewer-registry.json): Track A `code-review`, Track B `standards-review`, and Track C `spec-review`. `safety-review` remains an opt-in reviewer, not a default track. Do not infer internal reviewer topology from a reviewer skill; every resolved reviewer is already one leaf.

When the dispatcher can select a model, each review leaf uses one of two default profiles: `gpt-5.6-terra` with `reasoning_effort=high`, or `gpt-5.6-sol` with `reasoning_effort=high`. The orchestrating agent selects the suitable profile for each leaf from the review scope and risk; task, owner, host, or explicit capacity constraints override this default. Keep that selection independent of the reviewer topology: choosing a profile must not omit, merge, or weaken a selected review track.

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

`Loop` 模式的动态 track lifecycle 不改变 registry 中的已选 reviewer topology：所有 selected track 必须参加 Round 1；首次没有新增 accepted blocker/follow-up 的 track 仍须参加下一轮。主会话只可在该 track 连续两轮 clean 后将它标记为 `dormant`，后续只为 `active` 或被重新激活的 track 预留容量。`N rounds` 与 `Closure verification` 不使用此优化，仍要求每轮全部 selected track 完成。

Completion criterion: every selected reviewer has a verified canonical path and a capacity slot or safe phase; otherwise the run stops.

## Step 1: Fix Scope And Shared Context

Determine the target, mode, reviewer selection, complete change unit, immutable base SHA, immutable head SHA, diff range, and included commits once before dispatch. Review the complete requested change unit, not merely `HEAD^`: use a user-supplied base/PR base/branch/tag/issue set; for a plan or implementation package include the package's reachable commits; otherwise use the integration or PR merge base through head. Ask before dispatch if this cannot be determined reliably.

Before preparing context or reserving capacity, fail fast on the fixed range: resolve both references with `git rev-parse <base>^{commit}` and `git rev-parse <head>^{commit}`, pin the resulting SHAs, then inspect `git diff <base-sha>...<head-sha>` and the included commit list. An invalid reference or empty diff stops the review before any leaf dispatch; do not turn either condition into a reviewer evidence gap.

`do-review` owns Spec evidence discovery. Resolve and record sources in this order: (1) issue/PR references in the included commit messages and their complete tracker content under repository rules; (2) user-provided paths; (3) matching PRD/spec material in `docs/`, `specs/`, or `.scratch/` for the branch or feature; (4) relevant Impl-Package Decision, Spec, Plan, and DAG material. Record each searched source and its result, including explicit empty results. If no usable contract evidence is found, ask the user when a source can reasonably be supplied; if review must continue, record the evidence gap and still dispatch the default `spec-review` leaf. Only an explicit reviewer selection or a user-approved named degraded topology may omit Track C.

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
Spec source discovery record (searched sources and results):
Spec evidence gap / user confirmation, if any:
User classification policy:
User review-depth preference:
Prior-round canonical ledger:
Assigned track label:
Assigned reviewer skill:
Assigned canonical SKILL.md path:
```

Create the canonical ledger immediately after the base/head SHAs and review slug are fixed. Use `python scripts/review_ledger.py create` (or an equivalent temp-aware file operation) and record its absolute path in the shared context as `Canonical ledger artifact`. If the generated filename already exists, fail closed rather than overwriting it and start a new timestamped run. The main session must write the initial scope, source-discovery record, user classification policy, and round state before dispatch.

When the target is an Impl-Package, include its package root and relevant Decision, Spec, Plan, and DAG material as evidence only. `impl-package/dev-with-track` remains the lifecycle owner for applying findings and package gates.

Completion criterion: base/head are verified immutable commits, the diff is non-empty, Spec source discovery is recorded, and every selected reviewer receives the same complete diff, base SHA, head SHA, commit list, and comparison point.

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

### Loop Track Lifecycle

本节只适用于 `Loop` 模式。主会话在 canonical ledger 中为每个 selected track 维护 `active`、`probation` 或 `dormant` 状态及连续 clean 计数：

- 每个 selected track 从 `active`、计数 0 开始，并参加 Round 1。
- 一轮结束后，只有主会话完成候选去重、证据核验和分类后，才能判定该 track 是否 clean。clean 的定义是该 track 没有带来新的、distinct、已接受的 blocker 或 follow-up；duplicate、refinement、disputed、out-of-scope 和 backlog-only 不会重置计数。
- 第一次 clean 后标记为 `probation`，下一轮仍必须调度；连续第二次 clean 后标记为 `dormant`，该 loop 的后续轮次不再调度它。
- 新的已接受 blocker/follow-up 会把其来源 track 的计数重置为 0 并保持 `active`。如果其他 track 的新 finding 实质影响 dormant track 的审查职责、证据边界或可能修复面，主会话必须在下一轮重新激活该 track 并重置其计数。
- incomplete、timeout、PARTIAL、UNCERTAIN 或 evidence gap 绝不算 clean；它们保持 `active`。`dormant` 表示已完成两次独立 clean 审查，不表示 PASS、无需证据或永久移除。

收敛前，最后一轮不得有新的已接受 blocker/follow-up，且每个 selected track 必须是 `dormant`，除非该 track 因新 finding 被重新激活后尚未完成两次 clean。这样至少保留两轮独立审查，同时避免在静态 comparison point 上无限重复无发现的 track。

## Step 3: Dispatch Independent Leaf Tracks

For each round, dispatch every `active` selected reviewer as an independent leaf. In `N rounds` and `Closure verification`, every selected reviewer remains `active`; only `Loop` may mark a track `dormant` under the lifecycle rule above. Use [subagent-briefs.md](references/subagent-briefs.md) for the common context and one generic leaf brief, plus the closure brief when applicable. Include the exact preflight-verified absolute `SKILL.md` path.

Every normal-review prompt must include this contract:

```text
You are <Track label> using reviewer skill <skill-name>.
Read and use exactly this canonical reviewer skill: <absolute SKILL.md path>.
You are a leaf reviewer in a topology already resolved by the parent do-review run.
Do not invoke do-review. Do not dispatch subagents. Do not re-evaluate reviewer topology or capacity.
Perform only the review role defined by the assigned reviewer skill.
Treat that role as a primary review intent, not an exclusive capability boundary. You may return an evidence-backed cross-domain candidate and suggested handoff, but do not classify or deduplicate it.
Review exactly the supplied complete diff and fixed comparison point.
Do not inspect, request, or use findings produced by other tracks in the current round.
If this round is executed in phases, treat other same-round track results as unavailable.
Return findings naturally, with enough location, evidence, and failure-mode detail for the parent to record and verify them. Do not make the final cross-track classification or overall verdict.
```

The prompt must also include `Canonical ledger artifact: <absolute temp path>`. In round 1, reviewers may read the artifact's scope metadata but must treat the findings table as empty. From round 2 onward, they may read the prior-round canonical findings from that path; they must not edit, replace, classify, or append to it. If a reviewer cannot read the path, the parent may provide a read-only copy of the relevant section, but the temp artifact remains authoritative.

All same-round tracks are isolated, including phased tracks. Do not deduplicate, classify, summarize, or inject one track's output into another track until every selected reviewer has finished the round. In round 1 provide no ledger. From round 2 onward provide only the prior round's canonical review context, after main-session deduplication and required evidence verification; never provide raw reviewer output.

The canonical review context may remain concise, free-form Markdown; it is not a rigid wire schema and must not turn leaf reviewers into form-fillers. It must nevertheless preserve the semantic facts needed to avoid rediscovering or splitting an existing finding: the broken invariant or failure mode, the best evidence, the parent decision/status, and any boundary on what is already covered or remains open. Do not replace it with topic labels such as "storage issues" or "labeling concerns". When it is too large for a prompt, provide it through a readable context artifact rather than deleting those facts.

Start each review round with a fresh leaf-worker session. Resume a worker only to finish the same interrupted round; never carry a worker's raw session into a later round. A cancelled, timed-out, stalled, or max-turns worker is incomplete, not PASS, even if it emitted partial prose. Treat a worker that explicitly reports `PARTIAL` the same way: finish that round or mark it blocked; do not silently reinterpret it as PASS.

Completion criterion: every active track has completed independently for the round, or the run is explicitly blocked. A dormant Loop track is explicitly recorded in the canonical ledger and is not a missing reviewer or degraded topology.

## Step 4: Ledger, Verification, Classification, And Loop

A leaf result is a review candidate, not an accepted finding. The parent preserves reviewer freedom to surface any plausible risk, then decides whether the candidate is accepted, duplicate/refined, disputed, downgraded, or out of scope. This gate exists to distinguish a real new risk from a plausible architectural concern without suppressing either.

The parent maintains one canonical ledger across all rounds; the Markdown file at `Canonical ledger artifact` is authoritative, and this is the parent's record format, not a form that leaf reviewers must fill:

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

Before reporting a P1, P2, or blocker, read its cited target-revision evidence, confirm the citation supports the claim and is in fixed scope, then apply the user's policy or the default classification. For each candidate, establish whether the changed diff directly contains it, the changed behavior directly triggers it, or it is a pre-existing/baseline concern. Also establish the concrete failure mode and the relevant contract, acceptance criterion, or repository rule when one exists. Mark insufficient evidence as `disputed`, `downgraded`, `out of scope`, or `UNCERTAIN`; do not present it as a verified blocker.

Default classification: blocker risks business data, money, inventory, order/customer state, security, or runtime-visible product data; follow-up is real but non-blocking under stated release constraints; backlog is non-urgent cleanup or optional hardening; no issue is duplicate, fixed, out of scope, or unsupported.

For Loop mode, apply the track lifecycle above after every completed round. A genuinely new risk that survives parent verification is added to the canonical context, resets the relevant track lifecycle, and continues the loop. Converge only when the latest completed round adds no distinct **accepted** blocker/follow-up issue class and every selected track is `dormant`; duplicates, refinements, disputed, out-of-scope, and backlog-only candidates may still be recorded but do not by themselves continue the loop. A no-finding result never skips the required probation round: a track becomes dormant only after two consecutive parent-classified clean rounds. A round is incomplete if any active reviewer is missing or incomplete, unless the user explicitly authorized that named degraded topology.

Completion criterion: every accepted finding has source attribution and main-session decision; every P1/P2/blocker has an evidence verification note; the stop reason is recorded. Keep disputed and out-of-scope candidates visible separately so a later closure review can revisit them without treating them as merge gates.

After every round, wait for all selected tracks, deduplicate and verify candidates in the main session, then atomically rewrite the same temp ledger with the round verdicts, finding status, evidence, and convergence decision. Do not create a second ledger for a later round. A reviewer result is never authoritative until this main-session update is complete.

## Step 5: Report

Read [output-templates.md](references/output-templates.md) and use the smallest matching template. Default review output states the overall verdict, every selected track's verdict, material findings and next action. Ledger paths remain internal unless requested; track verdicts are review evidence, not an owner approval request or a request to decide reviewer topology. The final report states its stop reason without turning the review into an owner approval request.

Aggregate fail-closed: any required `FAIL` makes Overall `FAIL`; otherwise any required `UNCERTAIN` makes Overall `UNCERTAIN`; Overall is `PASS` only when every required track passes. A passing track never offsets another track's failure, and finding count is not a vote.

## Guardrails

- Do not mutate code, issues, or git state unless the user explicitly asks.
- Do not create tracking issues unless the user asks.
- Do not broaden closure verification into new-problem hunting.
- Do not hide subagent unavailability or an incomplete/degraded topology.
- Do not create, request, or infer owner approval. In a GO execution attempt, return findings to `dev-with-track` so it automatically repairs, verifies and evaluates the gate; a direct `$do-review` invocation stops at the review checkpoint.
- Only revise a reviewer's responsibility or topology when that reviewer's own skill definition changes.
