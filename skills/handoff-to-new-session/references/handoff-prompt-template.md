# Handoff Prompt Template

从权威记录填充两张紧凑卡片；它们只负责恢复和 session 交付，不复制 owning workflow。

## First-stage anchor prompt

```text
[TASK / PACKAGE] 的全新独立 local session；不继承旧会话历史。

所有检查与后续命令使用：
- worktree：[ABSOLUTE_WORKTREE_PATH]
- expected HEAD：[FULL_GIT_HEAD]
- authority / entry：[AUTHORITY_AND_ENTRY_POINT]
- validation anchors：[READ_ONLY_VALIDATION_ANCHORS_OR_N/A]

本轮只在上述 worktree 做只读 anchor 检查。任一不符：报告 `anchor FAIL: source worktree setup mismatch` 与实际值并停止。全部匹配：只报告 `anchor PASS` 与锚点值并停止；不要读取恢复记录或开始工作。
```

## Second-stage continuation prompt

仅在标题和 anchor PASS 均确认后发送。

需要 Handoff Notes 时，将占位符替换为用户或当前 agent 提供的 1–3 条已确认小坑，每条一行且只保留会影响本次 continuation 的内容；没有时删除整个 `## Handoff Notes` 章节。该章节不得复制 plan、Ticket AC、调度规则、测试命令、凭证或受控数据。

```text
Continuation 已就绪；从 authority / entry 恢复，不回溯旧聊天或重做已登记工作。

- authority / entry：[AUTHORITY_AND_ENTRY_POINT]
- checkpoint：[ACTIVE_CHECKPOINT]
- status / ready work：[CURRENT_STATUS_AND_CANONICAL_READY_TICKETS_OR_RECORDED_ACTION]
- authorization / blocker：[AUTHORIZATION_AND_NAMED_BLOCKERS]
- WIP：保护未提交内容，不 reset、checkout、clean、覆盖或重建
- external boundary：[ACTIONS_REQUIRING_SEPARATE_AUTHORIZATION]

## Handoff Notes
[OPTIONAL_HANDOFF_NOTES_OR_OMIT]

Ticket package 使用 `/impl-package:dev-with-track` 恢复并持续执行 owning workflow；由 `$dispatcher` 调度，由 `/impl-package:subagent-driven-development` 约束 bounded worker。非 Ticket workflow 按 authority 指定的 recorded action 执行。直到 owning workflow 返回 terminal、blocker、idle/checkpoint，或确需换 session 时再停止。

收到后先用一条简洁 commentary 回报 authority、完整 ready work、所用 owning skills、授权/blocker 与停止条件；这是理解回报，不是执行预演，也不等待批准。随后立即从 entry point 恢复并执行。
```
