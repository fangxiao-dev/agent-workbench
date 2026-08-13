# 阶段 D-1：外层 broker/controller 初版合同

- 父文档：[README.md](README.md)「阶段 D：外层 broker/controller」
- 状态：锁定设计；D-1 broker MVP 已实施并通过 thread-harness 验证
- 适用范围：thread-harness 作为 impl-package 外层消费者

本页细化父文档的阶段 D 初版合同。它不改变 impl-package 的 Ticket、evidence、acceptance、dependency 或 package `state.json` 语义；与父文档冲突时，以父文档为准。

## 1. 目标与边界

阶段 D-1 提供一个 user-facing broker/controller，用于：

- 监控 task session、worktree、Git HEAD 和结构化回报；
- 在 Owner 授权 envelope 内路由任务、阻塞和 session handoff；
- 单写 coordination ledger；
- 机械化计算当前 session 的上下文预算，并在达到 handoff 阈值时触发交接。

broker 不代写 package `state.json`，不判断 Ticket acceptance，也不把 handoff、checkpoint 或 broker ledger 当作 acceptance evidence。

## 2. Package consumer contract

broker 通过一个薄的 package adapter 消费 impl-package 的 3.5 projection。adapter 不承担迁移或业务 schema 完整性校验；package state 缺失、旧格式或字段不完整时只输出 schema warning，并将无法确认的 package facts 置空，不阻断 broker preflight。broker 本身不写入 package state。

adapter 对 broker 暴露以下最小只读事实：

| 字段 | 含义 |
| --- | --- |
| `package_entry` | 当前任务包的恢复入口绝对路径 |
| `active_checkpoint` | 当前 session 可恢复的 checkpoint 指针；无法确认时为 `null` |
| `next_action` | checkpoint 中唯一的下一动作；无法确认时为 `null`，broker 不从聊天历史重建 |
| `worktree` / `branch` / `head` | 当前 task session 实际使用的实现上下文 |
| `current_session_id` | registry 中该 package node 的当前 session |
| `revision` | adapter 读取结果对应的 package/repository revision |

这些字段只用于恢复锚点、路由和监控。package session 仍是包内状态的唯一 writer；需要改变包内事实时，broker 发送结构化指令，由 package session 自己落盘。

## 3. Coordination profiles

thread-harness 只定义两个 profile：`solo` 与 `swarm`。

profile 写入 coordination registry，由 router 读取；agent 不根据 child 数量自行猜测 profile。

### `solo`

- 一个 controller、一个 task package session、一个实现 worktree；
- 普通单任务包直接使用 impl-package 时不加载 thread-harness；`solo` 只表示该单 task 已进入 broker coordination；
- package entry/checkpoint 是恢复权威；
- 不启用跨包 seam、Platform worker、assignment requeue 或 swarm claim；
- broker 只负责监控、Owner blocker、上下文预算和 handoff。

### `swarm`

- 多个 task package session，通常各自拥有独立 worktree/branch；
- coordination ledger 记录 session claim、跨包 seam、阻塞、派发和交接；
- 可启用 Platform worker、H3 停滞处理和跨 node 路由；
- 每个 node 仍保持一个 writer、一个 worktree、一个 branch 的约束。

router 的加载顺序固定为：

1. 读取 thread-harness 入口页和 registry；
2. 按 `profile` 读取 `solo` 或 `swarm` controller contract；
3. 只读取当前 node 的 role 页面、package entry/checkpoint 和 `ledger.py sync` action summary；
4. 只有遇到 handoff、Owner decision、seam 或完整性错误时，才读取对应 reference。

agent 不在每轮重新读取完整 registry、四个 JSONL 或全部 thread-harness references。

## 4. Context budget handoff

token observer 增量读取当前 session rollout 的 `token_count` 事件：

- 使用最近一次请求的 `last_token_usage` 作为当前上下文占用近似值；
- 使用事件中的 `model_context_window` 作为窗口容量；
- 不使用累计的 `total_token_usage` 判断当前窗口位置。

预算 policy 由 registry/runtime 配置提供，阈值由脚本机械计算：

```text
tail_reserve_tokens = tail_requests × tail_p75_increment_tokens
handoff_at = smart_zone_tokens − tail_reserve_tokens
```

agent 不计算阈值，只消费 `ledger.py sync` 输出的 `budget_stage`。阶段 D-1 只定义两个有效阶段：

- `tracking`：尚未达到 handoff 阈值；
- `handoff_due`：已达到阈值，状态保持，不能因后续 compact 导致 token 数下降而自动清除。

进入 `handoff_due` 后，controller 只发送一次现有 handoff 触发消息。task session 完成当前 bounded action、写 active checkpoint，并按 `$handoff-to-new-session` 交接。broker 在收到 `handed_off` H1 后更新 registry routing。

compact count 保留为诊断和 token observer 不可用时的兼容 fallback；它不再是正常 handoff 的主要触发条件。

阶段 D-1 不新增 emergency handoff 状态、不修改固定 `120000` poll contract，也不要求 agent 解释或重算预算。

## 5. Ownership

| 事实 | 唯一 writer |
| --- | --- |
| package Ticket、evidence、checkpoint、`state.json` | task package session |
| session routing、claim、seam、Owner decision、handoff 记录 | broker/controller |
| worker 执行证据 | worker 返回，package session 或 broker 按所属层落盘 |
| Owner 级授权 | Owner；controller 只代理和传达 |

broker ledger 是协调事实源，不是 package acceptance state；package state 也不是跨 package coordination ledger。

## 6. 阶段 D-1 不包含

- impl-package 内部 Ticket-first runtime、迁移或 acceptance 改造；
- seam admission 或跨 package acceptance 边设计；
- broker 代写 package state；
- 为 token policy 增加 adaptive poll、emergency 状态或多阶段 handoff；
- 把 `solo` 与 `swarm` 做成两个独立 skill。

## 7. 初版验收

阶段 D-1 实施后，至少应证明：

1. `solo` 能在现有 package adapter 下完成监控、预算阈值触发和 session handoff，且 broker 没有写 package state。
2. `swarm` 保留现有多 node routing、worktree 隔离、seam/claim 和 Owner boundary。
3. token fixture 能证明阈值由脚本计算、只触发一次、compact 不会清除 `handoff_due`，新 session 会建立新的预算基线。
4. package consumer contract 只依赖 entry、checkpoint、next action 和上下文锚点；package schema warning 不会变成 registry 阻断，也不会让 broker 代写 package state。
