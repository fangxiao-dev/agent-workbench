---
name: thread-harness
description: >
  多 thread 编排的角色定义与控制流。当一个主控 thread 需要长时间调度多条子 thread
  推进同一个目标时使用：确定自己是主控 / 任务包子线 / Platform 子线中的哪个角色、
  什么时候必须向上回报、怎么轮询、怎么判断整体是否还在推进、卡住了怎么办。
  涉及 broker loop、wait_threads、派发任务、seam 缺失、停滞、Owner 决策上报时适用。
  线程路由（thread-id 与 topic 绑定）由本目录下的 owner-thread-broker 负责，本 skill 不重复。
---

# Thread Harness

一个主控 thread 带若干子 thread 长跑时，最容易出的不是某一步做错，而是**整体停下来了却没人发现**。

## 先确定你是谁

| 你的处境 | 你的角色 | 读哪一页 |
| --- | --- | --- |
| 你有一个明确的任务包要做完 | **任务包子线** | [role-a.md](references/role-a.md) |
| 你没有任务包，被指派去造某个共享的东西 | **Platform 子线** | [role-b.md](references/role-b.md) |
| 你负责调度别人、自己不写业务代码 | **主控** | [role-c.md](references/role-c.md) |

**读完本页，再只读你自己那一页。** 其他角色页不用看。

线程路由（谁是谁、session id 绑定）用 `$owner-thread-broker`，本 skill 不重复。

## 四条硬规则

只有这四条是硬的，其余全是引导。

- **H1 回报触发**：turn 结束前，若 ①`head` 变了 ②状态从 working 转为 waiting ③产生 Owner 级阻塞——三者任一成立，**必须**向主控发送 H1 envelope。
- **H2 账本**：controller 是 ledger 的唯一写入者。子线不调用 `ledger.py`，状态变更一律走 H1。**不要把进度只留在自己的上下文里**，它会被 compaction 清掉。
- **H3 停滞二选一**（主控专属，判定细节见 [role-c.md](references/role-c.md)）：连续 5 轮所有 node 的 `head` 无变化 → 派发新工作，或向 Owner 报告并结束 loop。**没有第三个选项。**
- **H4 seam 归属**：任何"我在等某个上游产物"都要指向一个 `seam_id`，且该 seam 在账本里要有 `producer`。查不到 producer 时**立即上报，不要继续等**。脚本只在 `sync` 摘要里报 `seams_unowned` 计数，**不阻断**，这条靠你自己守。

## 任务怎么分工

- impl / investigate → `$investigate-before-implement`
- review → `$do-review`
- 验收 → `$verification-before-completion`，不外包

## H1 envelope

子线通过现有 `send_message_to_thread` 发送一段 JSON，不运行 `ledger.py report`、`seam` 或 `decide`。字段固定为：

```json
{"v":1,"registry":"<absolute-registry-json>","coordination_id":"<id>","node":"<node>","session_id":"<current-session-id>","event":"head_changed|state_changed|owner_blocked|seam_delivered|handed_off","state":"working|awaiting_seam|awaiting_owner|done","head":"<full-git-sha>","waiting_on":[],"artifact":null,"details":null,"note":"<short-fact>"}
```

`awaiting_seam` 必须带 `waiting_on:["seam:<id>"]`；其他状态通常为空数组。`session_id` 必须是 child 当前 session，`artifact` 在无交付物时为 `null`。`details` 只承载事件所需的机械字段：seam 交付带 `seam_id/consumers`，Owner 阻塞带 `decision_id/blocks/question`，自交接带 `new_session_id`；其他事件为 `null`。

controller 重新读取 `registry`，确认 session 仍是该 node 的 current session，并确认 H1 的 HEAD 既是最新 ledger HEAD 的后代、又位于该 node 当前 worktree HEAD 的历史上，才可用现有 ledger 命令 append。seam 登记与 Owner decision 也只由 controller 写入。

## 参考

- [session-dispatch.md](references/session-dispatch.md) — 建线与交接的两阶段契约、派发模板
- [poll-contract.md](references/poll-contract.md) — 固定 JS 片段、wake 语义（主控用）
- [ledger-schema.md](references/ledger-schema.md) — 四个 JSONL 的字段定义
- [owner-thread-broker](owner-thread-broker/SKILL.md) — 线程路由与 Owner 授权边界
