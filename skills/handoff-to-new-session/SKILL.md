---
name: handoff-to-new-session
description: 当用户要把已有权威 checkpoint 交接到全新 Codex task，并继续使用既有 implementation worktree 时使用；负责创建 clean local task、核验恢复锚点并分两阶段续接。
compatibility: Requires Codex Desktop thread tools (create_thread, set_thread_title, wait_threads, and send_message_to_thread), access to the current turn's request metadata, and local Git access.
---

# Handoff To New Session

Create a fresh normal Codex thread that explicitly uses a verified existing implementation worktree. The handoff uses a compact anchor prompt followed by a compact continuation prompt; neither is a temporary handoff document or a compressed conversation summary.

## Scope

Use this skill only when all of these are true:

- The user wants a new, clean thread rather than inherited conversation history.
- A task or ticket reached a documented checkpoint and its package, issue, plan, or progress records are the current authority.
- The user identifies the existing implementation worktree in which the new session must run its commands.
- The next action is known, even when it is blocked on named input or authorization.

Do not use this skill for a half-finished task that needs a rolling handoff, a general session summary, a fork, or a workflow that has no authoritative entry record yet. Route those requests to the appropriate handoff or planning workflow instead.

## Safety Model

Do not create a worktree child or snapshot any checkout. The new session starts normally; its inherited initial directory is not an anchor and must never itself cause a mismatch. Every first-turn check and later task command must use the exact existing implementation worktree as its execution `workdir`; no thread-level cwd switch is required or assumed.

### Create-thread environment override

For this skill, the existing implementation worktree is an execution anchor **inside the child prompt**, not a thread-creation target. When `create_thread` is called for a Git project, explicitly set:

```text
target.environment = { type: "local" }
```

This rule overrides the generic `create_thread` advice to default Git projects to a new worktree. Never pass `target.environment.type = "worktree"`, `startingState`, a branch, or a source-worktree snapshot for this handoff. A UI/result that says `Worktree created` is a delivery failure: stop, report it, and do not treat the child as a valid clean-session handoff.

## Execution location before anchor verification

Treat the source worktree path as the child's execution location, not as a condition its inherited startup directory must already satisfy. The child's first action is to run the stated read-only checks with that exact path as `workdir`, then verify HEAD, package, and entry-point anchors there.

If the child cannot execute in the exact worktree, or anchors inside that worktree do not match, it must report `anchor FAIL: source worktree setup mismatch` and stop. It must not stop merely because it initially opened at the saved project's root or another inherited directory.

For an ordinary checkpoint handoff, use these three recovery anchors:

1. The absolute path of the existing implementation worktree.
2. Its full current Git HEAD.
3. The task package directory and the single Impl-Package entry point that owns the next action.

Do not put a project ID or dirty-state fingerprint in the child prompt. Preserve existing uncommitted implementation without attempting to enumerate it or clean it. A downstream protocol may add a small number of extra anchors, such as a branch, only when each one is required for admission and can be verified read-only in the target worktree; these are validation anchors, not new recovery authorities.

### Downstream protocol extension

A downstream protocol may reuse this skill's clean local-session delivery layer for a stateless child that has no package recovery authority. That protocol must provide both a complete second-stage continuation contract and the read-only context anchors needed for admission. In this branch, the first-stage authority block is replaced by those context anchors, the generic continuation card is replaced by the downstream continuation, and no context entry is treated as recovery authority. Creation, configuration, naming, PASS/FAIL gating, worktree safety and incomplete-delivery rules remain owned by this skill.

## Parent Preflight

Perform these read-only checks before drafting or creating the child:

1. Resolve the user-supplied existing implementation worktree. It does not need to equal the parent thread `cwd`; the child will use it as the execution `workdir`.
2. In that worktree, read the full HEAD with `git rev-parse HEAD`.
3. Confirm the stated package directory and Impl-Package entry point exist. For a downstream protocol extension, confirm its stated context anchors instead. Read records needed to fill the applicable continuation from its authority, not from chat memory.
4. Read the current task's `model` and `reasoning_effort` from `x-codex-turn-metadata` in the request metadata exposed to tool calls. When `node_repl` is available, inspect `nodeRepl.requestMeta["x-codex-turn-metadata"]`; do not infer either value from the system prompt, tool catalog, or a hard-coded default.

If step 1, 2, or 3 cannot be confirmed, stop before `create_thread`. Report `anchor FAIL: source worktree setup mismatch` with the expected worktree and failed anchor. If step 4 cannot be confirmed, stop before `create_thread` and report `session configuration unavailable`. Do not create a child, copy files, cherry-pick, reset, checkout, rebuild changes, choose another worktree, or substitute a guessed session configuration automatically.

## Fill The Two Prompts

Read [references/handoff-prompt-template.md](references/handoff-prompt-template.md) in full. Fill its first-stage anchor card and second-stage continuation card from verified records. Together they should normally stay within 16 bullets / roughly 900 Chinese characters. Do not add another summary of plan, DAG, ticket ACs, historical evidence, test commands, file boundaries, or design decisions that the package already owns.

The first-stage anchor prompt must:

- Name the existing source implementation worktree and expected HEAD. State that first-turn checks and later task commands must execute with that path as `workdir`.
- Contain only the ordinary recovery anchors, or the downstream protocol's context anchors, plus any explicitly required read-only validation anchors.
- Require that the child's first turn only checks those anchors. On mismatch it reports `anchor FAIL: source worktree setup mismatch` and stops without repair; on success it reports anchor PASS and stops without reading recovery records or starting work.

