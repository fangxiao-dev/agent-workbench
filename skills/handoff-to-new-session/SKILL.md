---
name: handoff-to-new-session
description: Create a clean normal Codex Desktop thread for a task or ticket whose authoritative records are already complete, using create_thread and a compact continuation prompt that runs the child’s work in an existing implementation worktree, then verifies its HEAD and package anchors. Use whenever the user asks to hand off a finished checkpoint to a fresh new session, especially when the implementation worktree, HEAD, and task/package state must survive the switch. Do not use for a partial-work summary, a rolling handoff, an automatic multi-hop relay, or any request to fork conversation history.
compatibility: Requires Codex Desktop thread tools (create_thread and optionally wait_threads) plus local Git access.
---

# Handoff To New Session

Create a fresh normal Codex thread that explicitly uses a verified existing implementation worktree. The handoff is a compact, complete initial prompt, not a temporary handoff document and not a compressed conversation summary.

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

If the child cannot execute in the exact worktree, or anchors inside that worktree do not match, it must report `source worktree setup mismatch` and stop. It must not stop merely because it initially opened at the saved project's root or another inherited directory.

Use only three recovery anchors:

1. The absolute path of the existing implementation worktree.
2. Its full current Git HEAD.
3. The task package directory and the single Impl-Package entry point that owns the next action.

Do not put a project ID, branch name, or dirty-state fingerprint in the child prompt. Preserve existing uncommitted implementation without attempting to enumerate it or clean it.

## Parent Preflight

Perform these read-only checks before drafting or creating the child:

1. Resolve the user-supplied existing implementation worktree. It does not need to equal the parent thread `cwd`; the child will use it as the execution `workdir`.
2. In that worktree, read the full HEAD with `git rev-parse HEAD`.
3. Confirm the stated package directory and Impl-Package entry point exist. Read the package records needed to fill the prompt from those sources, not from chat memory.

If step 1, 2, or 3 cannot be confirmed, stop before `create_thread`. Report `source worktree setup mismatch` with the expected worktree and failed anchor. Do not create a child, copy files, cherry-pick, reset, checkout, rebuild changes, or choose another worktree automatically.

## Fill The Initial Prompt

Read [references/handoff-prompt-template.md](references/handoff-prompt-template.md) in full. The prompt is an **anchor card**, not a history dump: fill only its fields from verified records. It should normally stay within 16 bullets / roughly 900 Chinese characters. Do not add a second summary of plan, DAG, ticket ACs, historical evidence, test commands, file boundaries, or design decisions that the package already owns.

The resulting prompt must:

- Name the existing source implementation worktree and expected HEAD. State that first-turn checks and later task commands must execute with that path as `workdir`, then verify its anchors before continuing.
- State only the current attempt/status, the single next action, the one material proof already earned, and the remaining proof that prevents closure. Let the entry point recover all detail.
- Carry the recorded subagent mode in one line. For `default-long`, say that the main session is **only** responsible for scheduling, authorization/decision records, cross-Task seaming, shared verification, Ticket acceptance, claim audit, gate and final integration, while subagents should be used fully for non-overlapping bounded execution work. For `ordinary`, say that the main session may also execute small/tightly-coupled work and subagents may own bounded work. Preserve any recorded GO rule that lets the main session complete verification, review, claim audit and gate evaluation without a second confirmation; do not reproduce the entire prior authorization contract.
- Require that the child's first turn is only the stated working-directory, package-entry and HEAD checks. On a mismatch, it must stop without a repair attempt. On success, it must continue the stated next action, stopping only for an explicitly named input, authorization, or other blocker.
- Keep controlled inputs, credentials, customer data, and oracle artifacts out of Git, chat bodies, and repository temporary files.
- Use the package directory and Impl-Package entry point as the authority route. Do not copy concrete commands or parameters, design details, Task steps, file ownership/boundaries, test commands, or implementation instructions into the child prompt. Use literal `N/A` only for a truly inapplicable field.

