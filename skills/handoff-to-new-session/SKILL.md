---
name: handoff-to-new-session
description: Create a clean normal Codex Desktop thread for a task or ticket whose authoritative records are already complete, using create_thread and a compact continuation prompt that names the existing implementation worktree, task package directory and Impl-Package entry point. Use whenever the user asks to hand off a finished checkpoint to a fresh new session, especially when the implementation worktree, HEAD, and task/package state must survive the switch. Do not use for a partial-work summary, a rolling handoff, an automatic multi-hop relay, or any request to fork conversation history.
compatibility: Requires Codex Desktop thread tools (create_thread and optionally wait_threads) plus local Git access.
---

# Handoff To New Session

Create a fresh normal Codex thread that explicitly uses a verified existing implementation worktree. The handoff is a compact, complete initial prompt, not a temporary handoff document and not a compressed conversation summary.

## Scope

Use this skill only when all of these are true:

- The user wants a new, clean thread rather than inherited conversation history.
- A task or ticket reached a documented checkpoint and its package, issue, plan, or progress records are the current authority.
- The user identifies the existing implementation worktree that the new session must use.
- The next action is known, even when it is blocked on named input or authorization.

Do not use this skill for a half-finished task that needs a rolling handoff, a general session summary, a fork, or a workflow that has no authoritative entry record yet. Route those requests to the appropriate handoff or planning workflow instead.

## Safety Model

Do not create a worktree child or snapshot any checkout. The new session starts normally and uses the exact existing implementation worktree named in the prompt. A shell command run with another `workdir` does not rebind the Codex thread; the prompt must therefore state the target working directory before its read-only checks.

Use only three recovery anchors:

1. The absolute path of the existing implementation worktree.
2. Its full current Git HEAD.
3. The task package directory and the single Impl-Package entry point that owns the next action.

Do not put a project ID, branch name, or dirty-state fingerprint in the child prompt. Preserve existing uncommitted implementation without attempting to enumerate it or clean it.

## Parent Preflight

Perform these read-only checks before drafting or creating the child:

1. Resolve the user-supplied existing implementation worktree. It does not need to equal the parent thread `cwd`; the new normal session will be explicitly directed to use this path.
2. In that worktree, read the full HEAD with `git rev-parse HEAD`.
3. Confirm the stated package directory and Impl-Package entry point exist. Read the package records needed to fill the prompt from those sources, not from chat memory.

If step 1, 2, or 3 cannot be confirmed, stop before `create_thread`. Report `source worktree setup mismatch` with the expected worktree and failed anchor. Do not create a child, copy files, cherry-pick, reset, checkout, rebuild changes, or choose another worktree automatically.

## Fill The Initial Prompt

Read [references/handoff-prompt-template.md](references/handoff-prompt-template.md) in full. Fill every placeholder from the verified records. Write `N/A` where a section genuinely does not apply; do not silently remove sections or abbreviate material facts.

The resulting prompt must:

- Name the existing source implementation worktree and expected HEAD. State that the normal session must use that path before running any command.
- State the task or ticket status, complete and incomplete work, verification evidence, external state, and the single entry point that owns the next action.
- Preserve explicit collaboration and execution-preflight authorization without converting one-time permission into standing permission.
- Require that the child's first turn is only the stated working-directory, package-entry and HEAD checks. On a mismatch, it must stop without a repair attempt. On success, it must continue the stated next action, stopping only for an explicitly named input, authorization, or other blocker.
- Keep controlled inputs, credentials, customer data, and oracle artifacts out of Git, chat bodies, and repository temporary files.
- Use the package directory and Impl-Package entry point as the authority route; do not enumerate every package file or restate a plan that is already authoritative on disk. Do not copy concrete commands or parameters, design details, Task steps, file ownership/boundaries, test commands, or implementation instructions into the child prompt; the entry point must recover them from the package. Carry only the current snapshot, verification, authorization and blocker facts needed to resume safely. Use literal `N/A` only for a truly inapplicable field.

## Create And Deliver

1. Create every child with the fixed default configuration `model=gpt-5.6-terra` and `thinking=xhigh`. This clean-session contract is explicit rather than inherited: do not attempt to inspect or infer the parent thread's configuration. An owner may override the pair only by naming a supported replacement configuration.
2. Confirm that the destination supports the selected pair. If the default pair, or an owner-specified replacement, is unsupported, stop and report `session configuration unavailable`; do not silently fall back to another model or reasoning effort.
3. Call `create_thread`; never call `fork_thread`. Pass `model=gpt-5.6-terra` and `thinking=xhigh` explicitly, or the supported owner override, together with the filled prompt unchanged as `prompt`.
4. Create a normal session without `startingState: { type: "working-tree" }`, without a worktree snapshot option, and without supplying the source worktree as a creation-state target. Follow the current desktop `create_thread` schema for its required project/environment wrapper, but let the prompt bind the child to the verified existing implementation worktree.
5. If the tool returns a `threadId` and `hostId`, make one non-blocking `wait_threads` call with that exact pair and `timeoutMs: 0`. This may surface an immediately completed source-worktree report, but the child must not depend on a parent acknowledgement to continue.
6. If the tool returns a queued `clientThreadId`, report the queued setup instead of polling an unavailable thread ID.
7. In the final response, state whether delivery succeeded or stopped at a mismatch and emit `::created-thread{threadId="..."}` for an immediate thread or `::created-thread{clientThreadId="..."}` for queued worktree setup. Do not write another handoff file.

## Child First-Turn Contract

The initial prompt must impose this exact sequence:

1. Before running commands, make the exact existing source worktree named in the prompt the session working directory.
2. Read the package entry directory and use the named Impl-Package entry point to select only the current records needed for restore.
3. Confirm the current full HEAD equals the expected HEAD.
4. Confirm the required entry directory or documents exist.

If the source worktree cannot be selected or any check fails, report `source worktree setup mismatch` and stop. If all checks pass, use the named Impl-Package entry point to continue its recorded `Next Action`. Do not stop merely to ask for a second confirmation.

## Final Check

Before reporting delivery, verify that:

- The stated implementation worktree, HEAD and authority records were verified before creation.
- The child explicitly uses `gpt-5.6-terra` with `xhigh` reasoning effort, unless the owner supplied a supported explicit override.
- The prompt contains the three anchors, the target-working-directory rule, package directory, Impl-Package entry point, current snapshot, mismatch rule, next action, and authorization/collaboration boundaries.
- No project ID, branch, dirty-state fingerprint, secret, or controlled input was copied into the prompt.
- The child was created as a normal session with `create_thread`, never as a worktree snapshot, or the process stopped before creation for a documented source mismatch.
