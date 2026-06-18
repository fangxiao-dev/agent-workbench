# Handoff Common Errors

Use this reference when reviewing a handoff, debugging a failed session migration, or improving this skill. The main `SKILL.md` keeps only the top three errors so the primary workflow stays readable.

## Thread Selection

- User did not explicitly ask to inherit history, but the agent forked the old thread. Default is a clean `create_thread`.
- User explicitly asked to inherit history, but the agent created a clean thread.
- The agent treated `{ type: "same-directory" }` fork as a new worktree.
- Current host had `create_thread`, but the agent stopped after writing the continuation prompt. Default new-session handoff must call `create_thread` unless there is a clear blocker.
- The agent first followed the manual handoff branch, later discovered `create_thread`, and failed to return to the thread-creation branch.

## State Freshness

- The agent wrote the handoff before committing, causing the child to receive a stale HEAD. Commit must happen before handoff when a checkpoint commit is part of the flow.
- The agent claimed verification that did not actually happen, or mixed up verified facts with assumptions.
- The handoff relied on conversation memory instead of fresh `git status --short --branch`, `git log -1 --oneline`, and relevant project files.
- Runtime validation was counted even though the agent did not prove the server processes were serving the current workspace.

## Handoff Shape

- The agent created timestamped handoffs for every small gate, leaving multiple plausible continuation entries. Default is to refresh one rolling handoff.
- The agent told the child to “read history” without providing a current facts summary and clear Next Action.
- The agent copied task status but omitted explicit collaboration preferences, especially main session / new session / subagent / spec review / quality review boundaries.
- The agent pasted secrets, tokens, env values, or full logs into the handoff.

## Continuation Prompt

- The continuation prompt was too long and rewrote the handoff, plan, issue notes, PR body, or closure checklist.
- The continuation prompt was written into a second file. It should be returned in chat and used directly for `create_thread` / `fork_thread`.
- The prompt mirrored handoff facts such as Fresh State, Verified Gates, or External State. Facts live in the handoff; the prompt carries rules and indexes.
- The prompt did not make the child an orchestration runner.
- The prompt weakened the orchestration role, letting the main/new session do implementation, research, and verification directly instead of dispatching bounded tasks to agents and focusing on work slicing, assignment, and seaming.
- A completed implementation plan was handed off as “verify then wait for owner” instead of closure orchestration that prepares external actions but does not execute them without authorization.

## Child Session Flow

- The parent treated `create_thread` as blocking IPC and required the child to wait for parent ACK after its first visible update.
- The child treated First Progress Update as a final answer and stopped after reporting verified state / intent.
- The parent never checked the child’s first progress update when the host made that visible. A lightweight correction is allowed, but child progress must not depend on parent ACK.
