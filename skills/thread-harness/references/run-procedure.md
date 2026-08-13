# 运行流程：职责、冷启动与首轮同步

本页只规定运行顺序。Owner 要粘贴的启动文本、goal 与 `create_thread` 授权来自
[goal-prompt.md](../goal-prompt.md)；controller 发给 child 的 registration、assignment card、接手与交接文本来自
[session-dispatch.md](session-dispatch.md)。不要从本页或历史设计记录复制模板。

## 一、职责

| 角色 | 运行职责 |
| --- | --- |
| Owner | 写清目标、结束判据、执行授权边界与排除项；亲自给出 `create_thread` 授权；确认 effort；处理 Owner 级决策。 |
| controller | 建 registry 与 ledger；按授权建线和派发；维护 session 路由；执行 preflight、poll、sync、stall-check、H3 动作与 terminal node 退休。 |
| child | 按当前任务包或 assignment card 推进；命中 H1 条件时向 controller 发送结构化报告；不直接写 ledger。 |

Owner goal 中的目标、结束判据、执行授权边界与排除项构成本 coordination 的常设授权（standing authority）。主控（controller）可在该边界内直接向当前 child 发送 registration、assignment card 与 H3 dispatch。coordination 内的 seam producer 调度属于执行路由；扩大 scope 或权限、改变长期 ownership，或者新增不可逆外部影响时，仍须向 Owner 提案。

新建或替换 thread 仍受 `create_thread` 工具授权约束：授权必须由 Owner 本人写入 goal 或当前对话，不能由上一任 controller 代写。Role B compaction 后派发新 card 不等于自动获准新建 thread；若需要 replacement thread，必须已有明确授权或先问 Owner。

## 二、冷启动

goal 是最后一步。先用普通消息引导 controller 完成：

1. 按 `../sub-skills/owner-thread-broker/SUB-SKILL.md` 建 registry，填好根部 `broker.profile`、三项 budget，以及各 node 的 `node_type`、task `package_entry`、`worktree`、`branch` 与 topic。
2. 执行 `ledger.py init --registry <absolute-registry-json>`。
3. 按 [session-dispatch.md](session-dispatch.md) 建立 child，并把返回的 session id 回填 registry。
4. 执行 `ledger.py preflight --registry <absolute-registry-json>`；只有 `PREFLIGHT OK` 才能继续。
5. 按 profile 文档与 [poll-contract.md](poll-contract.md) 跑首轮 poll，再执行 `ledger.py sync`；确认 `valid=yes` 且 `head_unavailable` 为空。该轮在 controller 与 active task current session rollout 的 EOF 建立 observer baseline；可用预算项进入 `budget_stage=tracking`，token/compaction 缺失保持未知，不猜成 0。

五步通过后，Owner 才把 [goal-prompt.md](../goal-prompt.md) 的 Role C goal 文本贴入 goal 框。goal 不内联 session id；controller 每轮从 registry 重新读取当前路由。

## 三、preflight

Owner 在设置 goal 前确认：

- goal 已填写目标、结束判据、执行授权边界与排除项；
- `create_thread` 授权由 Owner 本人给出，并覆盖本轮需要的新建或 replacement 情形；
- effort 档位已确认。

controller 在进入 loop 前确认：

- registry 的 `current_session_id`、`worktree`、`branch` 与实际状态一致；
- ledger 已初始化；
- child 已按两阶段契约注册，session id 已回填；
- preflight 输出 `PREFLIGHT OK`；
- 首轮 sync 输出 `valid=yes`，且 `head_unavailable` 为空。

任一项失败都先修正，不设置 goal，不进入自驱 loop。

## 四、进入 loop

goal 设置后，controller 每轮按以下顺序执行：

1. 读取 registry 的 profile、当前 role/task package entry/checkpoint 与 ledger action summary，机械推导 runnable watch-set。
2. 按 [poll-contract.md](poll-contract.md) 原样执行固定 poll。
3. 执行 `ledger.py sync`，检查摘要与自检结果。
4. 执行 `ledger.py stall-check`，按 [role-c.md](role-c.md) 的退出码契约行动。
5. `reassignment_required` 中的 node 若已核验 terminal，执行 `retire --registry <absolute-registry-json> --node <node> --expect-current <current-session>`；solo 最后一个 child 退休后跑一次空 active 集合的 `sync`，再由 `stall-check` 确认 `coordination_closed`。
6. `handoff_required` 非空时只追加一次 `act --handoff`，完成当前 bounded action 后复用 [session-dispatch.md](session-dispatch.md) 的交接文本；需要变更 child 当前任务时同样使用完整文本，不从聊天记忆重建旧模板。

Role A compaction 使用以 package entry 为恢复权威的短 catch-up；Role B 不恢复旧 card，由 controller 派发新的最小 card；Role C 从 registry、ledger 与 `status` 恢复。
