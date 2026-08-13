# Profile: solo

## 形状

- 一个 controller、一个 active task child、一个 worktree、一个 branch。
- `preflight` 对 active child 数量严格 fail-closed（必须恰好一个）；未通过该检查的 registry 不得进入 solo runtime。
- 普通单任务包直接使用 impl-package 时不加载 thread-harness；`solo` 只表示该单 task 已进入 broker coordination。
- task child 必须声明有效的绝对 `package_entry`，指向任务包 `progress.md`；adapter 只读取最小恢复事实。
- controller 每轮监控 task 的 H1、HEAD、Owner blocker、budget stage 与 handoff action。

## 每轮

1. 读取当前 task 的 `package_entry`、active checkpoint、`next_action` 与 `sync` action summary。
2. 按 [poll-contract.md](poll-contract.md) 对当前 task 执行固定 `120000` poll，再运行 `sync` 和 `stall-check`。
3. `budget_stage=handoff_due` 后，追加一次 `act --handoff --node <task> --source-session <current-controller-session> --reason "..."`。
4. controller 发送现有 `$handoff-to-new-session` 触发；task 完成当前 bounded action、写 checkpoint 并发送 `handed_off` H1。controller 收到后按 [session-dispatch.md](session-dispatch.md) 更新 routing，再由下一轮 sync 为新 session 建立 EOF baseline。
5. task 报 `ready_for_assignment` 后，controller 核验当前 revision 的 terminal acceptance，再执行 `retire --registry <absolute-registry-json> --node <task> --expect-current <current-task-session>`；随后跑一轮空 active 集合的 `sync` 与 `stall-check`，确认 `coordination_closed`。这是收尾步骤，不重新执行要求恰好一个 active child 的启动 preflight。

## 终态与阻塞

- task completion 不创建下一张 assignment card，也不产生 `reassignment_required`。
- solo 不启用 seam、Platform worker、claim 或 assignment requeue；跨域依赖应转为 Owner blocker。
- `report --state awaiting_seam`、`seam` 与 `act --dispatch` 在 solo 中均退出 `64`；H3 到达时只能 halt 或向 Owner escalation。
- `awaiting_owner` 必须绑定 decision ledger 中当前 pending 的 `decision_id`，先由 controller `decide --raise`，再接受 report；decision 解决后 child 回到 runnable watch-set。`awaiting_seam` 不属于 solo 路由。
- terminal child 退休后不再是 active node，不进入 poll watch-set、`reassignment_required` 或 H3 停滞集合。

## 预算

只观察 controller 与 task session。优先使用 rollout 增量 `last_token_usage.input_tokens` 和 `model_context_window`；token observer 不可用时使用已有 compaction-count fallback，缺失值保持未知。`handoff_due` 是 sticky stage，compact 后 token 降低也不回退。
