---
name: session-handoff
description: Summarize the current session into a reusable handoff when the user asks to summarize this session, save context to disk, generate a handoff, migrate context into a new session, or整理当前进度/坑/后续. Use this whenever the user wants a session handoff artifact or wants context preserved before switching to a fresh conversation.
---

# Session Handoff

Create a durable handoff so a fresh conversation can continue with minimal re-discovery.

Two phases, kept separate:

1. Phase 1 (default deliverable): write one handoff markdown file, then return a continuation prompt in chat.
2. Phase 2 (optional, only on explicit request): a manual review of whether the session produced a reusable skill pattern.

Never fold Phase 2 content into the Phase 1 handoff.

## Example Triggers

Should trigger:

- `总结这个 session，把当前目标、完成状态、踩过的坑和后续动作落盘，我要切到新会话继续。`
- `帮我做一个 handoff，把当前上下文存到仓库里，然后给我一段能直接发到新 session 的提示词。`
- `把这次对话整理成 context handoff，我之后要在新会话继续 debug。`
- `先把当前进度和未验证项写成 handoff，再看看这次 session 有没有值得沉淀成 skill 的模式。`

Should NOT auto-route here:

- `帮我总结这份文档。`
- `把这个 bug 的根因写成 issue。`
- `帮我写一个新技能。`

## Phase 1: Write The Handoff

### Gather state from the live workspace, not memory

Conversation memory can be stale. Before drafting, inspect actual state:

- Run `git status`, `git branch --show-current`, and `git log --oneline -1`; compare with the trunk when integration is in scope.
- Record whether work is committed or only in the working tree, the branch, HEAD, and any divergence from trunk.
- Record the actual workspace/worktree where implementation should continue. The current shell cwd is not always the correct target.

The handoff must reflect verified state, not what you assume happened.

### Worktree-aware handoffs

If the task involves worktrees or branch integration, identify which typical case applies before recommending the next Git move. For an existing feature branch, protect dirty feature changes, rebase the feature branch onto the intended trunk, verify there, and only then consider merging back to trunk. For a task currently on trunk that should continue in another worktree/branch, ask whether strongly related untracked documents should be committed or copied into the new worktree so the context travels with the work.

For details and wording patterns, read [worktree-handoff.md](references/worktree-handoff.md) only when a worktree or branch-integration handoff is involved.

### Output location

Default: `docs/exchange/handoffs/handoff-<slug>-MMDDhhmm.md` under the current task's repo/worktree root (local time, 24-hour clock). Build `<slug>` from the workstream (2–5 hyphenated lowercase ASCII words, e.g. `lark-webhook-debug`), never a generic word like `session`. If the target name already exists, refine the slug or append seconds (`MMDDhhmmss`) instead of overwriting. Honor a user-specified destination if one is given.

### File structure

Write the file using the exact structure in [handoff-template.md](references/handoff-template.md). The template is the source of truth — do not restate or invent sections here.

Keep it high-signal: behavior-level changes over raw edit inventories, concrete paths/commands where they matter, and an explicit split between verified and assumed. Do not paste secrets, tokens, env values, or full logs.

## Continuation Prompt In Chat

After the file is written, return a continuation prompt directly in chat — never a second file — following [continuation-prompt-template.md](references/continuation-prompt-template.md). It must include the handoff path, current goal, current status, must-read files, the first recommended action, an instruction to verify state before continuing, and any open issues to confirm first.

Then offer one line: a skill-candidate review (Phase 2) is available on request.

## Phase 2: Optional Manual Review

Only on explicit user request after Phase 1. Follow [continuous-learning-review.md](references/continuous-learning-review.md) and produce the advisory review it specifies. Do not create, edit, or package any skill.

## Prohibited Behavior

- Skipping the file write.
- Writing the continuation prompt as a file instead of returning it in chat.
- Folding Phase 2 analysis into the handoff markdown.
- Auto-running continuous-learning extraction, or auto-creating/editing any skill.
- Claiming verification that did not happen, or blurring verified vs assumed state.
