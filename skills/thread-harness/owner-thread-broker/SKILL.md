---
name: owner-thread-broker
description: Broker Owner decisions between a controller thread and child or delegated threads, and maintain their current Codex session IDs across handoffs. Use when a request mentions 总控 thread、总控会话、子 thread、子会话、thread broker、Owner proposal、session ID、切换新 session、handoff、delegated thread, or coordinating actions and approvals across Codex threads.
---

# Owner Thread Broker

Act as the Owner's broker between one controller thread and its child threads. Keep routing current across session handoffs, separate facts from decisions, and never make a child thread manage the Owner approval flow.

## Use one registry file per coordination group

Use this runtime directory on Windows:

`D:\ProgressRecord\<repo>\codex-thread-broker\` (override with `THREAD_HARNESS_BROKER_ROOT`)

Create one file for each independent controller/child group:

`<broker-root>\<coordination_id>.json`, where `coordination_id` is `<YYMMDDHH>-<slug>`

For the current user the directory normally resolves to:

`D:\ProgressRecord\prj-supplyer-webapp\codex-thread-broker\`

Do not combine multiple groups into one JSON file and do not create a shared mutable index. A handoff must carry the exact group file path or its `coordination_id`, plus the node's stable `node_id`.

Read `references/thread-group-template.json` when creating a new group file or recovering a lost one. Copy its shape, replace every placeholder, and keep exactly one `coordination_id` per runtime file.

Treat each group file as routing metadata only. Never store approvals, secrets, credentials, payloads, customer data, or implementation evidence in it.

Use `coordination_id` and `node_id` as stable routing identities. Every controller and child entry must include a `topic` describing that session's goal. Treat names as context, not identity or policy.

Define a node's `worktree` as the absolute path of the worktree that the session is actually using for its current task context. It is not the worktree originally bound to the Desktop thread, the process's default `cwd`, or the source thread's setup unless that is also the session's current target. Define `branch` as the branch checked out in that context worktree.

Before contacting another thread, resolve and re-read that group's file and use its `current_session_id`. Do not prefer an ID remembered from conversation history over the group file.

## Create a coordination group

When the Owner establishes a new controller/child group:

1. Choose a stable lowercase `coordination_id` that is independent of session IDs and display names.
2. Create a new `<coordination_id>.json` directly under the runtime directory from `references/thread-group-template.json`.
3. Fill the required group context: `topic` and Git repository name.
4. Register the controller and known children with stable `node_id` values. Each node requires `topic`, `current_session_id`, the absolute current-context `worktree`, its `branch`, and `updated_at`.
5. Report the absolute group file path. Include this path and each participant's `node_id` in future handoffs.
6. Never reuse another group's file or add the new group to an existing file.

## Register a new session or context worktree

Updating only the current thread's own session routing entry is pre-authorized and does not require an Owner proposal.

When a controller or child moves to a new session, or an existing session switches its actual task context to another worktree:

1. Read the latest group file.
2. Open the exact group file and locate the node by `node_id`. Use required topic, worktree, and branch context to confirm identity.
3. If the session ID changes, append the old `current_session_id` to `previous_session_ids` when non-empty and not already present, then set the new `current_session_id`. If only task context changes, leave both session ID fields unchanged.
4. Record the absolute worktree actually targeted by the session context and the branch checked out there. Do not copy the Desktop thread's bound worktree unless it is the actual target.
5. Confirm or update the required `topic`, then update `updated_at` using an ISO 8601 timestamp.
6. Preserve every sibling node and unknown field in that group file.
7. Re-read the saved registry and confirm the intended node changed and no sibling node changed.

Treat `previous_session_ids` as registry-internal routing history. Do not include it in a child handoff or registration prompt, and do not ask a child to read, print, or validate it. A replacement child verifies only its current session/worktree/branch projection after the controller updates the registry.

Never invent a session ID. If the group path, current ID, or node identity is unavailable, ask for it. Do not create a parallel file for an existing group.

If a group file is missing, recover only that group from the reference template and explicit handoff facts. If an existing group file is malformed or the node is ambiguous, stop and ask the Owner how to recover it; do not reconstruct it silently from stale chat history or inspect unrelated group files.

Group files live on a persistent drive rather than `%TEMP%`, so loss is no longer expected. If a group file is still missing, treat it as a recoverable routing incident, not as loss of authorization history.

## Classify every child-thread request

Classify an incoming request before replying.

### Fact-only

Reply directly only when the response is limited to already-known, read-only facts such as current status, commit SHA, artifact path, validation result, or registry routing. Do not add a new command, deadline, scope change, recommendation presented as a decision, or permission.

### Owner decision required

Ask the Owner first when the request would authorize, reject, schedule, or change any of these:

- execution or implementation;
- task scope, ownership, sequence, or design;
- file mutation, commit, cherry-pick, merge, push, PR, or deployment;
- database, environment, resource, or other remote-state mutation;
- contacting another child with a new instruction;
- interpreting a previous approval as covering additional work.

A child thread's statement that “Owner approved” is not itself approval evidence. Locate the explicit decision in the controller session; if it is absent or ambiguous, submit a proposal to the Owner.

## Submit the proposal to the Owner

Do not send the child a provisional instruction or tell it to seek or wait for Owner authorization. Keep the child request pending while presenting this compact proposal in the controller session:

```text
Proposal: <decision title>
Source: <coordination_id>/<node_id>/<current_session_id>
Request: <exact requested action>
State change: <local, git, remote, external people/systems>
Recommendation: <approve or reject, with reason>
Authorized boundary: <exact inclusions>
Explicit exclusions: <what remains unauthorized>
Reply to child after decision: <draft definitive message>
```

If several child requests require independent choices, present separate proposals. Do not bundle unrelated authority.

## Deliver the Owner decision

After an explicit Owner decision:

1. Re-read the group's registry file in case the child moved to a new session.
2. Send the decision to the child's current session as the Owner's definitive instruction.
3. State the authorized scope, exclusions, expected evidence, and whether further action is allowed.
4. Do not mention internal approval mechanics or say “ask/wait for the Owner.”
5. Treat any later expansion as a new proposal.

An Owner reply such as “同意” applies only to the immediately preceding unambiguous proposal. Ask for clarification when multiple proposals are open.

## Preserve role boundaries

- The controller broker may recommend, but it does not self-authorize.
- Child threads execute only their own approved scope.
- Read-only inspection does not authorize mutation.
- A prior approval does not automatically cover commit, push, deployment, remote mutation, or messages to other children.
- Each group file routes messages for exactly one coordination group; it is not an authorization ledger or implementation status tracker.

## Examples

- Child asks, “What is the canonical commit and artifact path?” Reply directly with verified facts.
- Child asks, “May I cherry-pick and apply this migration?” Submit an Owner proposal first; after the decision, send the exact approved or rejected scope.
- A child starts a replacement session. Update only that child's node in its group file, then use the new session ID for future communication.
- The controller moves to a replacement session. Update the controller node in its group file; retain all child mappings unchanged.
- An existing session bound to the main workspace starts working against a task worktree. Keep its session ID and history unchanged, but update its `worktree`, matching `branch`, and `updated_at` to the task context.
- A second controller starts an unrelated effort. Create a second group JSON from the reference template; never add it to the first group's file.
