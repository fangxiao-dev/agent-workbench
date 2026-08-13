# Profile: swarm

## 形状

- 一个 controller 与多个 active task child；Platform child 可不声明 `package_entry`。
- 提供 `package_entry` 的 child 按 task adapter 校验；Platform child 只承担明确的共享 seam 或 bounded assignment。
- 每个 node 仍保持一个 worktree、一个 branch、一个 current session。

## 每轮

1. 从 `sync` action summary 处理 `reassignment_required`、`idle_nodes`、`changed_nodes`、Owner decision、seam ownership 与 budget stage。
2. 按 [poll-contract.md](poll-contract.md) 推导 runnable watch-set；保留固定 `120000` poll。
3. task session 与 controller 使用 token budget observer；Platform session 继续遵循 assignment/compaction card，不进入 task budget handoff。
4. `handoff_due` 后由 controller 对当前 active node 追加一次 handoff action；新 session 的 `route` 后在下一轮 sync 建立新 baseline。

## 调度

- 保留多 node routing、worktree/branch 隔离、seam、Platform 与 H3 dispatch。
- `ready_for_assignment` 或历史 `done` 进入 `reassignment_required`；controller 在下一轮 poll 前派卡、核验 terminal 后退休，或转成带 producer 的 `awaiting_seam`。
- seam 登记与 Owner decision 只由 controller 写入；child 只发送 H1。
