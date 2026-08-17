---
name: thread-harness
description: 当一个主控 thread 需要协调一个或多个任务包继续推进时使用；负责角色边界、profile 路由、状态回报、轮询、session 切换、预算交接以及 Owner 阻塞处理。
---

# Thread Harness

## 入口路由

1. 读取本页与 `sub-skills/owner-thread-broker/SUB-SKILL.md`，确认 registry、ledger 和 Owner 授权边界。
2. 从 registry 根部读取 `broker.profile`，只接受 `solo` 或 `swarm`。缺失、非法 profile 或非法 budget 时先执行 `preflight` 并停止。
3. `profile=solo` 读取 [profile-solo.md](references/profile-solo.md)；`profile=swarm` 读取 [profile-swarm.md](references/profile-swarm.md)。agent 不按 child 数量猜 profile。
4. 每轮只读取当前 role、当前 task 的 `package_entry` / active checkpoint，以及 `sync` 的 action summary；需要 handoff、Owner decision、seam 或完整性修复时，再读取对应 reference。

线程路由（谁是谁、session id 绑定）读取 `sub-skills/owner-thread-broker/SUB-SKILL.md`，本 skill 不重复。

## 五条硬规则

- **H1 回报触发**：turn 结束前，若 `head` 变了、状态从 `working` 变为 waiting、产生 Owner 级阻塞或 bounded assignment 结束，必须向主控发送 H1 JSON payload。
- **H2 账本**：controller 是 ledger 的指定写入者；child 状态只通过 H1 回报。CLI 的 `--source-session` 是防误操作与来源一致性护栏，不提供可信调用者鉴权。
- **H3 停滞二选一**：连续 5 轮所有 node 的 `head` 无变化，controller 必须派发或向 Owner 报告并结束 loop。细节见 profile 文档与 [role-c.md](references/role-c.md)。
- **H4 seam 归属**：等待跨域产物时使用带 producer 的 `seam_id`；找不到 producer 就上报并处理，不把无主 seam 当作自然等待。
- **H5 active node 无静默终态**：`ready_for_assignment` 只结束当前 bounded assignment。`swarm` 由 `reassignment_required` 驱动下一张卡、terminal 退休或 seam 转移；`solo` 不生成 assignment requeue。只有 `active=false` 表示 node 已退出 coordination。

## H1 JSON payload

child 通过现有 `send_message_to_thread` 发送 JSON，不运行 `ledger.py report`、`seam` 或 `decide`：

```json
{"v":1,"event":"head_changed|state_changed|owner_blocked|seam_delivered|handed_off","state":"working|awaiting_seam|awaiting_owner|ready_for_assignment","head":"<full-git-sha>","waiting_on":[],"artifact":null,"details":null,"note":"<short-fact>"}
```

`awaiting_seam` 使用 `waiting_on:["seam:<id>"]`；`ready_for_assignment` 不表示 package terminal；`details` 只承载 seam、Owner decision 或自交接所需的机械字段。controller 根据消息来源和 registry 唯一绑定 node/session，无法唯一绑定时停止，不猜测。

## 预算交接

`sync` 机械输出 `budget_stage` 与 `handoff_required`。预算阈值由 registry 的 budget 脚本计算；agent 不自行估算。`handoff_due` 后，controller 只追加一次 `act --handoff`，发送一次现有 `$handoff-to-new-session` 触发；task 完成当前 bounded action、写 checkpoint 后交接，收到 `handed_off` H1 再执行 `route`。

## 参考

- [profile-solo.md](references/profile-solo.md) — 单 controller、单 task、单 worktree 的监控与交接
- [profile-swarm.md](references/profile-swarm.md) — 多 task / Platform 的 routing、seam 与 H3 调度
- [session-dispatch.md](references/session-dispatch.md) — session 路由与角色化 continuation/assignment delta
- [poll-contract.md](references/poll-contract.md) — 固定 poll、budget summary 与 wake 语义
- [ledger-schema.md](references/ledger-schema.md) — 四个 JSONL 与 sync-state 字段
- [role-a.md](references/role-a.md) / [role-b.md](references/role-b.md) / [role-c.md](references/role-c.md) — 当前角色页
- [owner-thread-broker](sub-skills/owner-thread-broker/SUB-SKILL.md) — 线程路由与 Owner 授权边界
