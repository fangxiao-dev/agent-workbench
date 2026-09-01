---
name: handoff-to-new-session
description: 当用户要把已有权威 checkpoint 交接到全新 Codex task，并继续使用既有 implementation worktree 时使用；负责创建 clean local task、核验恢复锚点并分阶段续接。
compatibility: Requires Codex Desktop thread tools (create_thread, set_thread_title, wait_threads, and send_message_to_thread), access to the current turn's request metadata, and local Git access.
---

# Handoff To New Session

把已有权威 checkpoint 交给新的普通 Codex task；不复制旧聊天、不创建 worktree snapshot，也不替 owning workflow 执行业务。

## Ownership

- 本 Skill 只拥有 session 创建、existing-worktree 锚定、模型与标题继承、两阶段 prompt、交付纠偏和理解回报审计。
- Ticket/State/Evidence/Gate 与 package 续跑由 `/impl-package:dev-with-track` 拥有；Topic、当前批次与 idle 由 `$dispatcher` 拥有；bounded worker 的 dependency、lane 与 lifecycle 由 `/impl-package:subagent-driven-development` 拥有。handoff 只传递 canonical `readyTickets`，不复述这些流程。
- downstream protocol 可以提供自己的 validation anchors 与 continuation；本 Skill 仍只负责通用创建和交付 gate。

使用前确认：Owner 要求新 task；已有可恢复 authority 与 active checkpoint；目标 implementation worktree 和下一状态可从 authority 判定。滚动中的无 checkpoint 工作改用普通 handoff，不使用本 Skill。

`context compaction is only an emergency fallback`；已有可恢复 checkpoint 时优先创建 clean local task。

## Preflight

1. 在用户指定的 existing implementation worktree 读取 full HEAD，并确认 package/context authority 与 entry point 存在。该路径是 child 所有命令的 `workdir`，不要求等于新 task 的初始 cwd。
2. 从 authority 读取 continuation 所需的最小当前事实。Ticket package 使用 canonical runtime/status 的 current attempt、状态、完整 `readyTickets`、checkpoint、授权与 blocker；checkpoint 文案不能收窄 `readyTickets`。非 Ticket workflow 使用其 recorded action。
3. 从 `nodeRepl.requestMeta["x-codex-turn-metadata"]` 读取当前 task 的 `model` 与 `reasoning_effort`；缺任一项时报告 `session configuration unavailable`，不猜测。
4. 用 `list_projects` 确认 local project id，用 thread manager 读取原 task 标题；无数字后缀加 `01`，已有后缀则递增。

worktree、HEAD 或 authority 不符时报告 `anchor FAIL: source worktree setup mismatch` 并停止。保留未提交内容，不 reset、checkout、clean、覆盖、复制或重建。

## Prompt Cards

完整读取 [references/handoff-prompt-template.md](references/handoff-prompt-template.md)，从已验证事实填充两张卡。两卡使用 plain prompt text，不加 `<codex_delegation>`；不复制 plan、Ticket AC、调度算法、测试命令、凭证或受控数据。

- Anchor card 只含 worktree、full HEAD、authority/entry 与必要的只读 validation anchors。child 必须在该 worktree 检查后报告 PASS/FAIL 并停止，不开始工作。
- Continuation card 只含 authority、checkpoint、状态/完整 `readyTickets` 或 recorded action、授权与 blocker；它指向 owning skills，不展开其执行方法。

## Create And Deliver

1. 调用 `create_thread`，显式传入当前 `model` 与 `thinking=reasoning_effort`；target 固定为 `{ type: "project", projectId, environment: { type: "local" } }`。不得用 `fork_thread`、worktree environment、startingState、branch 或 source snapshot。
2. 只有返回 `threadId` 时才继续；用 `set_thread_title` 确认递增后的标题。仅有 `clientThreadId` 时报告 incomplete delivery，不轮询或发送 continuation。
3. 用返回的 `threadId`/`hostId` 等待 anchor。只有标题已确认且 child 明确 anchor PASS，才发送 continuation；timeout 不是 PASS。
4. continuation 后每次 `wait_threads` 不超过 60 秒。审计 child commentary 是否正确复述 authority、完整 ready work、owning skills、授权/blocker 与停止条件。
5. receipt 对齐后保持静默并完成交付；缺失或偏差进入下方纠偏流程。

## Recoverable Deviations

当 parent 重新读取 authority 后确认 worktree、HEAD、entry、session config 与授权仍一致，自动修正 prompt path、Windows 路径格式、optional anchor、标题、wrapper 解析或 receipt wording，然后继续同一 child。只执行无副作用或 task-metadata 修正；每轮必须使用新证据并产生进展，不重复相同失败动作。

真实 worktree/HEAD/authority/config/authorization 不匹配、意外创建 worktree/snapshot，或已无可证明的进展时停止。anchor FAIL 的 child 当前轮仍停止，由 parent 修正后重新发送 anchor-only prompt。

## Completion

成功要求：normal local task、标题确认、anchor PASS、continuation 已发送、理解回报对齐。成功后报告 direct 或 corrected delivery，并输出 `::created-thread{threadId="..."}`；任何条件未满足都明确报告 incomplete，不写额外 handoff 文件。
