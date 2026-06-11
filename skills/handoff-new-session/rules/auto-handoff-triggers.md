# Auto Handoff Triggers

Use this rule for long-running workflows that need durable continuation across sessions.

## Required Triggers

Enter the durable handoff flow when either condition is true:

1. **A major quality gate has passed**
   - Examples: integration gate, adapter readiness gate, final backend gate, frontend gate, cutover gate.
   - Finish the checkpoint first: record verification results, commit related changes when appropriate, capture fresh git state, then write or refresh the handoff.
2. **Context auto-compaction happened**
   - If the conversation has been compacted or only a summary remains, do not rely on the summary alone.
   - Recover facts from the actual workspace first: `git status --short --branch`, `git log -1 --oneline`, and the relevant plan / handoff / progress files.
   - Then write or refresh the durable handoff before continuing or creating a new session.

## Gate Boundary

A major quality gate is a handoff-worthy phase boundary. It is not every unit test, typo fix, or small local iteration.

When unsure, prefer writing a handoff, but never invent verification, commits, external updates, or task status that did not actually happen.

## 触发后的产物要求

进入耐久交接 Checkpoint（见 `SKILL.md`）。自动交接额外要求：

- continuation prompt 的 mission 必须可执行：以 rolling handoff 的 Next Action 为准。plan 已完成本地实现时，mission 写成 closure orchestration（列出仍需 owner 授权的外部动作，准备但不执行 push/PR/issue/merge，向 owner 请求授权）；禁止交接一个“验证后等待”的任务。
- prompt 草稿与 handoff 一起过审核 gate（见 `rules/reviewer-input.md`）。
- `create_thread` 之后执行 handshake：读取 child 第一条回复，核对 First Reply Contract（verified state / interpreted objective / next action / proceed-or-wait-and-why）；不符纠正一次，读第二次回复后评价退出。
