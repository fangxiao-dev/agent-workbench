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

- continuation prompt 必须是短启动器：以 rolling handoff 的 Next Action 为准，把 child 设为 orchestration runner。plan 已完成本地实现时，mission 写 closure orchestration，但不要在 prompt 中展开完整 closure checklist / PR body / issue comment；这些由 child 从 handoff / plan 推导或写入 closure packet。禁止交接一个“验证后等待”的任务。
- continuation prompt 必须显式写出两条 owner 授权 / 运行条件，不能只放在 handoff 或本 rule 文件里：
  - 主 session / 新 session 关注调度和 seaming，尽量派用 subagent 执行单个任务。
  - 交接触发点：session context auto compact 了，或者自行识别到的大 gate。
- prompt 草稿与 handoff 一起过审核 gate（见 `rules/reviewer-input.md`）。
- `create_thread` 之后不要设计阻塞式 handshake。child 第一条可见更新必须是短 First Progress Update：说明会继续自动推进、会如何按 orchestration contract 使用 subagent（或当前阶段为什么不需要），然后在没有验证失败、blocker、或 owner stop 的情况下继续自动推进。
- 如果当前 host 能读取 child 回复并发送 follow-up，parent 可以做一次轻量纠偏；纠偏不应成为 child 继续工作的前置 ACK。需要可等待、可纠偏的阻塞协作时，使用 `multi_agent` worker/reviewer subagent，而不是新 Codex thread。