For an ordinary checkpoint handoff, the second-stage continuation prompt must:

- State only the current attempt/status, the single next action, the one material proof already earned, and the remaining proof that prevents closure. Let the entry point recover all detail.
- Carry the recorded subagent mode in one line and point to `/impl-package:subagent-driven-development` for its meaning; do not reproduce the mode contract. Preserve any recorded GO rule that lets the main session complete verification, review, claim audit and gate evaluation without a second confirmation; do not reproduce the entire prior authorization contract.
- Tell the child to recover through the package directory and Impl-Package entry point, then execute the recorded next action without another confirmation, stopping only for an explicitly named input, authorization, or other blocker.
- Keep controlled inputs, credentials, customer data, and oracle artifacts out of Git, chat bodies, and repository temporary files.
- Do not copy concrete commands or parameters, design details, Task steps, file ownership/boundaries, test commands, or implementation instructions into the prompt. Use literal `N/A` only for a truly inapplicable field.

A downstream protocol that supplies its own continuation must keep the same title-plus-anchor-PASS send gate, but its continuation authority, fields and start behavior come from that protocol rather than the generic continuation card.

## Create And Deliver

1. Default the child configuration to the current task's verified pair: pass its `model` unchanged as `model` and its `reasoning_effort` unchanged as `thinking`. An owner may override the inherited pair only by naming a supported replacement configuration.
2. Confirm that the destination supports the selected pair. If the inherited pair, or an owner-specified replacement, is unsupported, stop and report `session configuration unavailable`; do not silently fall back to another model or reasoning effort.
3. Call `create_thread`; never call `fork_thread`. Pass the selected `model` and `thinking` explicitly together with the filled first-stage prompt unchanged as `prompt`. Pass both prompts as plain prompt text: do not wrap either one in `<codex_delegation>` or add any Codex delegation tag or label. Normalize the tool result before branching: the desktop wrapper may return the creation payload as serialized JSON text rather than an object, so parse that text and extract `threadId` / `hostId` or `clientThreadId`; never infer a queued result from the wrapper shape alone.
4. Create a normal session with `target.environment = { type: "local" }`, without `startingState: { type: "working-tree" }`, a worktree snapshot option, a branch, or the source worktree as a creation-state target. Let the prompt bind the child to the verified existing implementation worktree.
5. Obtain the original session title from the thread manager before creation. Derive the title by adding `01` if it has no numeric suffix, or incrementing the existing suffix (`01` → `02`). `create_thread` has no title parameter, so after an immediate result with `threadId`, call `set_thread_title` with that exact derived title. Do not claim the naming step succeeded until that call succeeds.
   If `set_thread_title` fails, stop before waiting for anchors or sending continuation and report incomplete delivery.
6. If the tool returns a `threadId` and `hostId`, set the title first, then use `wait_threads` with that exact pair until the child reports anchor PASS/FAIL or needs attention. A timeout is not PASS. On FAIL, stop without sending the continuation prompt or attempting repair.
7. Only after both the title and anchor PASS are confirmed, send the filled second-stage continuation prompt to that exact `threadId`. The child may then recover through the authority entry and start the recorded next action without another confirmation.
8. A correct `local` creation should normally return `threadId`. If a `clientThreadId` is returned, do not poll it or claim naming succeeded; report the queued creation as incomplete delivery because no thread ID is available for `set_thread_title`.
9. In the final response, state whether delivery succeeded or stopped at an environment, title, anchor, or continuation mismatch. Emit `::created-thread{threadId="..."}` only after local creation, renaming, anchor PASS, and continuation delivery all succeed. For an incomplete queued result, emit `::created-thread{clientThreadId="..."}` and explicitly state that the requested handoff has not yet met its no-worktree/naming contract. Do not write another handoff file.

## Child First-Turn Contract

The initial prompt must impose this exact sequence:

1. Run the first read-only checks with the exact existing source worktree named in the prompt as `workdir`. Do not compare the inherited startup directory with the target.
2. In that worktree, confirm the current full HEAD equals the expected HEAD and the applicable recovery or downstream context anchors exist.
3. Verify any additional read-only anchors named by a downstream protocol.

If the source worktree cannot be used as `workdir` or any in-worktree check fails, report `anchor FAIL: source worktree setup mismatch` and stop. If all checks pass, report anchor PASS with the verified values and stop. Do not read recovery records or start implementation until the second-stage continuation prompt arrives.

## Final Check

Before reporting delivery, verify that:

- The stated implementation worktree, HEAD and authority records were verified before creation.
- The child explicitly uses the verified current-task model and reasoning effort, unless the owner supplied a supported explicit override.
- The first-stage and continuation prompts were sent as plain text without a Codex delegation tag or label.
- The `create_thread` target explicitly used `environment: { type: "local" }`; no result or UI reports a newly created worktree.
- The child title was derived from the source title and confirmed through `set_thread_title`, or delivery was reported incomplete.
- The first-stage prompt contains the applicable recovery or downstream context anchors, target-`workdir` execution rule, mismatch rule and PASS-then-stop rule; the second-stage prompt follows the applicable generic or downstream continuation contract.
- The two prompts contain no duplicated plan/DAG/Ticket/history/test detail and stay within the template's compact limit unless a named authorization or blocker required the exception.
- No project ID, dirty-state fingerprint, secret, or controlled input was copied into either prompt; any downstream validation anchor is read-only, necessary and minimal.
- The title and anchor PASS were confirmed before the continuation prompt was sent.
- The child was created as a normal session with `create_thread`, never as a worktree snapshot, or the process stopped before creation for a documented source mismatch.