## Create And Deliver

1. Create every child with the fixed default configuration `model=gpt-5.6-terra` and `thinking=xhigh`. This clean-session contract is explicit rather than inherited: do not attempt to inspect or infer the parent thread's configuration. An owner may override the pair only by naming a supported replacement configuration.
2. Confirm that the destination supports the selected pair. If the default pair, or an owner-specified replacement, is unsupported, stop and report `session configuration unavailable`; do not silently fall back to another model or reasoning effort.
3. Call `create_thread`; never call `fork_thread`. Pass `model=gpt-5.6-terra` and `thinking=xhigh` explicitly, or the supported owner override, together with the filled prompt unchanged as `prompt`. Normalize the tool result before branching: the desktop wrapper may return the creation payload as serialized JSON text rather than an object, so parse that text and extract `threadId` / `hostId` or `clientThreadId`; never infer a queued result from the wrapper shape alone.
4. Create a normal session with `target.environment = { type: "local" }`, without `startingState: { type: "working-tree" }`, a worktree snapshot option, a branch, or the source worktree as a creation-state target. Let the prompt bind the child to the verified existing implementation worktree.
5. Obtain the original session title from the thread manager before creation. Derive the title by adding `01` if it has no numeric suffix, or incrementing the existing suffix (`01` → `02`). `create_thread` has no title parameter, so after an immediate result with `threadId`, call `set_thread_title` with that exact derived title. Do not claim the naming step succeeded until that call succeeds.
6. If the tool returns a `threadId` and `hostId`, set the title first, then make one non-blocking `wait_threads` call with that exact pair and `timeoutMs: 0`. This may surface an immediately completed source-worktree report, but the child must not depend on a parent acknowledgement to continue.
7. A correct `local` creation should normally return `threadId`. If a `clientThreadId` is returned, do not poll it or claim naming succeeded; report the queued creation as incomplete delivery because no thread ID is available for `set_thread_title`.
8. In the final response, state whether delivery succeeded or stopped at an environment/title mismatch and emit `::created-thread{threadId="..."}` only after local creation and renaming both succeed. For an incomplete queued result, emit `::created-thread{clientThreadId="..."}` and explicitly state that the requested handoff has not yet met its no-worktree/naming contract. Do not write another handoff file.

## Child First-Turn Contract

The initial prompt must impose this exact sequence:

1. Run the first read-only checks with the exact existing source worktree named in the prompt as `workdir`. Do not compare the inherited startup directory with the target.
2. In that worktree, read the package entry directory and use the named Impl-Package entry point to select only the current records needed for restore.
3. In that worktree, confirm the current full HEAD equals the expected HEAD and required entry directory or documents exist.

If the source worktree cannot be used as `workdir` or any in-worktree check fails, report `source worktree setup mismatch` and stop. If all checks pass, use the named Impl-Package entry point to continue its recorded `Next Action`. Do not stop merely to ask for a second confirmation.

## Final Check

Before reporting delivery, verify that:

- The stated implementation worktree, HEAD and authority records were verified before creation.
- The child explicitly uses `gpt-5.6-terra` with `xhigh` reasoning effort, unless the owner supplied a supported explicit override.
- The `create_thread` target explicitly used `environment: { type: "local" }`; no result or UI reports a newly created worktree.
- The child title was derived from the source title and confirmed through `set_thread_title`, or delivery was reported incomplete.
- The prompt contains the three anchors, the target-`workdir` execution rule, package directory, Impl-Package entry point, current snapshot, mismatch rule, next action, selected subagent mode, and authorization/gate boundaries.
- The prompt remains an anchor card: it contains no duplicated plan/DAG/Ticket/history/test detail and stays within the template's compact limit unless a named authorization or blocker required the exception.
- No project ID, branch, dirty-state fingerprint, secret, or controlled input was copied into the prompt.
- The child was created as a normal session with `create_thread`, never as a worktree snapshot, or the process stopped before creation for a documented source mismatch.
