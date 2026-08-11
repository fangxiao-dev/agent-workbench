---
name: thread-harness
description: 当一个主控 thread 需要长期协调多条子 thread 推进同一目标时使用；负责角色边界、状态回报、轮询、路由切换、停滞以及 seam / Owner 阻塞处理。
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

线程路由（谁是谁、session id 绑定）读取 `sub-skills/owner-thread-broker/SUB-SKILL.md`，本 skill 不重复。

## 五条硬规则

只有这五条是硬的，其余全是引导。

- **H1 回报触发**：turn 结束前，若 ①`head` 变了 ②状态从 working 转为 waiting ③产生 Owner 级阻塞 ④bounded assignment 结束——四者任一成立，**必须**向主控发送 H1 JSON payload。
- **H2 账本**：主控（controller）是账本（ledger）的指定写入者。子线不调用 `ledger.py`，状态变更一律走 H1。命令行接口（CLI）不提供可信调用者鉴权；`act --halt --source-session` 只是防误操作与来源一致性护栏。**不要把进度只留在自己的上下文里**，它会被 compaction 清掉。
- **H3 停滞二选一**（主控专属，判定细节见 [role-c.md](references/role-c.md)）：连续 5 轮所有 node 的 `head` 无变化 → 派发新工作，或向 Owner 报告并结束 loop。**没有第三个选项。**
- **H4 seam 归属**：任何"我在等某个上游产物"都要指向一个 `seam_id`，且该 seam 在账本里要有 `producer`。查不到 producer 时**立即上报，不要继续等**。脚本只在 `sync` 摘要里报 `seams_unowned` 计数，**不阻断**，这条靠你自己守。
- **H5 active node 无静默终态**（主控专属）：bounded assignment 结束只报 `ready_for_assignment`，不代表 package、node 或 coordination 完成。`sync` 将其列入 `reassignment_required`；主控进入下一轮 poll 前必须派下一张卡、核验 terminal 后设 registry `active=false`，或转成带 producer 的 `awaiting_seam`。只有 `active=false` 表示 node 已退出 coordination。

## 任务怎么分工

- main session / subagent 调度 → `/impl-package:subagent-driven-development`
- impl / investigate → `/impl-package:investigate-before-implement`
- review → `/impl-package:do-review`
- 验收 → `/impl-package:verification-before-completion`，不外包

## H1 JSON payload

子线通过现有 `send_message_to_thread` 发送一段 JSON，不运行 `ledger.py report`、`seam` 或 `decide`。字段固定为：

```json
{"v":1,"event":"head_changed|state_changed|owner_blocked|seam_delivered|handed_off","state":"working|awaiting_seam|awaiting_owner|ready_for_assignment","head":"<full-git-sha>","waiting_on":[],"artifact":null,"details":null,"note":"<short-fact>"}
```

`awaiting_seam` 必须带 `waiting_on:["seam:<id>"]`；其他状态通常为空数组。`ready_for_assignment` 只结束当前 assignment，不宣称 package terminal；历史 `done` 仅为兼容输入，controller 必须按 `ready_for_assignment` 处理。`artifact` 在无交付物时为 `null`。`details` 只承载事件所需的机械字段：seam 交付带 `seam_id/consumers`，Owner 阻塞带 `decision_id/blocks/question`，自交接带 `new_session_id`；其他事件为 `null`。

controller 根据消息来源和自己持有的 registry 唯一绑定 routing；无法唯一绑定时停止，不猜测。绑定后重新读取 registry，确认来源仍是该 node 的 current session，并确认 H1 的 HEAD 既是最新 ledger HEAD 的后代、又位于该 node 当前 worktree HEAD 的历史上，才可用现有 ledger 命令 append。seam 登记与 Owner decision 也只由 controller 写入。

## 参考

- [session-dispatch.md](references/session-dispatch.md) — 建线与交接的两阶段契约、派发模板
- [poll-contract.md](references/poll-contract.md) — 固定 JS 片段、wake 语义（主控用）
- [ledger-schema.md](references/ledger-schema.md) — 四个 JSONL 的字段定义
- [owner-thread-broker](sub-skills/owner-thread-broker/SUB-SKILL.md) — 线程路由与 Owner 授权边界
