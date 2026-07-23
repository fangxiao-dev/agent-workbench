---
name: handoff-to-new-session
description: Create a clean new Codex Desktop thread for a task or ticket whose authoritative records are already complete, using create_thread and a fully filled continuation prompt. Use whenever the user asks to hand off a finished checkpoint to a fresh new session, especially when the implementation worktree, HEAD, and task/package entry documents must survive the switch. Do not use for a partial-work summary, a rolling handoff, an automatic multi-hop relay, or any request to fork conversation history.
compatibility: Requires Codex Desktop thread tools (list_projects, create_thread, and optionally wait_threads) plus local Git access.
---

# Handoff To New Session

Create a fresh Codex thread from a verified implementation worktree. The handoff is a complete initial prompt, not a temporary handoff document and not a compressed conversation summary.

## Scope

Use this skill only when all of these are true:

- The user wants a new, clean thread rather than inherited conversation history.
- A task or ticket reached a documented checkpoint and its package, issue, plan, or progress records are the current authority.
- The user identifies the implementation worktree that must be the source of the new thread's working-tree snapshot.
- The next action is known, even when it is blocked on named input or authorization.

Do not use this skill for a half-finished task that needs a rolling handoff, a general session summary, a fork, or a workflow that has no authoritative entry record yet. Route those requests to the appropriate handoff or planning workflow instead.

## Safety Model

`create_thread` with `startingState: working-tree` snapshots the current Codex thread checkout. A shell command run with another `workdir` does not rebind the Codex thread. Creating a child from the wrong checkout can silently produce a plausible but unusable worktree.

Use only three recovery anchors:

1. The absolute path of the parent implementation worktree.
2. Its full current Git HEAD.
3. The authoritative entry directory or document set and the purpose of each entry.

Do not put a project ID, branch name, or dirty-state fingerprint in the child prompt. Preserve existing uncommitted implementation without attempting to enumerate it or clean it.

## Parent Preflight

Perform these read-only checks before drafting or creating the child:

1. Resolve the user-supplied implementation worktree and compare it with the current Codex thread `cwd` from the environment context. They must be the same resolved path. Do not treat a shell `workdir` override as evidence.
2. In that worktree, read the full HEAD with `git rev-parse HEAD`.
3. Confirm every stated entry directory or document exists. Read the progress or package records needed to fill the prompt from those sources, not from chat memory.
4. If a package-level validation command is part of the task contract, use it in the child's first turn only when it is confirmed to be read-only: it must not modify the worktree or call an external system. Otherwise record `N/A — no read-only package validation command is defined` and leave that validation for the authorized Next Action.
5. Resolve the one saved Codex project that is bound to this verified current checkout with `list_projects`. A project that merely contains the same repository is insufficient. If there is no exact match or more than one plausible match, treat it as a mismatch; do not select one automatically. Keep its ID only for the tool call.

If step 1, 2, 3, or 5 cannot be confirmed, stop before `create_thread`. Report `source-thread/worktree mismatch` with the expected worktree and failed anchor. Do not create a child, copy files, cherry-pick, reset, checkout, rebuild changes, or choose another worktree automatically.

## Fill The Initial Prompt

Read [references/handoff-prompt-template.md](references/handoff-prompt-template.md) in full. Fill every placeholder from the verified records. Write `N/A` where a section genuinely does not apply; do not silently remove sections or abbreviate material facts.

The resulting prompt must:

- Name the source implementation worktree and expected HEAD. Explain that the child receives a new Codex-managed worktree, so its path may differ while its HEAD and authority records must match.
- State the task or ticket status, complete and incomplete work, verification evidence, external state, and the exact next action.
- Preserve explicit collaboration and execution-preflight authorization without converting one-time permission into standing permission.
- Require that the child's first turn is only the stated read-only checks. On a mismatch, it must stop without a repair attempt. On success, it must continue the stated next action, stopping only for an explicitly named input, authorization, or other blocker.
- Keep controlled inputs, credentials, customer data, and oracle artifacts out of Git, chat bodies, and repository temporary files.
- Carry every applicable fact from the stated authority into its matching template field. Do not use “见文件”, “同上”, “略”, or a link as a replacement for a fact; use literal `N/A` only for a truly inapplicable field.

## Create And Deliver

1. Call `create_thread`; never call `fork_thread` in this skill.
2. Use the resolved project target with `{ type: "worktree", startingState: { type: "working-tree" } }` and pass the filled prompt unchanged as `prompt`.
3. If the tool returns a `threadId` and `hostId`, make one non-blocking `wait_threads` call with that exact pair and `timeoutMs: 0`. This may surface an immediately completed setup-mismatch report, but the child must not depend on a parent acknowledgement to continue.
4. If the tool returns a queued `clientThreadId`, report the queued setup instead of polling an unavailable thread ID.
5. In the final response, state whether delivery succeeded or stopped at a mismatch and emit `::created-thread{threadId="..."}` for an immediate thread or `::created-thread{clientThreadId="..."}` for queued worktree setup. Do not write another handoff file.

## Child First-Turn Contract

The initial prompt must impose this exact sequence:

1. Read only the listed entry records.
2. Confirm the current full HEAD equals the expected HEAD.
3. Confirm the required entry directory or documents exist.
4. Run the listed package validation only when one is defined.
5. Inspect `git status --short` only to preserve existing work. It is informational, is never compared with parent output, and is never a mismatch condition; never clean, reset, checkout, copy, or reconstruct it.

If any check fails, report `new worktree setup mismatch` and stop. If all checks pass, continue the filled `Next Action`. Do not stop merely to ask for a second confirmation.

## Final Check

Before reporting delivery, verify that:

- The current thread was genuinely bound to the stated implementation worktree before creation.
- The prompt contains the three anchors, complete facts from the authoritative records, the child mismatch rule, the next action, and the authorization/collaboration boundaries.
- No project ID, branch, dirty-state fingerprint, secret, or controlled input was copied into the prompt.
- The child was created with `create_thread` or the process stopped before creation for a documented source mismatch.
